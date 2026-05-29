"""Logo region geometry in native video pixel coordinates."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """A rectangular region in pixel coordinates (top-left origin)."""

    x: int
    y: int
    w: int
    h: int

    def clamped(self, width: int, height: int) -> Region:
        """Clamp the region so it stays fully inside a ``width`` x ``height`` frame."""

        x = max(0, min(self.x, max(0, width - 1)))
        y = max(0, min(self.y, max(0, height - 1)))
        w = max(1, min(self.w, width - x))
        h = max(1, min(self.h, height - y))
        return Region(x, y, w, h)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


def veo3_preset(width: int, height: int) -> Region:
    """Return the default region for the Flow Veo logo (bottom-right corner).

    Flow stamps an animated "Veo" wordmark in the bottom-right corner. The exact
    glyph is small, but we pad generously so the watermark is fully covered; the
    user can fine-tune the box afterwards.
    """

    w = max(1, round(width * 0.18))
    h = max(1, round(height * 0.10))
    margin_x = round(width * 0.015)
    margin_y = round(height * 0.025)
    x = width - margin_x - w
    y = height - margin_y - h
    return Region(x, y, w, h).clamped(width, height)
