"""Frameless quick-controls popup shown at the cursor when the hotkey fires."""

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QSlider, QLabel, QFrame
)


class ControlPopup(QWidget):
    play_pause = Signal()
    stop = Signal()
    reread = Signal()
    speed_changed = Signal(float)     # 0.5 .. 2.0
    volume_changed = Signal(float)    # 0.0 .. 1.0

    def __init__(self, speed: float, volume: float):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setWindowTitle("Crier")

        card = QFrame(self)
        card.setObjectName("card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # Transport row
        row = QHBoxLayout()
        self.btn_play = QPushButton("Pause")
        self.btn_stop = QPushButton("Stop")
        self.btn_reread = QPushButton("Re-read")
        self.btn_hide = QPushButton("Hide")
        for b in (self.btn_play, self.btn_stop, self.btn_reread, self.btn_hide):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        root.addLayout(row)

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
        self.btn_play.clicked.connect(self.play_pause.emit)
        self.btn_stop.clicked.connect(self.stop.emit)
        self.btn_reread.clicked.connect(self.reread.emit)
        self.btn_hide.clicked.connect(self.hide)
        self.speed.valueChanged.connect(self._on_speed)
        self.volume.valueChanged.connect(self._on_volume)

        self.setStyleSheet(
            """
            #card { background: #1f2330; border: 1px solid #3a4054; border-radius: 12px; }
            QLabel { color: #c8cede; font-size: 12px; }
            QPushButton {
                background: #2c3244; color: #e8ecf6; border: 1px solid #3a4054;
                border-radius: 8px; padding: 6px 10px; font-size: 12px;
            }
            QPushButton:hover { background: #39415a; }
            QSlider::groove:horizontal { height: 4px; background: #3a4054; border-radius: 2px; }
            QSlider::handle:horizontal { width: 14px; margin: -6px 0; border-radius: 7px; background: #6ea8fe; }
            """
        )
        self.setFixedWidth(280)

    def set_playing(self, playing: bool):
        self.btn_play.setText("Pause" if playing else "Play")

    def _on_speed(self, val):
        self.speed_label.setText(f"{val / 100:.2f}x")
        self.speed_changed.emit(val / 100.0)

    def _on_volume(self, val):
        self.volume_label.setText(f"{val}%")
        self.volume_changed.emit(val / 100.0)

    def show_near_cursor(self):
        self.adjustSize()
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(pos.x() + 12, geo.right() - self.width() - 8)
        y = min(pos.y() + 12, geo.bottom() - self.height() - 8)
        self.move(QPoint(max(geo.left() + 8, x), max(geo.top() + 8, y)))
        self.show()
        self.raise_()
        self.activateWindow()
