"""A horizontal slider that jumps straight to wherever you click (and drag),
instead of QSlider's default page-step-towards-the-click behavior."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSlider

_STEPS = 1000  # internal resolution; position is exposed/set as a 0.0-1.0 fraction


class SeekSlider(QSlider):
    seek_requested = Signal(float)   # 0.0 .. 1.0, emitted live while dragging/clicking

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.setRange(0, _STEPS)
        self._dragging = False

    def _fraction_at(self, x: int) -> float:
        return max(0.0, min(1.0, x / max(1, self.width())))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._dragging = True
        frac = self._fraction_at(int(event.position().x()))
        self.setValue(int(frac * _STEPS))
        self.seek_requested.emit(frac)
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return super().mouseMoveEvent(event)
        frac = self._fraction_at(int(event.position().x()))
        self.setValue(int(frac * _STEPS))
        self.seek_requested.emit(frac)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def set_position(self, frac: float):
        """External position update (e.g. from a playback-progress timer).
        Ignored while the user is actively clicking/dragging, so it doesn't
        fight their input."""
        if self._dragging:
            return
        self.setValue(int(max(0.0, min(1.0, frac)) * _STEPS))
