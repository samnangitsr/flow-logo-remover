from veo3_logo_remover.region import Region, veo3_preset
from veo3_logo_remover.remover import safe_delogo_region


def test_clamp_keeps_region_inside_frame():
    region = Region(x=1900, y=1050, w=400, h=400).clamped(1920, 1080)
    assert region.x + region.w <= 1920
    assert region.y + region.h <= 1080
    assert region.w >= 1 and region.h >= 1


def test_clamp_negative_origin():
    region = Region(x=-50, y=-50, w=100, h=100).clamped(1280, 720)
    assert region.x == 0 and region.y == 0


def test_veo3_preset_is_bottom_right():
    region = veo3_preset(1920, 1080)
    assert region.x > 1920 / 2
    assert region.y > 1080 / 2
    assert region.x + region.w <= 1920
    assert region.y + region.h <= 1080


def test_safe_delogo_region_keeps_border():
    # A corner region touching both edges must be nudged inward by 1px.
    region = Region(x=1700, y=900, w=220, h=180)  # touches right/bottom of 1920x1080
    safe = safe_delogo_region(region, 1920, 1080)
    assert safe.x >= 1
    assert safe.y >= 1
    assert safe.x + safe.w <= 1920 - 1
    assert safe.y + safe.h <= 1080 - 1
