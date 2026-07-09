"""A Snip & Sketch style region-select overlay: shows a frozen screenshot
of the whole virtual desktop, dims everything outside the drag rectangle,
and hands back the cropped selection as a QPixmap."""

from PySide6.QtCore import Qt, QRect, QRectF, QPoint, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QPainterPath, QColor, QPen, QPixmap
from PySide6.QtWidgets import QWidget

_MIN_SIZE = 6  # px; smaller than this on release counts as "clicked, not dragged"


def _grab_virtual_desktop() -> tuple[QPixmap, QRect]:
    """One flat screenshot spanning every monitor, in logical (DPI-independent)
    coordinates - so it lines up 1:1 with mouse events on the overlay widget
    regardless of each screen's own scale factor."""
    screens = QGuiApplication.screens()
    virtual_rect = QRect()
    for s in screens:
        virtual_rect = virtual_rect.united(s.geometry())

    combined = QPixmap(virtual_rect.size())
    combined.fill(Qt.black)
    painter = QPainter(combined)
    for s in screens:
        shot = s.grabWindow(0)
        target = QRect(s.geometry().topLeft() - virtual_rect.topLeft(), s.geometry().size())
        painter.drawPixmap(target, shot, QRect(QPoint(0, 0), shot.size()))
    painter.end()
    combined.setDevicePixelRatio(1.0)
    return combined, virtual_rect


class RegionSelectOverlay(QWidget):
    region_captured = Signal(QPixmap)
    cancelled = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self._background, virtual_rect = _grab_virtual_desktop()
        self.setGeometry(virtual_rect)

        self._selecting = False
        self._start = QPoint()
        self._current = QRect()

    def show_and_focus(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.OtherFocusReason)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._background)

        dim_area = QPainterPath()
        dim_area.addRect(QRectF(self.rect()))
        sel = self._current.normalized()
        if self._selecting and not sel.isEmpty():
            hole = QPainterPath()
            hole.addRect(QRectF(sel))
            dim_area = dim_area.subtracted(hole)
        painter.fillPath(dim_area, QColor(0, 0, 0, 140))

        if self._selecting and not sel.isEmpty():
            painter.setPen(QPen(QColor("#6ea8fe"), 2))
            painter.drawRect(sel)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.position().toPoint()
            self._current = QRect(self._start, self._start)
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._selecting:
            self._current = QRect(self._start, event.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._selecting:
            return
        self._selecting = False
        rect = self._current.normalized()
        self.close()
        if rect.width() >= _MIN_SIZE and rect.height() >= _MIN_SIZE:
            self.region_captured.emit(self._background.copy(rect))
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._selecting = False
            self.close()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)
