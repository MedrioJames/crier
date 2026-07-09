"""Check the git remote for new commits and pull them in, then restart.

Crier runs from a plain git checkout (no installer/frozen exe), so
"updating" just means pulling origin/main and relaunching - no download,
no unsigned installer for SmartScreen to block.
"""

import os
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Signal, QProcess
from PySide6.QtWidgets import QMessageBox

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Suppress the console window git.exe would otherwise briefly flash on Windows.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _git(*args, timeout=30):
    return subprocess.run(
        ["git", *args], cwd=REPO_DIR, capture_output=True, text=True,
        timeout=timeout, creationflags=_NO_WINDOW,
    )


class _CheckWorker(QObject):
    result = Signal(bool, str)   # update_available, summary (short log or error)

    def run(self):
        try:
            fetch = _git("fetch", "origin", "main")
            if fetch.returncode != 0:
                self.result.emit(False, fetch.stderr.strip())
                return
            local = _git("rev-parse", "HEAD").stdout.strip()
            remote = _git("rev-parse", "origin/main").stdout.strip()
            if not local or not remote or local == remote:
                self.result.emit(False, "")
                return
            log = _git("log", "--oneline", f"{local}..{remote}").stdout.strip()
            self.result.emit(True, log or remote[:7])
        except Exception as e:
            self.result.emit(False, f"{type(e).__name__}: {e}")


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

    def _on_result(self, available: bool, summary: str):
        if not available:
            if not self._silent:
                if summary:
                    QMessageBox.warning(self._parent, "Crier", f"Couldn't check for updates:\n{summary}")
                else:
                    QMessageBox.information(self._parent, "Crier", "You're on the latest version.")
            return
        msg = QMessageBox(self._parent)
        msg.setWindowTitle("Crier - update available")
        msg.setText(f"An update is available:\n\n{summary}\n\nPull it in and restart now?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec() != QMessageBox.Yes:
            return
        self._pull_and_restart()

    def _pull_and_restart(self):
        pull = _git("pull", "--ff-only", "origin", "main", timeout=60)
        if pull.returncode != 0:
            QMessageBox.critical(self._parent, "Crier", f"Update failed:\n{pull.stderr}")
            return
        try:
            pip = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=REPO_DIR, capture_output=True, text=True, timeout=300,
                creationflags=_NO_WINDOW,
            )
            if pip.returncode != 0:
                QMessageBox.critical(self._parent, "Crier", f"Dependency update failed:\n{pip.stderr}")
                return
        except Exception as e:
            QMessageBox.critical(self._parent, "Crier", f"Dependency update failed:\n{e}")
            return

        # sys.executable is pythonw.exe (that's what launched this process).
        QProcess.startDetached(sys.executable, ["-m", "crier"], REPO_DIR)
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
