"""Check GitHub releases for a newer version and optionally run its installer."""

import os
import re
import tempfile
import threading

import requests
from PySide6.QtCore import QObject, Signal, QProcess
from PySide6.QtWidgets import QMessageBox

from . import config, __version__


def _to_tuple(v: str):
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums) if nums else (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _to_tuple(latest) > _to_tuple(current)


class _CheckWorker(QObject):
    result = Signal(bool, str, str)   # update_available, latest_tag, asset_url

    def run(self):
        try:
            url = f"https://api.github.com/repos/{config.REPO}/releases/latest"
            r = requests.get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
            r.raise_for_status()
            data = r.json()
            tag = data.get("tag_name", "")
            asset_url = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if name.endswith(".exe"):        # the Inno Setup installer
                    asset_url = asset.get("browser_download_url", "")
                    break
            self.result.emit(_is_newer(tag, __version__), tag, asset_url)
        except Exception:
            self.result.emit(False, "", "")


class Updater(QObject):
    """check(silent): silent=True suppresses the 'you're up to date' message."""

    def __init__(self, parent_widget=None):
        super().__init__()
        self._parent = parent_widget
        self._worker = _CheckWorker()
        self._worker.result.connect(self._on_result)
        self._silent = True

    def check(self, silent: bool = True):
        self._silent = silent
        threading.Thread(target=self._worker.run, daemon=True).start()

    def _on_result(self, available: bool, tag: str, asset_url: str):
        if not available:
            if not self._silent:
                QMessageBox.information(self._parent, "Crier", "You're on the latest version.")
            return
        msg = QMessageBox(self._parent)
        msg.setWindowTitle("Crier - update available")
        msg.setText(f"Crier {tag} is available (you have {__version__}).\nUpdate now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            return
        if asset_url:
            self._download_and_run(asset_url)
        else:
            # No installer asset on the release; open the releases page instead.
            QProcess.startDetached("cmd", ["/c", "start", "",
                                            f"https://github.com/{config.REPO}/releases/latest"])

    def _download_and_run(self, asset_url: str):
        try:
            dest = os.path.join(tempfile.gettempdir(), "Crier-Setup.exe")
            with requests.get(asset_url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        if chunk:
                            fh.write(chunk)
            # Launch the installer and quit so it can replace files.
            QProcess.startDetached(dest, [])
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self._parent, "Crier", f"Update failed:\n{e}")
