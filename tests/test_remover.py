from pathlib import Path

from veo3_logo_remover.region import Region
from veo3_logo_remover.remover import _parse_progress_line, build_delogo_command
from veo3_logo_remover.video import VideoInfo


def _info(has_audio: bool = True) -> VideoInfo:
    return VideoInfo(
        path=Path("/tmp/in.mp4"),
        width=1920,
        height=1080,
        duration=10.0,
        fps=30.0,
        has_audio=has_audio,
    )


def test_build_delogo_command_contains_filter():
    cmd = build_delogo_command(_info(), Region(1700, 900, 200, 150), "/tmp/out.mp4")
    joined = " ".join(cmd)
    assert "delogo=" in joined
    assert "-progress" in cmd
    assert "/tmp/out.mp4" in cmd


def test_build_delogo_command_copies_audio_when_present():
    cmd = build_delogo_command(_info(has_audio=True), Region(10, 10, 50, 50), "/tmp/o.mp4")
    assert "copy" in cmd


def test_build_delogo_command_skips_audio_when_absent():
    cmd = build_delogo_command(_info(has_audio=False), Region(10, 10, 50, 50), "/tmp/o.mp4")
    assert "-c:a" not in cmd


def test_parse_progress_line():
    assert _parse_progress_line("out_time_ms=5000000") == 5.0
    assert _parse_progress_line("out_time_us=2500000") == 2.5
    assert _parse_progress_line("progress=continue") is None
    assert _parse_progress_line("garbage") is None
