"""Custom Qt widgets for previewing a frame and selecting the logo region."""

from __future__ import annotations

import cv2
import numpy as np
from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from .region import Region


def bgr_to_qpixmap(frame: np.ndarray) -> QPixmap:
    """Convert an OpenCV BGR frame to a QPixmap."""

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, _ = rgb.shape
    image = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class FramePreview(QWidget):
    """Displays a video frame and lets the user drag a selection rectangle.

    The selection is reported in native video pixel coordinates via
    :attr:`regionChanged`.
    """

    regionChanged = pyqtSignal(object)  # noqa: N815 (Qt signal naming)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 270)
        self._pixmap: QPixmap | None = None
        self._frame_size = (0, 0)
        self._region: Region | None = None
        self._drag_start: QPoint | None = None
        self._drag_end: QPoint | None = None
        self.setMouseTracking(True)

    def set_frame(self, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]
        self._frame_size = (width, height)
        self._pixmap = bgr_to_qpixmap(frame)
        self.update()

    def set_region(self, region: Region | None) -> None:
        self._region = region
        self.update()

    def region(self) -> Region | None:
        return self._region

    def _display_rect(self) -> QRect:
        """Rectangle (in widget coords) where the frame is drawn, letterboxed."""

        if not self._pixmap or self._frame_size == (0, 0):
            return QRect()
        fw, fh = self._frame_size
        scale = min(self.width() / fw, self.height() / fh)
        dw, dh = int(fw * scale), int(fh * scale)
        ox, oy = (self.width() - dw) // 2, (self.height() - dh) // 2
        return QRect(ox, oy, dw, dh)

    def _widget_to_frame(self, point: QPoint) -> QPoint:
        rect = self._display_rect()
        if rect.isEmpty():
            return QPoint(0, 0)
        fw, fh = self._frame_size
        rel_x = (point.x() - rect.x()) / rect.width()
        rel_y = (point.y() - rect.y()) / rect.height()
        fx = int(round(max(0.0, min(1.0, rel_x)) * fw))
        fy = int(round(max(0.0, min(1.0, rel_y)) * fh))
        return QPoint(fx, fy)

    def _frame_to_widget(self, x: int, y: int) -> QPoint:
        rect = self._display_rect()
        fw, fh = self._frame_size
        if fw == 0 or fh == 0:
            return QPoint(0, 0)
        wx = rect.x() + int(round(x / fw * rect.width()))
        wy = rect.y() + int(round(y / fh * rect.height()))
        return QPoint(wx, wy)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._pixmap and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            self._drag_end = event.pos()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is not None:
            self._drag_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is None:
            return
        start = self._widget_to_frame(self._drag_start)
        end = self._widget_to_frame(event.pos())
        self._drag_start = None
        self._drag_end = None
        x, y = min(start.x(), end.x()), min(start.y(), end.y())
        w, h = abs(end.x() - start.x()), abs(end.y() - start.y())
        if w >= 4 and h >= 4:
            fw, fh = self._frame_size
            self._region = Region(x, y, w, h).clamped(fw, fh)
            self.regionChanged.emit(self._region)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))
        if not self._pixmap:
            painter.setPen(QColor(180, 180, 180))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Open a video to preview a frame",
            )
            return

        rect = self._display_rect()
        painter.drawPixmap(rect, self._pixmap)

        if self._region is not None:
            top_left = self._frame_to_widget(self._region.x, self._region.y)
            bottom_right = self._frame_to_widget(
                self._region.x + self._region.w, self._region.y + self._region.h
            )
            box = QRect(top_left, bottom_right)
            overlay = QColor(255, 80, 80, 70)
            painter.fillRect(box, overlay)
            painter.setPen(QPen(QColor(255, 80, 80), 2))
            painter.drawRect(box)

        if self._drag_start is not None and self._drag_end is not None:
            painter.setPen(QPen(QColor(80, 180, 255), 2, Qt.PenStyle.DashLine))
            painter.drawRect(QRect(self._drag_start, self._drag_end))
