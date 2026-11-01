"""Small standard-library helpers shared by the reference/verification CLIs."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from fractions import Fraction
from uuid import uuid4


class MediaError(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def configure_output():
    # Keep Chinese paths legible when Windows captures the CLI through UTF-8 pipes.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_tool(name, explicit=None, project_root=None):
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(explicit)
        if found:
            return found
        raise MediaError("Explicit {} was not found: {}".format(name, explicit))
    found = shutil.which(name)
    if found:
        return found
    if project_root:
        base = Path(project_root).expanduser().resolve() / "node_modules" / "@remotion"
        packages = ["win32-x64-msvc", "linux-x64-gnu", "darwin-arm64", "darwin-x64"]
        # Prefer a package matching this host if a project holds several platforms.
        preferred = "win32" if os.name == "nt" else "darwin" if __import__("sys").platform == "darwin" else "linux"
        packages.sort(key=lambda item: not item.startswith(preferred))
        for package in packages:
            for filename in (name + ".exe", name) if package.startswith("win32") else (name, name + ".exe"):
                candidate = base / ("compositor-" + package) / filename
                if candidate.is_file():
                    return str(candidate)
    raise MediaError("{} not found. Set --{}, add it to PATH, or pass --project-root.".format(name, name))


def run(command, timeout=1800):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [str(part) for part in command], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace", timeout=timeout, **kwargs
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MediaError("Could not run {}: {}".format(command[0], error)) from error
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-8000:]
        raise MediaError("{} exited {}: {}".format(Path(command[0]).name, result.returncode, detail))
    return result.stdout


def finite_number(value, label, positive=False):
    if isinstance(value, bool):
        raise MediaError("{} must be a finite number".format(label))
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise MediaError("{} must be a finite number".format(label)) from error
    if not math.isfinite(number) or (positive and number <= 0):
        raise MediaError("{} must be {}finite".format(label, "positive and " if positive else ""))
    return number


def rate(value, label="fps"):
    try:
        result = float(Fraction(str(value)))
    except (ValueError, TypeError, ZeroDivisionError) as error:
        raise MediaError("Invalid {}: {}".format(label, value)) from error
    return finite_number(result, label, positive=True)


def probe(ffprobe, path, count_frames=False, timeout=1800):
    command = [ffprobe, "-v", "error"]
    if count_frames:
        command.append("-count_frames")
    command += ["-show_streams", "-show_format", "-of", "json", str(path)]
    try:
        result = json.loads(run(command, timeout=timeout))
    except json.JSONDecodeError as error:
        raise MediaError("ffprobe returned invalid JSON") from error
    video = next((stream for stream in result.get("streams", []) if stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic")), None)
    if not video:
        raise MediaError("Input has no video stream: {}".format(path))
    audio = [stream for stream in result.get("streams", []) if stream.get("codec_type") == "audio"]
    duration = result.get("format", {}).get("duration", video.get("duration"))
    duration = finite_number(duration, "media duration", positive=True)
    fps_value = video.get("avg_frame_rate")
    if fps_value in (None, "0/0", "0"):
        fps_value = video.get("r_frame_rate")
    fps = rate(fps_value)
    measured_frames = video.get("nb_read_frames") if count_frames else video.get("nb_frames")
    try:
        frame_count = int(measured_frames)
    except (ValueError, TypeError):
        frame_count = None
    try:
        video_duration = finite_number(video.get("duration"), "video duration", positive=True)
    except MediaError:
        video_duration = frame_count / fps if frame_count and frame_count > 0 else duration
    return {
        "width": int(video["width"]), "height": int(video["height"]),
        "fps": fps, "fpsFraction": fps_value, "frames": frame_count,
        "durationSeconds": duration, "videoDurationSeconds": video_duration, "videoCodec": video.get("codec_name"),
        "videoStreamIndex": video["index"],
        "audioStreams": [{"index": item["index"], "codec": item.get("codec_name"), "sampleRate": item.get("sample_rate"), "channels": item.get("channels")} for item in audio],
    }


def validate_times(values, duration):
    times = [finite_number(value, "frame time") for value in values]
    if not times:
        raise MediaError("At least one frame time is required")
    for value in times:
        if value < 0 or value >= duration:
            raise MediaError("Frame time {} is outside [0, {}) seconds".format(value, duration))
    return times


def extract_frame(ffmpeg, source, output, second, video_index=0, width=None, timeout=1800):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-v", "error", "-nostdin", "-y", "-ss", "{:.9f}".format(second), "-i", str(source), "-map", "0:{}".format(video_index), "-frames:v", "1", "-an"]
    if width:
        command += ["-vf", "scale={}:-2".format(width)]
    command += ["-c:v", "png", "-threads", "1", "-f", "image2", "-update", "1", str(output)]
    run(command, timeout=timeout)
    if not output.is_file() or not output.stat().st_size:
        raise MediaError("Frame extraction produced no image at {} seconds".format(second))
    return output


def decode_all(ffmpeg, source, video_index=0, timeout=1800):
    # Remotion's bundled FFmpeg omits the default wrapped_avframe encoder.
    # Explicit rawvideo/PCM keep the null sink portable, including audio decode.
    command = [ffmpeg, "-v", "error", "-nostdin", "-xerror", "-threads", "2", "-i", str(source), "-map", "0:{}".format(video_index), "-map", "0:a?", "-c:v", "rawvideo", "-threads:v", "2", "-c:a", "pcm_s16le", "-f", "null", "-"]
    run(command, timeout=timeout)

