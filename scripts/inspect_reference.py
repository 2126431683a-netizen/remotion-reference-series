#!/usr/bin/env python3
"""Inspect a local reference video without third-party Python packages."""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import sys
from urllib.parse import quote

from media_utils import MediaError, configure_output, extract_frame, finite_number, find_tool, now, probe, run_id, sha256, validate_times, write_json


def sheet(path, manifest):
    title = "Reference contact sheet"
    cards = []
    for item in manifest.get("frames", []):
        relative = Path(item["path"]).relative_to(path.parent).as_posix()
        cards.append('<figure><a href="{0}"><img src="{0}" loading="lazy" alt="Frame {1}"></a><figcaption>#{1:03d} · {2:.3f} s</figcaption></figure>'.format(quote(relative), item["number"], item["seconds"]))
    error = "<p class=error>{}</p>".format(html.escape(manifest.get("error", ""))) if manifest.get("error") else ""
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{font:16px system-ui,sans-serif;background:#171922;color:#eef0f5;margin:24px}}header{{max-width:1100px;margin-bottom:24px}}p{{overflow-wrap:anywhere}}main{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}}figure{{margin:0;background:#272b38;padding:10px}}img{{display:block;width:100%;height:auto}}figcaption{{padding-top:8px}}.error{{color:#ff9999}}</style>
<header><h1>{title}</h1><p>{source}</p><p>Status: {status}. Still-image inspection only; audio has not been listened to.</p>{error}</header><main>{cards}</main></html>""".format(title=title, source=html.escape(manifest["input"]), status=html.escape(manifest["status"]), error=error, cards="\n".join(cards))
    path.write_text(page, encoding="utf-8")


def main(argv=None):
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local video path")
    parser.add_argument("--output", required=True, help="Directory for frames.json and offline contact-sheet.html")
    parser.add_argument("--times", help="Comma-separated seconds, e.g. 0,10,30; each must be below duration")
    parser.add_argument("--samples", type=int, default=12, help="Evenly spaced samples if --times is omitted (default: 12)")
    parser.add_argument("--frame-width", type=int, default=960, help="Extracted PNG width, preserving aspect ratio")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--project-root", help="Find Remotion compositor binaries under this project")
    parser.add_argument("--timeout", type=float, default=1800, help="Maximum seconds for each subprocess")
    args = parser.parse_args(argv)
    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    manifest = {"version": 1, "runId": run_id(), "checkedAt": now(), "input": str(source), "status": "running", "passed": False, "frames": []}
    try:
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "frames.json", manifest)
        sheet(output / "contact-sheet.html", manifest)
        if not source.is_file():
            raise MediaError("Input video does not exist: {}".format(source))
        finite_number(args.timeout, "--timeout", positive=True)
        if args.samples < 1 or args.frame_width < 1:
            raise MediaError("--samples, --frame-width and --timeout must be positive")
        ffmpeg = find_tool("ffmpeg", args.ffmpeg, args.project_root)
        ffprobe = find_tool("ffprobe", args.ffprobe, args.project_root)
        metadata = probe(ffprobe, source, timeout=args.timeout)
        manifest["media"] = metadata
        fingerprint = sha256(source)
        manifest["inputSha256"] = fingerprint
        if args.times is None:
            end = max(0, min(metadata["durationSeconds"], metadata["videoDurationSeconds"]) - max(0.05, 1 / metadata["fps"]))
            values = [0] if args.samples == 1 else [end * index / (args.samples - 1) for index in range(args.samples)]
        else:
            values = args.times.split(",")
        times = validate_times(values, min(metadata["durationSeconds"], metadata["videoDurationSeconds"]))
        manifest["times"] = times
        image_dir = output / "frames" / manifest["runId"]
        for number, second in enumerate(times, 1):
            path = image_dir / "frame-{:04d}.png".format(number)
            extract_frame(ffmpeg, source, path, second, metadata["videoStreamIndex"], args.frame_width, args.timeout)
            manifest["frames"].append({"number": number, "seconds": second, "path": str(path), "bytes": path.stat().st_size})
        if sha256(source) != fingerprint:
            raise MediaError("Input video changed during inspection; rerun against a stable file")
        manifest.update(status="passed", passed=True, checkedAt=now())
        write_json(output / "frames.json", manifest)
        sheet(output / "contact-sheet.html", manifest)
        print("Extracted {} frames: {}".format(len(times), output / "contact-sheet.html"))
        return 0
    except (MediaError, OSError, ValueError) as error:
        manifest.update(status="failed", passed=False, checkedAt=now(), error=str(error))
        try:
            write_json(output / "frames.json", manifest)
            sheet(output / "contact-sheet.html", manifest)
        except OSError:
            pass
        print("Inspection failed: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

