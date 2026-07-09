"""Frameless quick-controls popup, docked in a screen corner by default and
freely movable by dragging its handle."""

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, QFrame
)

from .hotkey_capture import pretty_hotkey


class _DragHandle(QLabel):
    """A small grip bar; dragging it moves the popup (its child buttons/
    sliders would otherwise eat every mouse press before it reached them)."""

    def __init__(self, popup):
        super().__init__("⠷⠷  Crier")
        self._popup = popup
        self._offset = None
        self.setObjectName("handle")
        self.setCursor(Qt.SizeAllCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._offset = event.globalPosition().toPoint() - self._popup.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._offset is not None:
            self._popup.move(event.globalPosition().toPoint() - self._offset)
            self._popup.mark_user_moved()
            event.accept()

    def mouseReleaseEvent(self, event):
        self._offset = None
        event.accept()


class ControlPopup(QWidget):
    play_pause = Signal()
    stop = Signal()
    reread = Signal()
    read_selection = Signal()
    open_settings = Signal()
    quit_app = Signal()
    speed_changed = Signal(float)     # 0.5 .. 2.0
    volume_changed = Signal(float)    # 0.0 .. 1.0

    def __init__(self, speed: float, volume: float, hotkey_read: str = ""):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowTitle("Crier")
        self._user_moved = False

        card = QFrame(self)
        card.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(12, 8, 12, 10)
        root.setSpacing(8)

        self.drag_handle = _DragHandle(self)
        root.addWidget(self.drag_handle)

        # Primary action
        self.btn_read = QPushButton("Read Selection")
        self.btn_read.setCursor(Qt.PointingHandCursor)
        self.btn_read.setObjectName("readBtn")
        root.addWidget(self.btn_read)

        self.status_label = QLabel("Select text anywhere, then use the hotkey or this button.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        # Transport row
        row = QHBoxLayout()
        self.btn_play = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        self.btn_reread = QPushButton("Re-read")
        for b in (self.btn_play, self.btn_stop, self.btn_reread):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        root.addLayout(row)

        # Settings / Hide / Quit row
        row2 = QHBoxLayout()
        self.btn_settings = QPushButton("Settings")
        self.btn_hide = QPushButton("Hide")
        self.btn_quit = QPushButton("Quit")
        for b in (self.btn_settings, self.btn_hide, self.btn_quit):
            b.setCursor(Qt.PointingHandCursor)
            row2.addWidget(b)
        root.addLayout(row2)

        # Speed
        root.addWidget(QLabel("Speed"))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(50, 200)          # 0.50x .. 2.00x
        self.speed.setValue(int(speed * 100))
        self.speed_label = QLabel(f"{speed:.2f}x")
        srow = QHBoxLayout()
        srow.addWidget(self.speed)
        srow.addWidget(self.speed_label)
        root.addLayout(srow)

        # Volume
        root.addWidget(QLabel("Volume"))
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(volume * 100))
        self.volume_label = QLabel(f"{int(volume * 100)}%")
        vrow = QHBoxLayout()
        vrow.addWidget(self.volume)
        vrow.addWidget(self.volume_label)
        root.addLayout(vrow)

        # Wiring
        self.btn_read.clicked.connect(self.read_selection.emit)
        self.btn_play.clicked.connect(self.play_pause.emit)
        self.btn_stop.clicked.connect(self.stop.emit)
        self.btn_reread.clicked.connect(self.reread.emit)
        self.btn_settings.clicked.connect(self.open_settings.emit)
        self.btn_hide.clicked.connect(self.hide)
        self.btn_quit.clicked.connect(self.quit_app.emit)
        self.speed.valueChanged.connect(self._on_speed)
        self.volume.valueChanged.connect(self._on_volume)

        self.setStyleSheet(
            """
            #card { background: #1f2330; border: 1px solid #3a4054; border-radius: 12px; }
            QLabel { color: #c8cede; font-size: 12px; }
            QLabel#status { color: #9aa3b8; font-size: 11px; }
            QLabel#handle {
                color: #6a7286; font-size: 11px; letter-spacing: 1px;
                padding: 2px 0 4px 0;
            }
            QPushButton {
                background: #2c3244; color: #e8ecf6; border: 1px solid #3a4054;
                border-radius: 8px; padding: 6px 10px; font-size: 12px;
            }
            QPushButton:hover { background: #39415a; }
            QPushButton#readBtn { background: #3a5ba0; border-color: #4d76c4; font-weight: 600; }
            QPushButton#readBtn:hover { background: #4569b8; }
            QSlider::groove:horizontal { height: 4px; background: #3a4054; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -6px 0; border-radius: 7px; background: #6ea8fe; }
            """
        )
        self.setFixedWidth(280)
        self.set_hotkey_hint(hotkey_read)

    def set_playing(self, playing: bool):
        self.btn_play.setText("Pause" if playing else "Play")

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_hotkey_hint(self, hotkey_read: str):
        pretty = pretty_hotkey(hotkey_read) if hotkey_read else ""
        self.btn_read.setText(f"Read Selection ({pretty})" if pretty else "Read Selection")
        self.btn_read.setToolTip(f"Same as pressing {pretty}" if pretty else "")

    def mark_user_moved(self):
        self._user_moved = True

    def _on_speed(self, val):
        self.speed_label.setText(f"{val / 100:.2f}x")
        self.speed_changed.emit(val / 100.0)

    def _on_volume(self, val):
        self.volume_label.setText(f"{val}%")
        self.volume_changed.emit(val / 100.0)

    def show_popup(self):
        """Show the popup - docked in a screen corner the first time (and
        any time after the user hasn't dragged it), otherwise wherever the
        user last left it."""
        if not self._user_moved:
            self._dock_in_corner()
        self.show()
        self.raise_()
        self.activateWindow()

    def _dock_in_corner(self):
        self.adjustSize()
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        margin = 16
        x = geo.right() - self.width() - margin
        y = geo.bottom() - self.height() - margin
        self.move(QPoint(x, y))
