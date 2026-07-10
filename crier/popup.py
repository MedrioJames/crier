"""Frameless quick-controls popup, docked in a screen corner by default and
freely movable by dragging its handle."""

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, QFrame
)

from .hotkey_capture import pretty_hotkey
from .seek_slider import SeekSlider

_SPEED_MIN = 5     # 0.5x, in tenths
_SPEED_MAX = 40     # 4.0x, in tenths


class _DragHandle(QLabel):
    """The draggable part of the title bar; dragging it moves the popup
    (its sibling icon buttons get normal clicks - Qt only routes mouse
    events here when the pointer is actually over this label)."""

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
    smart = Signal()
    open_settings = Signal()
    quit_app = Signal()
    seek_requested = Signal(float)    # 0.0 .. 1.0
    speed_changed = Signal(float)     # 0.5 .. 2.0
    volume_changed = Signal(float)    # 0.0 .. 1.0

    def __init__(self, speed: float, volume: float, hotkey_smart: str = ""):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
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

        titlebar = QHBoxLayout()
        titlebar.setSpacing(2)
        self.drag_handle = _DragHandle(self)
        titlebar.addWidget(self.drag_handle, 1)
        self.btn_settings = QPushButton("⚙")
        self.btn_hide = QPushButton("–")
        self.btn_quit = QPushButton("✕")
        for b, tip in (
            (self.btn_settings, "Settings"), (self.btn_hide, "Hide"), (self.btn_quit, "Quit"),
        ):
            b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("titleBtn")
            b.setFixedSize(24, 22)
            b.setToolTip(tip)
            titlebar.addWidget(b)
        root.addLayout(titlebar)

        # Primary action: reads the selection, or screen-grabs if there isn't one.
        self.btn_smart = QPushButton("Read / Screen Grab")
        self.btn_smart.setCursor(Qt.PointingHandCursor)
        self.btn_smart.setObjectName("smartBtn")
        root.addWidget(self.btn_smart)

        self.status_label = QLabel("Select text anywhere, then use the hotkey or this button.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("status")
        root.addWidget(self.status_label)

        # Transport: compact icon buttons over a seek bar.
        # U+23F8/U+23F9 (the "proper" pause/stop symbols) get substituted
        # with Segoe UI Emoji's color glyphs (solid blue rounded squares) -
        # the Unicode text-presentation selector doesn't stop Qt's font
        # fallback from picking that font in the first place. Using plain
        # ASCII / pre-emoji-era glyphs sidesteps the substitution entirely.
        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_play = QPushButton("▶")
        self.btn_stop = QPushButton("■")
        self.btn_reread = QPushButton("↻")
        for b in (self.btn_play, self.btn_stop, self.btn_reread):
            b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("iconBtn")
            b.setFixedSize(36, 30)
            row.addWidget(b)
        row.addStretch(1)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("time")
        row.addWidget(self.time_label)
        root.addLayout(row)

        self.seek = SeekSlider()
        root.addWidget(self.seek)

        # Speed - stepped in 0.1x increments (0.5x .. 4.0x) rather than a
        # freely-sliding scale, with +/- buttons at each end for one-click
        # nudges. Internally the slider works in tenths of x (5 == 0.5x).
        root.addWidget(QLabel("Speed"))
        self.btn_speed_down = QPushButton("−")
        self.btn_speed_up = QPushButton("+")
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(_SPEED_MIN, _SPEED_MAX)
        self.speed.setSingleStep(1)
        self.speed.setPageStep(1)
        self.speed.setValue(round(speed * 10))
        self.speed_label = QLabel(f"{speed:.1f}x")
        for b in (self.btn_speed_down, self.btn_speed_up):
            b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("iconBtn")
            b.setFixedSize(28, 26)
        srow = QHBoxLayout()
        srow.addWidget(self.btn_speed_down)
        srow.addWidget(self.speed, 1)
        srow.addWidget(self.btn_speed_up)
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
        self.btn_smart.clicked.connect(self.smart.emit)
        self.btn_play.clicked.connect(self.play_pause.emit)
        self.btn_stop.clicked.connect(self.stop.emit)
        self.btn_reread.clicked.connect(self.reread.emit)
        self.btn_settings.clicked.connect(self.open_settings.emit)
        self.btn_hide.clicked.connect(self.hide)
        self.btn_quit.clicked.connect(self.quit_app.emit)
        self.seek.seek_requested.connect(self.seek_requested.emit)
        self.speed.valueChanged.connect(self._on_speed)
        self.btn_speed_down.clicked.connect(lambda: self.speed.setValue(self.speed.value() - 1))
        self.btn_speed_up.clicked.connect(lambda: self.speed.setValue(self.speed.value() + 1))
        self.volume.valueChanged.connect(self._on_volume)

        # Click-toolbar buttons, not tab-focusable form controls - without
        # this Qt draws a lingering focus rectangle around whichever one
        # was clicked last (the "blue box" around e.g. Stop after using it).
        for b in self.findChildren(QPushButton):
            b.setFocusPolicy(Qt.NoFocus)

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
            QPushButton#smartBtn { background: #3a5ba0; border-color: #4d76c4; font-weight: 600; }
            QPushButton#smartBtn:hover { background: #4569b8; }
            QPushButton#iconBtn { font-size: 15px; padding: 0px; }
            QPushButton#titleBtn {
                background: transparent; border: none; color: #7d859c;
                font-size: 13px; border-radius: 5px; padding: 0px;
            }
            QPushButton#titleBtn:hover { background: #333a4f; color: #e8ecf6; }
            QLabel#time { color: #9aa3b8; font-size: 11px; }
            QSlider::groove:horizontal { height: 4px; background: #3a4054; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -6px 0; border-radius: 7px; background: #6ea8fe; }
            """
        )
        self.setFixedWidth(280)
        self.set_smart_hotkey_hint(hotkey_smart)

    def set_playing(self, playing: bool):
        self.btn_play.setText("| |" if playing else "▶")

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_position(self, frac: float, pos_secs: float, dur_secs: float):
        self.seek.set_position(frac)
        self.time_label.setText(f"{_fmt_time(pos_secs)} / {_fmt_time(dur_secs)}")

    def set_smart_hotkey_hint(self, hotkey_smart: str):
        pretty = pretty_hotkey(hotkey_smart) if hotkey_smart else ""
        self.btn_smart.setText(f"Read / Screen Grab ({pretty})" if pretty else "Read / Screen Grab")
        self.btn_smart.setToolTip(f"Same as pressing {pretty}" if pretty else "")

    def mark_user_moved(self):
        self._user_moved = True

    def _on_speed(self, val):
        speed = val / 10.0
        self.speed_label.setText(f"{speed:.1f}x")
        self.speed_changed.emit(speed)

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


def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"
