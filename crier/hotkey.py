"""Global hotkeys via pynput, re-emitted as Qt signals on the GUI thread."""

from pynput import keyboard
from PySide6.QtCore import QObject, Signal


class HotkeyManager(QObject):
    read_triggered = Signal()
    stop_triggered = Signal()

    def __init__(self, read_combo: str, stop_combo: str):
        super().__init__()
        self._read = read_combo
        self._stop = stop_combo
        self._listener = None

    def start(self):
        self.stop()
        # GlobalHotKeys callbacks run on pynput's own thread; emitting a Qt
        # signal is the thread-safe way to hop back to the GUI thread.
        self._listener = keyboard.GlobalHotKeys({
            self._read: self.read_triggered.emit,
            self._stop: self.stop_triggered.emit,
        })
        self._listener.start()

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def rebind(self, read_combo: str, stop_combo: str):
        self._read = read_combo
        self._stop = stop_combo
        self.start()
