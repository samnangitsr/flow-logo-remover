"""Logo removal back-ends: ffmpeg ``delogo`` and OpenCV inpainting."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from .region import Region
from .video import VideoInfo, ffmpeg_path

ProgressCb = Callable[[float], None]
LogCb = Callable[[str], None]

QUALITY_CRF = {
    "high": "16",
    "medium": "20",
    "low": "26",
}


def _noop(_value) -> None:  # pragma: no cover - trivial
    return None


def safe_delogo_region(region: Region, width: int, height: int) -> Region:
    """Clamp ``region`` so ffmpeg ``delogo`` keeps a 1px border to sample from.

    ``delogo`` interpolates a box from the pixels immediately surrounding it, so
    the box must not touch the frame border. Corner watermarks naturally touch
    two edges, so we nudge the box inward by a pixel on each side.
    """

    region = region.clamped(width, height)
    x = min(max(region.x, 1), max(1, width - 2))
    y = min(max(region.y, 1), max(1, height - 2))
    w = max(1, min(region.w, width - 1 - x))
    h = max(1, min(region.h, height - 1 - y))
    return Region(x, y, w, h)


def build_delogo_command(
    info: VideoInfo,
    region: Region,
    output: str | Path,
    quality: str = "high",
) -> list[str]:
    """Build the ffmpeg command for delogo-based removal."""

    safe = safe_delogo_region(region, info.width, info.height)
    delogo = f"delogo=x={safe.x}:y={safe.y}:w={safe.w}:h={safe.h}"
    crf = QUALITY_CRF.get(quality, QUALITY_CRF["high"])

    cmd = [
        ffmpeg_path(),
        "-y",
        "-i",
        str(info.path),
        "-vf",
        delogo,
        "-c:v",
        "libx264",
        "-crf",
        crf,
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
    ]
    if info.has_audio:
        cmd += ["-c:a", "copy"]
    cmd += ["-progress", "pipe:1", "-nostats", str(output)]
    return cmd


def _parse_progress_line(line: str) -> float | None:
    """Return out_time in seconds from a ffmpeg -progress line, else None."""

    line = line.strip()
    if line.startswith("out_time_ms="):
        value = line.split("=", 1)[1]
        try:
            return int(value) / 1_000_000.0
        except ValueError:
            return None
    if line.startswith("out_time_us="):
        value = line.split("=", 1)[1]
        try:
            return int(value) / 1_000_000.0
        except ValueError:
            return None
    return None


def run_delogo(
    info: VideoInfo,
    region: Region,
    output: str | Path,
    quality: str = "high",
    progress_cb: ProgressCb = _noop,
    log_cb: LogCb = _noop,
    should_cancel: Callable[[], bool] | None = None,
) -> Path:
    """Remove the logo using ffmpeg ``delogo`` and write to ``output``."""

    cmd = build_delogo_command(info, region, output, quality)
    log_cb("Running: " + " ".join(cmd))

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    duration = max(info.duration, 0.001)
    try:
        for line in process.stdout:
            if should_cancel and should_cancel():
                process.terminate()
                raise RuntimeError("Cancelled by user.")
            seconds = _parse_progress_line(line)
            if seconds is not None:
                progress_cb(min(1.0, seconds / duration))
            elif line.strip() and "=" not in line:
                log_cb(line.rstrip())
    finally:
        process.stdout.close()
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg exited with code {code}")
    progress_cb(1.0)
    return Path(output)


def _build_inpaint_sink_command(
    info: VideoInfo,
    output: str | Path,
    quality: str,
) -> list[str]:
    crf = QUALITY_CRF.get(quality, QUALITY_CRF["high"])
    cmd = [
        ffmpeg_path(),
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{info.width}x{info.height}",
        "-r",
        f"{info.fps}",
        "-i",
        "pipe:0",
    ]
    if info.has_audio:
        cmd += ["-i", str(info.path), "-map", "0:v:0", "-map", "1:a:0?"]
    cmd += [
        "-c:v",
        "libx264",
        "-crf",
        crf,
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
    ]
    if info.has_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd += [str(output)]
    return cmd


def run_inpaint(
    info: VideoInfo,
    region: Region,
    output: str | Path,
    quality: str = "high",
    radius: int = 3,
    progress_cb: ProgressCb = _noop,
    log_cb: LogCb = _noop,
    should_cancel: Callable[[], bool] | None = None,
) -> Path:
    """Remove the logo by inpainting each frame with OpenCV (Telea)."""

    safe = region.clamped(info.width, info.height)
    capture = cv2.VideoCapture(str(info.path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {info.path}")

    mask = np.zeros((info.height, info.width), dtype=np.uint8)
    mask[safe.y : safe.y + safe.h, safe.x : safe.x + safe.w] = 255

    cmd = _build_inpaint_sink_command(info, output, quality)
    log_cb("Running: " + " ".join(cmd))
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    assert process.stdin is not None

    total = max(info.frame_count, 1)
    index = 0
    try:
        while True:
            if should_cancel and should_cancel():
                raise RuntimeError("Cancelled by user.")
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            cleaned = cv2.inpaint(frame, mask, radius, cv2.INPAINT_TELEA)
            process.stdin.write(cleaned.tobytes())
            index += 1
            progress_cb(min(1.0, index / total))
    finally:
        capture.release()
        if process.stdin:
            process.stdin.close()
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg exited with code {code}")
    progress_cb(1.0)
    return Path(output)
