#!/usr/bin/env python3
"""Measure, fully decode, and extract review frames from a rendered series report."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from media_utils import MediaError, configure_output, decode_all, extract_frame, finite_number, find_tool, now, probe, rate, run_id, sha256, validate_times, write_json


def load_report(path):
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict) or type(data.get("version")) is not int or data.get("version") != 1 or data.get("mode") not in ("render", "preview"):
        raise MediaError("Report must have version:1 and mode:'render' or 'preview'")
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise MediaError("Report episodes must be a nonempty array")
    ids = set()
    for item in episodes:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise MediaError("Each episode needs a nonempty string id")
        if item["id"] in ids:
            raise MediaError("Duplicate episode id: " + item["id"])
        ids.add(item["id"])
        if not isinstance(item.get("path"), str) or not item["path"].strip() or "://" in item["path"]:
            raise MediaError(item["id"] + ": path must be a local video path")
        for field in ("width", "height", "frames"):
            if isinstance(item.get(field), bool) or not isinstance(item.get(field), int) or item[field] <= 0:
                raise MediaError(item["id"] + ": " + field + " must be a positive integer")
        item["expectedFps"] = rate(item.get("fps"))
        item["durationSeconds"] = finite_number(item.get("durationSeconds"), "durationSeconds", positive=True)
        if not isinstance(item.get("audioExpected"), bool):
            raise MediaError(item["id"] + ": audioExpected must be boolean")
        if not isinstance(item.get("checkSeconds"), list):
            raise MediaError(item["id"] + ": checkSeconds must be an array")
        item["checkSeconds"] = validate_times(item["checkSeconds"], item["durationSeconds"])
        media = Path(item["path"]).expanduser()
        item["resolvedPath"] = str((media if media.is_absolute() else path.parent / media).resolve())
    return data, hashlib.sha256(raw).hexdigest()


def folder_id(identifier):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", identifier).strip("-")[:70] or "episode"
    return stem + "-" + hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:8]


def verify_episode(spec, ffmpeg, ffprobe, frame_root, run_identifier, timeout, duration_tolerance):
    source = Path(spec["resolvedPath"])
    result = {"id": spec["id"], "path": str(source), "status": "running", "passed": False, "checkedAt": now(), "runId": run_identifier, "checks": {}, "frames": [], "reused": False}
    try:
        if not source.is_file():
            raise MediaError("Video does not exist: " + str(source))
        fingerprint = sha256(source)
        result.update(sha256=fingerprint, bytes=source.stat().st_size)
        metadata = probe(ffprobe, source, count_frames=True, timeout=timeout)
        result["measured"] = metadata
        expected = {field: spec[field] for field in ("width", "height", "fps", "frames", "durationSeconds", "audioExpected", "checkSeconds")}
        result["expected"] = expected
        tolerance = duration_tolerance if duration_tolerance is not None else max(0.1, 2 / spec["expectedFps"])
        checks = {
            "width": metadata["width"] == spec["width"],
            "height": metadata["height"] == spec["height"],
            "fps": abs(metadata["fps"] - spec["expectedFps"]) <= max(0.0001, spec["expectedFps"] * 0.00001),
            "frames": metadata["frames"] == spec["frames"],
            "duration": abs(metadata["durationSeconds"] - spec["durationSeconds"]) <= tolerance,
            "audio": bool(metadata["audioStreams"]) == spec["audioExpected"],
        }
        result["checks"] = checks
        result["durationToleranceSeconds"] = tolerance
        mismatches = [key for key, passed in checks.items() if not passed]
        if mismatches:
            raise MediaError("Metadata mismatch: " + ", ".join(mismatches))
        times = validate_times(spec["checkSeconds"], min(metadata["durationSeconds"], metadata["videoDurationSeconds"]))
        decode_all(ffmpeg, source, metadata["videoStreamIndex"], timeout=timeout)
        checks["fullDecode"] = True
        image_dir = frame_root / folder_id(spec["id"]) / run_identifier
        for number, second in enumerate(times, 1):
            output = image_dir / "check-{:03d}.png".format(number)
            extract_frame(ffmpeg, source, output, second, metadata["videoStreamIndex"], 960, timeout)
            result["frames"].append({"number": number, "seconds": second, "path": str(output), "bytes": output.stat().st_size})
        cover_second = min(1.0, max(0, min(metadata["durationSeconds"], metadata["videoDurationSeconds"]) - max(0.05, 1 / metadata["fps"])))
        cover = image_dir / "cover.png"
        extract_frame(ffmpeg, source, cover, cover_second, metadata["videoStreamIndex"], timeout=timeout)
        result["cover"] = {"seconds": cover_second, "path": str(cover), "bytes": cover.stat().st_size}
        checks["frameExtraction"] = True
        checks["coverExtraction"] = True
        if sha256(source) != fingerprint:
            raise MediaError("Video changed during verification; rerun against a stable file")
        result.update(status="passed", passed=True, checkedAt=now())
    except (MediaError, OSError, ValueError) as error:
        result.update(status="failed", passed=False, checkedAt=now(), error=str(error))
    return result


def retained_record(spec, prior, report_digest):
    """Keep prior evidence only when the report, video bytes and artifacts still match."""
    empty = {"id": spec["id"], "path": spec["resolvedPath"], "status": "not_checked", "passed": False, "reason": "Not selected in this run; no matching verified result"}
    if prior.get("version") != 1 or prior.get("reportSha256") != report_digest:
        return empty
    old_episodes = prior.get("episodes", [])
    if not isinstance(old_episodes, list):
        return empty
    record = next((item for item in old_episodes if isinstance(item, dict) and item.get("id") == spec["id"]), None)
    if not record or record.get("status") != "passed" or not record.get("passed"):
        return empty
    checks = record.get("checks", {})
    required = ("width", "height", "fps", "frames", "duration", "audio", "fullDecode", "frameExtraction", "coverExtraction")
    if not isinstance(checks, dict) or any(checks.get(key) is not True for key in required):
        return empty
    if not isinstance(record.get("frames"), list) or not isinstance(record.get("cover"), dict):
        return empty
    try:
        if sha256(spec["resolvedPath"]) != record.get("sha256"):
            empty["reason"] = "Video bytes changed; previous success invalidated"
            return empty
        artifacts = record.get("frames", []) + [record.get("cover", {})]
        if len(record.get("frames", [])) != len(spec["checkSeconds"]):
            return empty
        if any(not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"] or not Path(item["path"]).is_file() or Path(item["path"]).stat().st_size != item.get("bytes") for item in artifacts):
            empty["reason"] = "Review artifacts missing or changed; previous success invalidated"
            return empty
    except OSError:
        return empty
    return dict(record, reused=True, revalidatedAt=now())


def main(argv=None):
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="version:1 render-report.json; relative video paths resolve from this file")
    parser.add_argument("--output", help="Verification JSON path (default: verification.json beside the report)")
    parser.add_argument("--part", action="append", help="Episode id to verify; repeat to select several")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--project-root")
    parser.add_argument("--timeout", type=float, default=1800, help="Maximum seconds per subprocess")
    parser.add_argument("--duration-tolerance", type=float, help="Allowed duration delta; default max(0.1 seconds, 2 frames)")
    args = parser.parse_args(argv)
    report_path = Path(args.report).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else report_path.parent / "verification.json"
    result = {"version": 1, "runId": run_id(), "checkedAt": now(), "reportPath": str(report_path), "status": "running", "passed": False, "episodes": []}
    try:
        if output_path == report_path:
            raise MediaError("--output must differ from --report; the render report is read-only")
        prior = {}
        if output_path.is_file():
            try:
                prior = json.loads(output_path.read_text(encoding="utf-8-sig"))
                if not isinstance(prior, dict):
                    prior = {}
            except (OSError, ValueError):
                prior = {}
        # Clear a previous top-level success before any new validation can fail.
        write_json(output_path, result)
        report, digest = load_report(report_path)
        result.update(mode=report["mode"], reportSha256=digest)
        selected = set(args.part or [item["id"] for item in report["episodes"]])
        unknown = selected - {item["id"] for item in report["episodes"]}
        if unknown:
            raise MediaError("Unknown --part: " + ", ".join(sorted(unknown)))
        result["selectedParts"] = sorted(selected)
        finite_number(args.timeout, "--timeout", positive=True)
        if args.duration_tolerance is not None:
            finite_number(args.duration_tolerance, "--duration-tolerance")
            if args.duration_tolerance < 0:
                raise MediaError("--duration-tolerance cannot be negative")
        result["episodes"] = [retained_record(spec, prior, digest) if spec["id"] not in selected else {"id": spec["id"], "path": spec["resolvedPath"], "status": "pending", "passed": False} for spec in report["episodes"]]
        write_json(output_path, result)
        ffmpeg = find_tool("ffmpeg", args.ffmpeg, args.project_root)
        ffprobe = find_tool("ffprobe", args.ffprobe, args.project_root)
        result["tools"] = {"ffmpeg": ffmpeg, "ffprobe": ffprobe}
        for index, spec in enumerate(report["episodes"]):
            if spec["id"] not in selected:
                continue
            print("Verifying {}...".format(spec["id"]), flush=True)
            result["episodes"][index] = verify_episode(spec, ffmpeg, ffprobe, output_path.parent / "verification-frames", result["runId"], args.timeout, args.duration_tolerance)
            write_json(output_path, result)
            record = result["episodes"][index]
            print("{}: {}{}".format(spec["id"], record["status"], " — " + record["error"] if record.get("error") else ""), flush=True)
        if sha256(report_path) != digest:
            raise MediaError("Render report changed during verification; rerun against a stable report")
        selected_failed = any(not item.get("passed") for item in result["episodes"] if item["id"] in selected)
        all_passed = all(item.get("passed") for item in result["episodes"])
        result.update(status="failed" if selected_failed else "passed" if all_passed else "partial", passed=all_passed and not selected_failed, checkedAt=now())
        write_json(output_path, result)
        print("Verification {} (mode={}): {}".format(result["status"], result["mode"], output_path))
        return 1 if selected_failed else 0
    except (MediaError, OSError, ValueError, TypeError) as error:
        result.update(status="failed", passed=False, checkedAt=now(), error=str(error))
        if output_path != report_path:
            try:
                write_json(output_path, result)
            except OSError:
                pass
        print("Verification failed: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
