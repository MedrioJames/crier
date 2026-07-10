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
    def voice_speed(self) -> float:
        """Kokoro's own synthesis speed (0.5-2.0, its hard limit) - a
        voice-quality setting, edited in Settings > Voice. Independent of
        the popup's playback_speed."""
        return float(self._s.value("voice_speed", 1.0))

    @voice_speed.setter
    def voice_speed(self, v: float):
        self._s.setValue("voice_speed", float(v))

    @property
    def playback_speed(self) -> float:
        """The popup's live playback-rate control. Applied by stretching
        whatever Kokoro already produced (pitch-preserved), never by
        changing how Kokoro synthesizes - so it can go beyond 2.0x."""
        return float(self._s.value("playback_speed", 1.0))

    @playback_speed.setter
    def playback_speed(self, v: float):
        self._s.setValue("playback_speed", float(v))

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

    # --- voice provider (groundwork for future non-Kokoro voice modules) ---
    @property
    def voice_provider(self) -> str:
        return self._s.value("voice_provider", "kokoro", str)

    @voice_provider.setter
    def voice_provider(self, v: str):
        self._s.setValue("voice_provider", v)

    # --- hotkeys (pynput GlobalHotKeys syntax) ---
    @property
    def hotkey_read(self) -> str:
        return self._s.value("hotkey_read", "<ctrl>+<alt>+r", str)

    @hotkey_read.setter
    def hotkey_read(self, v: str):
        self._s.setValue("hotkey_read", v)

    @property
    def hotkey_stop(self) -> str:
        return self._s.value("hotkey_stop", "<ctrl>+<alt>+x", str)

    @hotkey_stop.setter
    def hotkey_stop(self, v: str):
        self._s.setValue("hotkey_stop", v)

    @property
    def hotkey_grab(self) -> str:
        return self._s.value("hotkey_grab", "<ctrl>+<alt>+c", str)

    @hotkey_grab.setter
    def hotkey_grab(self, v: str):
        self._s.setValue("hotkey_grab", v)

    @property
    def hotkey_smart(self) -> str:
        return self._s.value("hotkey_smart", "<ctrl>+<alt>+s", str)

    @hotkey_smart.setter
    def hotkey_smart(self, v: str):
        self._s.setValue("hotkey_smart", v)

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
