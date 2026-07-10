"""Playback with pause/resume/stop and live volume/speed, using a callback
OutputStream.

Kokoro's own synthesis speed (set in Settings > Voice) determines the
pitch/pacing of the audio it renders and is never touched here. The
popup's playback-speed control is a separate, purely post-hoc stretch:
a background thread runs the buffered audio through a WSOLA time-scale
modification (see tsm.py) as fast as it's produced, and the audio
callback just plays the (already speed-adjusted) result back at a flat
rate - so it stays pitch-correct instead of sounding like a chipmunk (or
a record played too slow) the way naive resampling would.

The stretch worker deliberately paces itself to stay only a fraction of
a second ahead of playback rather than eagerly processing everything at
once - otherwise a speed change made mid-playback would have nothing
left to apply to. WSOLA runs 100x+ faster than realtime (see tsm.py's
own benchmark), so this small a lead is still comfortable headroom.
"""

import threading
import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal

from .tsm import WsolaStretcher

_LEAD_SECONDS = 0.5   # how far ahead of playback the stretcher is allowed to get


class Player(QObject):
    finished = Signal()          # emitted when playback reaches the end naturally

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._stream = None
        self._base_samples = None     # raw audio as Kokoro produced it, growing via append()
        self._base_streaming = False  # True while more base chunks may still be appended
        self._out_samples = None      # speed-adjusted audio actually played
        self._out_pos = 0
        self._out_done = False        # True once no more stretched audio is coming
        self._sr = 24000
        self._paused = False
        self._volume = 1.0
        self._speed = 1.0
        self._worker = None
        self._worker_gen = 0          # bumped to make a stale worker thread exit

    def set_volume(self, vol: float):
        with self._lock:
            self._volume = max(0.0, min(1.0, float(vol)))

    def set_speed(self, speed: float):
        """Change the live playback speed. Applied by the stretch worker
        to whatever hasn't been processed yet - typically within
        _LEAD_SECONDS of the current playback position."""
        with self._lock:
            self._speed = max(0.1, float(speed))

    def play(self, samples, sample_rate: int, streaming: bool = False):
        """Start playback. If streaming=True, reaching the end of `samples`
        doesn't stop playback or fire `finished` - call append() with more
        audio as it becomes available, then finish_streaming() once there's
        no more coming."""
        self.stop()
        with self._lock:
            self._base_samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            self._base_streaming = streaming
            self._out_samples = np.zeros(0, dtype=np.float32)
            self._out_pos = 0
            self._out_done = False
            self._paused = False
            self._sr = int(sample_rate)
            self._worker_gen += 1
            my_gen = self._worker_gen
        self._worker = threading.Thread(target=self._stretch_worker, args=(my_gen,), daemon=True)
        self._worker.start()
        self._stream = sd.OutputStream(
            samplerate=self._sr, channels=1,
            callback=self._callback, finished_callback=self._on_finished,
        )
        self._stream.start()

    def append(self, samples):
        """Add more raw (not-yet-stretched) audio - used for chunked
        synthesis so playback can start on the first chunk while later
        ones are still being generated."""
        extra = np.asarray(samples, dtype=np.float32).reshape(-1)
        with self._lock:
            if self._base_samples is None:
                return
            self._base_samples = np.concatenate([self._base_samples, extra])

    def finish_streaming(self):
        """Call once no more base chunks are coming."""
        with self._lock:
            self._base_streaming = False

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
            return len(self._out_samples) / self._sr if self._out_samples is not None else 0.0

    def position_seconds(self) -> float:
        with self._lock:
            return self._out_pos / self._sr if self._out_samples is not None else 0.0

    def position_fraction(self) -> float:
        with self._lock:
            if self._out_samples is None or len(self._out_samples) == 0:
                return 0.0
            return self._out_pos / len(self._out_samples)

    def seek_fraction(self, frac: float):
        with self._lock:
            if self._out_samples is None:
                return
            frac = max(0.0, min(1.0, float(frac)))
            self._out_pos = int(frac * len(self._out_samples))

    def stop(self):
        with self._lock:
            self._worker_gen += 1   # tells any running worker thread to exit
        s = self._stream
        self._stream = None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass

    # --- background stretch worker ---
    def _stretch_worker(self, my_gen: int):
        stretcher = WsolaStretcher(self._sr)
        while True:
            with self._lock:
                if my_gen != self._worker_gen:
                    return
                base = self._base_samples
                base_done = not self._base_streaming
                speed = self._speed
                played = self._out_pos
                buffered = len(self._out_samples) if self._out_samples is not None else 0

            lead = (buffered - played) / self._sr
            if lead > _LEAD_SECONDS:
                time.sleep(0.05)
                continue

            out = stretcher.step(base, speed)
            if out is None:
                if base_done:
                    break
                time.sleep(0.01)
                continue
            if len(out):
                with self._lock:
                    if my_gen != self._worker_gen:
                        return
                    self._out_samples = np.concatenate([self._out_samples, out])

        tail = stretcher.flush()
        with self._lock:
            if my_gen != self._worker_gen:
                return
            if len(tail):
                self._out_samples = np.concatenate([self._out_samples, tail])
            self._out_done = True

    # --- audio thread ---
    def _callback(self, outdata, frames, time_info, status):
        with self._lock:
            if self._paused or self._out_samples is None:
                outdata.fill(0)
                return
            pos = self._out_pos
            end = pos + frames
            chunk = self._out_samples[pos:end]
            n = len(chunk)
            outdata[:n, 0] = chunk * self._volume
            if n < frames:
                outdata[n:, 0] = 0
                self._out_pos += n
                if self._out_done:
                    raise sd.CallbackStop()
                return   # more stretched audio may still be coming - wait
            self._out_pos = end

    def _on_finished(self):
        # Runs on a PortAudio thread; a queued Qt signal hops to the GUI thread.
        self.finished.emit()
