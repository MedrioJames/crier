"""Playback with pause/resume/stop and live volume, using a callback OutputStream."""

import threading

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal


class Player(QObject):
    finished = Signal()          # emitted when playback reaches the end naturally

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._stream = None
        self._samples = None
        self._pos = 0
        self._sr = 24000
        self._paused = False
        self._volume = 1.0

    def set_volume(self, vol: float):
        with self._lock:
            self._volume = max(0.0, min(1.0, float(vol)))

    def play(self, samples, sample_rate: int):
        self.stop()
        with self._lock:
            self._samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            self._sr = int(sample_rate)
            self._pos = 0
            self._paused = False
        self._stream = sd.OutputStream(
            samplerate=self._sr, channels=1,
            callback=self._callback, finished_callback=self._on_finished,
        )
        self._stream.start()

    def toggle_pause(self):
        with self._lock:
            if self._samples is None:
                return
            self._paused = not self._paused

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active

    def duration_seconds(self) -> float:
        with self._lock:
            return len(self._samples) / self._sr if self._samples is not None else 0.0

    def position_seconds(self) -> float:
        with self._lock:
            return self._pos / self._sr if self._samples is not None else 0.0

    def position_fraction(self) -> float:
        with self._lock:
            if self._samples is None or len(self._samples) == 0:
                return 0.0
            return self._pos / len(self._samples)

    def seek_fraction(self, frac: float):
        with self._lock:
            if self._samples is None:
                return
            frac = max(0.0, min(1.0, float(frac)))
            self._pos = int(frac * len(self._samples))

    def stop(self):
        s = self._stream
        self._stream = None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    # --- audio thread ---
    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            if self._paused or self._samples is None:
                outdata.fill(0)
                return
            end = self._pos + frames
            chunk = self._samples[self._pos:end]
            n = len(chunk)
            outdata[:n, 0] = chunk * self._volume
            if n < frames:
                outdata[n:, 0] = 0
                raise sd.CallbackStop()
            self._pos = end

    def _on_finished(self):
        # Runs on a PortAudio thread; a queued Qt signal hops to the GUI thread.
        self.finished.emit()
