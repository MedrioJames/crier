"""Persistent settings, backed by QSettings (writes to the registry on Windows)."""

from PySide6.QtCore import QSettings

from . import config


def _b(v, default):
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self):
        self._s = QSettings(config.ORG_NAME, config.APP_NAME)

    # --- voice / audio ---
    @property
    def voice(self) -> str:
        return self._s.value("voice", "af_heart", str)

    @voice.setter
    def voice(self, v: str):
        self._s.setValue("voice", v)

    @property
    def lang(self) -> str:
        return self._s.value("lang", "en-us", str)

    @lang.setter
    def lang(self, v: str):
        self._s.setValue("lang", v)

    @property
    def speed(self) -> float:
        return float(self._s.value("speed", 1.0))

    @speed.setter
    def speed(self, v: float):
        self._s.setValue("speed", float(v))

    @property
    def volume(self) -> float:
        return float(self._s.value("volume", 1.0))

    @volume.setter
    def volume(self, v: float):
        self._s.setValue("volume", float(v))

    @property
    def use_gpu(self) -> bool:
        return _b(self._s.value("use_gpu", False), False)

    @use_gpu.setter
    def use_gpu(self, v: bool):
        self._s.setValue("use_gpu", bool(v))

    # --- hotkeys (pynput GlobalHotKeys syntax) ---
    @property
    def hotkey_read(self) -> str:
        return self._s.value("hotkey_read", "<ctrl>+<alt>+r", str)

    @hotkey_read.setter
    def hotkey_read(self, v: str):
        self._s.setValue("hotkey_read", v)

    @property
    def hotkey_stop(self) -> str:
        return self._s.value("hotkey_stop", "<ctrl>+<alt>+s", str)

    @hotkey_stop.setter
    def hotkey_stop(self, v: str):
        self._s.setValue("hotkey_stop", v)

    # --- behaviour ---
    @property
    def auto_update(self) -> bool:
        return _b(self._s.value("auto_update", True), True)

    @auto_update.setter
    def auto_update(self, v: bool):
        self._s.setValue("auto_update", bool(v))

    @property
    def autostart(self) -> bool:
        return _b(self._s.value("autostart", False), False)

    @autostart.setter
    def autostart(self, v: bool):
        self._s.setValue("autostart", bool(v))
