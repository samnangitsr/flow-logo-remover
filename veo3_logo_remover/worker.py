"""Background worker that runs logo removal off the GUI thread."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from .region import Region
from .remover import run_delogo, run_inpaint
from .video import VideoInfo


class RemovalWorker(QThread):
    """Runs a removal back-end and reports progress/log/result via signals."""

    progress = pyqtSignal(float)
    log = pyqtSignal(str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        info: VideoInfo,
        region: Region,
        output: str | Path,
        method: str = "delogo",
        quality: str = "high",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._info = info
        self._region = region
        self._output = output
        self._method = method
        self._quality = quality
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D401 - QThread entry point
        try:
            common = dict(
                info=self._info,
                region=self._region,
                output=self._output,
                quality=self._quality,
                progress_cb=self.progress.emit,
                log_cb=self.log.emit,
                should_cancel=lambda: self._cancel,
            )
            if self._method == "inpaint":
                result = run_inpaint(**common)
            else:
                result = run_delogo(**common)
            self.finished_ok.emit(str(result))
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(exc))
