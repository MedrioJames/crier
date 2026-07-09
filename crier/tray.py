"""Tray (notification-area) icon and its menu."""

from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, Signal, QObject

from . import config


def _fallback_icon() -> QIcon:
    """Draw a simple speech-bubble glyph if no .ico ships with the build."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#6ea8fe"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(6, 8, 52, 38, 12, 12)
    p.drawPolygon([__import__("PySide6").QtCore.QPoint(x, y) for x, y in [(20, 44), (20, 58), (34, 44)]])
    p.setPen(QColor("#12141c"))
    f = QFont()
    f.setBold(True)
    f.setPointSize(22)
    p.setFont(f)
    p.drawText(pm.rect().adjusted(0, -6, 0, -12), Qt.AlignCenter, "C")
    p.end()
    return QIcon(pm)


class Tray(QObject):
    show_controls = Signal()
    open_settings = Signal()
    check_updates = Signal()
    quit_app = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        path = config.icon_path()
        icon = QIcon(path) if path else _fallback_icon()

        self.tray = QSystemTrayIcon(icon, parent)
        self.tray.setToolTip(config.APP_NAME)

        menu = QMenu()
        act_show = QAction("Show controls", menu)
        act_settings = QAction("Settings...", menu)
        act_update = QAction("Check for updates", menu)
        act_quit = QAction("Quit Crier", menu)
        for a in (act_show, act_settings, act_update):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)

        act_show.triggered.connect(self.show_controls.emit)
        act_settings.triggered.connect(self.open_settings.emit)
        act_update.triggered.connect(self.check_updates.emit)
        act_quit.triggered.connect(self.quit_app.emit)

        # Left-click the tray icon -> show controls.
        self.tray.activated.connect(self._on_activated)

        self.tray.setContextMenu(menu)
        self._menu = menu

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:      # left click
            self.show_controls.emit()

    def show(self):
        self.tray.show()

    def notify(self, title, message):
        self.tray.showMessage(title, message)
