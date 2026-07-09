"""Download the Kokoro model + voices on first run, with a progress dialog."""

import threading

import requests
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QProgressDialog, QMessageBox

from . import config


class _Worker(QObject):
    progress = Signal(int, int)      # bytes_done, bytes_total (per file, summed)
    done = Signal(bool, str)         # ok, error_message

    def __init__(self, jobs):
        super().__init__()
        self._jobs = jobs            # list of (url, dest_path)

    def run(self):
        try:
            # First, sum content lengths so the bar is meaningful.
            total = 0
            sizes = []
            for url, _ in self._jobs:
                r = requests.head(url, allow_redirects=True, timeout=30)
                size = int(r.headers.get("Content-Length", 0))
                sizes.append(size)
                total += size

            done = 0
            for (url, dest), _size in zip(self._jobs, sizes):
                with requests.get(url, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    with open(dest, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=1 << 16):
                            if chunk:
                                fh.write(chunk)
                                done += len(chunk)
                                self.progress.emit(done, total or 1)
            self.done.emit(True, "")
        except Exception as e:
            self.done.emit(False, f"{type(e).__name__}: {e}")


def ensure_models(parent=None) -> bool:
    """Return True if both model files are present (downloading them if needed)."""
    model, voices = config.model_paths()
    jobs = []
    if not model.exists():
        jobs.append((config.MODEL_URL, model))
    if not voices.exists():
        jobs.append((config.VOICES_URL, voices))
    if not jobs:
        return True

    dlg = QProgressDialog("Downloading voice model (first run only)...", "Cancel", 0, 100, parent)
    dlg.setWindowTitle("Crier - setup")
    dlg.setWindowModality(Qt.ApplicationModal)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)

    result = {"ok": False, "err": ""}
    worker = _Worker(jobs)

    def on_progress(d, t):
        dlg.setValue(int(d * 100 / t))

    def on_done(ok, err):
        result["ok"] = ok
        result["err"] = err
        dlg.reset()

    worker.progress.connect(on_progress)
    worker.done.connect(on_done)

    t = threading.Thread(target=worker.run, daemon=True)
    t.start()
    dlg.exec()  # modal; returns when reset() is called or user cancels

    if not result["ok"]:
        # Clean up any partial files so a retry starts fresh.
        for _, dest in jobs:
            try:
                if dest.exists() and dest.stat().st_size == 0:
                    dest.unlink()
            except Exception:
                pass
        if result["err"]:
            QMessageBox.critical(parent, "Crier", f"Could not download the voice model:\n{result['err']}")
        return False
    return True
