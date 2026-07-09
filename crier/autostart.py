"""Enable/disable 'start at login' via the Windows Run registry key. No-op elsewhere."""

import sys
from pathlib import Path

from . import config

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command() -> str:
    # Frozen (PyInstaller) -> the exe itself. Dev -> pythonw -m crier (no console window).
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    return f'"{pythonw}" -m crier'


def set_autostart(enabled: bool):
    if sys.platform != "win32":
        return
    try:
        import winreg
    except ImportError:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, config.APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, config.APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass
