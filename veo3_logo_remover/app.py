"""Main PyQt6 window for the Veo3 logo remover."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .region import Region, veo3_preset
from .video import FFmpegNotFoundError, VideoInfo, grab_frame, probe
from .widgets import FramePreview
from .worker import RemovalWorker

VIDEO_FILTER = "Videos (*.mp4 *.mov *.mkv *.webm *.avi *.m4v);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Veo3 Logo Remover")
        self.resize(1040, 680)

        self._info: VideoInfo | None = None
        self._worker: RemovalWorker | None = None

        self._build_ui()
        self._build_menu()
        self._update_controls()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)

        self.preview = FramePreview()
        self.preview.regionChanged.connect(self._on_region_changed)
        layout.addWidget(self.preview, stretch=3)

        side = QVBoxLayout()
        layout.addLayout(side, stretch=1)

        self.open_btn = QPushButton("Open video…")
        self.open_btn.clicked.connect(self.open_video)
        side.addWidget(self.open_btn)

        self.info_label = QLabel("No video loaded.")
        self.info_label.setWordWrap(True)
        side.addWidget(self.info_label)

        # Frame scrubber
        scrub_box = QGroupBox("Preview frame")
        scrub_layout = QVBoxLayout(scrub_box)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 1000)
        self.frame_slider.valueChanged.connect(self._on_scrub)
        scrub_layout.addWidget(self.frame_slider)
        side.addWidget(scrub_box)

        # Region controls
        region_box = QGroupBox("Logo region (pixels)")
        region_layout = QVBoxLayout(region_box)
        self.preset_btn = QPushButton("Use Veo3 preset (bottom-right)")
        self.preset_btn.clicked.connect(self.apply_preset)
        region_layout.addWidget(self.preset_btn)

        self.spin_x = self._make_spin()
        self.spin_y = self._make_spin()
        self.spin_w = self._make_spin()
        self.spin_h = self._make_spin()
        for label, spin in (
            ("X", self.spin_x),
            ("Y", self.spin_y),
            ("Width", self.spin_w),
            ("Height", self.spin_h),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(spin)
            region_layout.addLayout(row)
        region_layout.addWidget(
            QLabel("Tip: drag on the preview to draw the box.")
        )
        side.addWidget(region_box)

        # Method + quality
        options_box = QGroupBox("Options")
        options_layout = QVBoxLayout(options_box)
        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Method"))
        self.method_combo = QComboBox()
        self.method_combo.addItem("Delogo (fast, blends edges)", "delogo")
        self.method_combo.addItem("Inpaint (OpenCV Telea)", "inpaint")
        method_row.addWidget(self.method_combo)
        options_layout.addLayout(method_row)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("Quality"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("High", "high")
        self.quality_combo.addItem("Medium", "medium")
        self.quality_combo.addItem("Low (smaller file)", "low")
        quality_row.addWidget(self.quality_combo)
        options_layout.addLayout(quality_row)
        side.addWidget(options_box)

        # Export
        self.export_btn = QPushButton("Remove logo & export…")
        self.export_btn.clicked.connect(self.export_video)
        side.addWidget(self.export_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_export)
        self.cancel_btn.setEnabled(False)
        side.addWidget(self.cancel_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        side.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        side.addWidget(self.log_view, stretch=1)

        for spin in (self.spin_x, self.spin_y, self.spin_w, self.spin_h):
            spin.valueChanged.connect(self._on_spin_changed)

        self.setCentralWidget(central)

    def _make_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 100000)
        return spin

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("&Open video…", self)
        open_action.triggered.connect(self.open_video)
        file_menu.addAction(open_action)
        quit_action = QAction("&Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    # -------------------------------------------------------------- actions
    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open video", str(Path.home()), VIDEO_FILTER
        )
        if not path:
            return
        try:
            info = probe(path)
        except FFmpegNotFoundError as exc:
            QMessageBox.critical(self, "ffmpeg missing", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Could not open video", str(exc))
            return

        self._info = info
        self.info_label.setText(
            f"{Path(path).name}\n{info.width}x{info.height}  "
            f"{info.fps:.2f} fps  {info.duration:.1f}s  "
            f"audio: {'yes' if info.has_audio else 'no'}"
        )
        self.frame_slider.setValue(0)
        self._load_preview(0.0)
        self.apply_preset()
        self._update_controls()

    def _load_preview(self, position: float) -> None:
        if not self._info:
            return
        try:
            frame = grab_frame(self._info.path, position)
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Preview error: {exc}")
            return
        self.preview.set_frame(frame)
        self.preview.set_region(self.preview.region())

    def _on_scrub(self, value: int) -> None:
        if self._info:
            self._load_preview(value / 1000.0)

    def apply_preset(self) -> None:
        if not self._info:
            return
        region = veo3_preset(self._info.width, self._info.height)
        self._set_region(region)

    def _on_region_changed(self, region: Region) -> None:
        self._set_region(region, from_preview=True)

    def _on_spin_changed(self) -> None:
        if not self._info:
            return
        region = Region(
            self.spin_x.value(),
            self.spin_y.value(),
            self.spin_w.value(),
            self.spin_h.value(),
        ).clamped(self._info.width, self._info.height)
        self.preview.set_region(region)

    def _set_region(self, region: Region, from_preview: bool = False) -> None:
        for spin in (self.spin_x, self.spin_y, self.spin_w, self.spin_h):
            spin.blockSignals(True)
        self.spin_x.setValue(region.x)
        self.spin_y.setValue(region.y)
        self.spin_w.setValue(region.w)
        self.spin_h.setValue(region.h)
        for spin in (self.spin_x, self.spin_y, self.spin_w, self.spin_h):
            spin.blockSignals(False)
        if not from_preview:
            self.preview.set_region(region)

    def export_video(self) -> None:
        if not self._info:
            return
        region = Region(
            self.spin_x.value(),
            self.spin_y.value(),
            self.spin_w.value(),
            self.spin_h.value(),
        ).clamped(self._info.width, self._info.height)
        if region.w < 2 or region.h < 2:
            QMessageBox.warning(self, "No region", "Select the logo region first.")
            return

        default_name = self._info.path.with_name(
            self._info.path.stem + "_nologo.mp4"
        )
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save cleaned video", str(default_name), "MP4 video (*.mp4)"
        )
        if not out_path:
            return

        self._worker = RemovalWorker(
            self._info,
            region,
            out_path,
            method=self.method_combo.currentData(),
            quality=self.quality_combo.currentData(),
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._append_log)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self.progress.setValue(0)
        self._set_busy(True)
        self._append_log(f"Exporting to {out_path}")
        self._worker.start()

    def cancel_export(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("Cancelling…")

    # -------------------------------------------------------------- signals
    def _on_progress(self, value: float) -> None:
        self.progress.setValue(int(value * 100))

    def _on_finished(self, path: str) -> None:
        self._set_busy(False)
        self.progress.setValue(100)
        self._append_log(f"Done: {path}")
        QMessageBox.information(self, "Finished", f"Saved cleaned video to:\n{path}")

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        self._append_log(f"Failed: {message}")
        QMessageBox.critical(self, "Export failed", message)

    # --------------------------------------------------------------- helpers
    def _append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    def _set_busy(self, busy: bool) -> None:
        self.export_btn.setEnabled(not busy)
        self.open_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)

    def _update_controls(self) -> None:
        has_video = self._info is not None
        for widget in (
            self.export_btn,
            self.preset_btn,
            self.frame_slider,
            self.method_combo,
            self.quality_combo,
            self.spin_x,
            self.spin_y,
            self.spin_w,
            self.spin_h,
        ):
            widget.setEnabled(has_video)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
