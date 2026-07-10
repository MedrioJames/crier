"""Playback with pause/resume/stop and live volume/speed, using a callback
OutputStream.

Speed is split into two parts: `synth_speed` (whatever rate Kokoro actually
rendered the current audio at - it hard-caps this to 0.5-2.0) and the
user's live `desired_speed`, which can be anything. The playback callback
steps through the buffered samples at `desired_speed / synth_speed` per
output frame, so moving the speed slider takes effect on the very next
audio callback - no resynthesis, and no cap at 2x since the extra stretch
beyond what Kokoro rendered happens here.
"""

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
        self._base_samples = None
        self._base_pos = 0.0      # float index into _base_samples
        self._sr = 24000
        self._paused = False
        self._volume = 1.0
        self._synth_speed = 1.0   # rate the currently-loaded audio was synthesized at
        self._desired_speed = 1.0  # rate the user actually wants right now
        self._streaming = False   # True while more chunks may still be appended

    def set_volume(self, vol: float):
        with self._lock:
            self._volume = max(0.0, min(1.0, float(vol)))

    def set_speed(self, speed: float):
        """Change the live playback rate - applied on the next audio
        callback, whether or not something is currently playing."""
        with self._lock:
            self._desired_speed = max(0.1, float(speed))

    def play(self, samples, sample_rate: int, streaming: bool = False, synth_speed: float = 1.0):
        """Start playback. If streaming=True, reaching the end of `samples`
        doesn't stop playback or fire `finished` - call append() with more
        audio as it becomes available, then finish_streaming() once there's
        no more coming. `synth_speed` is the rate this audio was actually
        synthesized at, so the live speed control knows the baseline to
        scale from."""
        self.stop()
        with self._lock:
            self._base_samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            self._sr = int(sample_rate)
            self._base_pos = 0.0
            self._paused = False
            self._streaming = streaming
            self._synth_speed = max(0.1, float(synth_speed))
        self._stream = sd.OutputStream(
            samplerate=self._sr, channels=1,
            callback=self._callback, finished_callback=self._on_finished,
        )
        self._stream.start()

    def append(self, samples):
        """Add more audio to the end of the currently playing buffer -
        used for chunked synthesis so playback can start on the first
        chunk while later ones are still being generated."""
        extra = np.asarray(samples, dtype=np.float32).reshape(-1)
        with self._lock:
            if self._base_samples is None:
                return
            self._base_samples = np.concatenate([self._base_samples, extra])

    def finish_streaming(self):
        """Call once no more chunks are coming, so running out of buffered
        audio now means actually done (fires `finished`) instead of "wait
        for more"."""
        with self._lock:
            self._streaming = False

    def toggle_pause(self):
        with self._lock:
            if self._base_samples is None:
                return
            self._paused = not self._paused

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active

    def duration_seconds(self) -> float:
        with self._lock:
            return len(self._base_samples) / self._sr if self._base_samples is not None else 0.0

    def position_seconds(self) -> float:
        with self._lock:
            return self._base_pos / self._sr if self._base_samples is not None else 0.0

    def position_fraction(self) -> float:
        with self._lock:
            if self._base_samples is None or len(self._base_samples) == 0:
                return 0.0
            return self._base_pos / len(self._base_samples)

    def seek_fraction(self, frac: float):
        with self._lock:
            if self._base_samples is None:
                return
            frac = max(0.0, min(1.0, float(frac)))
            self._base_pos = frac * len(self._base_samples)

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
            if self._paused or self._base_samples is None:
                outdata.fill(0)
                return
            base = self._base_samples
            n_base = len(base)
            start = self._base_pos
            ratio = self._desired_speed / self._synth_speed

            if start >= n_base:
                outdata.fill(0)
                if not self._streaming:
                    raise sd.CallbackStop()
                return

            if ratio == 1.0:
                # Fast path: identical to plain unscaled playback - no
                # interpolation, so speed=synth_speed (the common case)
                # sounds exactly as before.
                pos = int(start)
                end = pos + frames
                chunk = base[pos:end]
                n = len(chunk)
                outdata[:n, 0] = chunk * self._volume
                if n < frames:
                    outdata[n:, 0] = 0
                    self._base_pos = end
                    if not self._streaming:
                        raise sd.CallbackStop()
                    return
                self._base_pos = end
                return

            idx = start + np.arange(frames, dtype=np.float64) * ratio
            lo = max(0, int(start))
            hi = min(n_base, int(np.ceil(start + frames * ratio)) + 2)
            window = base[lo:hi]
            if len(window) < 2:
                outdata.fill(0)
                self._base_pos = n_base
                if not self._streaming:
                    raise sd.CallbackStop()
                return

            local_idx = np.clip(idx - lo, 0, len(window) - 1)
            out = np.interp(local_idx, np.arange(len(window)), window).astype(np.float32)

            n_valid = frames if idx[-1] < n_base else int(np.searchsorted(idx, n_base))
            outdata[:n_valid, 0] = out[:n_valid] * self._volume
            if n_valid < frames:
                outdata[n_valid:, 0] = 0
                self._base_pos = n_base
                if not self._streaming:
                    raise sd.CallbackStop()
                return
            self._base_pos = start + frames * ratio

    def _on_finished(self):
        # Runs on a PortAudio thread; a queued Qt signal hops to the GUI thread.
        self.finished.emit()
