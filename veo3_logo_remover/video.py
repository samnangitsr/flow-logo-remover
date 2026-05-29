"""Video probing and frame extraction helpers built on ffprobe/OpenCV."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class FFmpegNotFoundError(RuntimeError):
    """Raised when the ffmpeg/ffprobe binaries are not available on PATH."""


@dataclass(frozen=True)
class VideoInfo:
    """Basic metadata about a video file."""

    path: Path
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool

    @property
    def frame_count(self) -> int:
        return int(round(self.duration * self.fps))


def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegNotFoundError("ffmpeg was not found on PATH.")
    return path


def ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise FFmpegNotFoundError("ffprobe was not found on PATH.")
    return path


def _parse_fraction(value: str | None) -> float:
    if not value:
        return 0.0
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            denom = float(den)
            if denom == 0:
                return 0.0
            return float(num) / denom
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def probe(path: str | Path) -> VideoInfo:
    """Return metadata for ``path`` using ffprobe."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Video not found: {path}")

    cmd = [
        ffprobe_path(),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError(f"No video stream found in {path}")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    fps = _parse_fraction(video_stream.get("avg_frame_rate"))
    if fps <= 0:
        fps = _parse_fraction(video_stream.get("r_frame_rate"))

    duration = 0.0
    if video_stream.get("duration"):
        duration = float(video_stream["duration"])
    elif data.get("format", {}).get("duration"):
        duration = float(data["format"]["duration"])

    return VideoInfo(
        path=path,
        width=width,
        height=height,
        duration=duration,
        fps=fps if fps > 0 else 30.0,
        has_audio=has_audio,
    )


def grab_frame(path: str | Path, position: float = 0.0) -> np.ndarray:
    """Grab a single BGR frame from ``path`` at the given ``position`` (0..1)."""

    path = str(path)
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError(f"Could not open video: {path}")
    try:
        total = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if total and total > 0:
            target = int(max(0.0, min(1.0, position)) * (total - 1))
            capture.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = capture.read()
        if not ok or frame is None:
            raise ValueError(f"Could not read a frame from: {path}")
        return frame
    finally:
        capture.release()
