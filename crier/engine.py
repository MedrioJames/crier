"""Grab the current selection from any app, and synthesize it with Kokoro."""

import re
import threading
import time

import numpy as np
import pyperclip
from pynput import keyboard

from . import config

_kbd = keyboard.Controller()
COPY_DELAY = 0.12

_LINE_GAP_SECONDS = 0.9        # pause between lines/paragraphs (e.g. a title -> body)
_GROUP_GAP_SECONDS = 0.12      # small gap only where a long paragraph had to be split for streaming
_FADE_SECONDS = 0.02           # short edge fade on every chunk so splices don't click
_MAX_CHUNK_CHARS = 220         # group consecutive sentences up to roughly this size per chunk

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


_MODIFIERS = (
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.cmd,
)


def grab_selection() -> str:
    """Copy whatever is selected in the foreground app, then restore the clipboard."""
    try:
        saved = pyperclip.paste()
    except Exception:
        saved = ""

    pyperclip.copy("")                      # sentinel to detect "nothing selected"

    # If we were triggered by a hotkey (e.g. Ctrl+Alt+R), Alt is almost
    # certainly still physically held at this point - human key-release
    # reaction time is much slower than this callback firing. Sending our
    # own Ctrl+C on top of a held Alt becomes Ctrl+Alt+C, which isn't bound
    # to Copy in virtually any app, so nothing gets copied.
    for key in _MODIFIERS:
        try:
            _kbd.release(key)
        except Exception:
            pass
    time.sleep(0.05)

    _kbd.press(keyboard.Key.ctrl)
    _kbd.press("c")
    _kbd.release("c")
    _kbd.release(keyboard.Key.ctrl)
    time.sleep(COPY_DELAY)

    try:
        text = pyperclip.paste()
    except Exception:
        text = ""

    try:
        pyperclip.copy(saved)
    except Exception:
        pass

    return (text or "").strip()


def _fade_edges(samples: np.ndarray, sr: int) -> np.ndarray:
    """A short linear ramp in/out at the very start/end of a chunk. Splicing
    raw neural-TTS output directly against silence (or another chunk) tends
    to click, since the waveform rarely crosses zero exactly at the cut."""
    n = int(_FADE_SECONDS * sr)
    if n <= 0 or len(samples) < 2 * n:
        return samples
    samples = samples.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    samples[:n] *= ramp
    samples[-n:] *= ramp[::-1]
    return samples


class Engine:
    """Thin wrapper over kokoro-onnx. CPU by default; optional experimental DirectML."""

    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu
        self.backend = "cpu"
        self._kokoro = None
        self._load_lock = threading.Lock()

    def load(self, voice: str = "af_heart", speed: float = 1.0, lang: str = "en-us"):
        """Load the model and run one warm-up synthesis. Pass the caller's
        actual current voice/speed/lang (App does) rather than leaving this
        on the hardcoded defaults - kokoro-onnx builds some state lazily
        per-voice, so warming up with a voice the user isn't using doesn't
        fully prime their first real read."""
        # Guards against loading twice if a proactive background warm-up
        # (see App.start()) and a real synthesis request race each other.
        with self._load_lock:
            if self._kokoro is not None:
                return

            import onnxruntime
            from kokoro_onnx import Kokoro

            model, voices = config.model_paths()
            model, voices = str(model), str(voices)

            if self.use_gpu and "DmlExecutionProvider" in onnxruntime.get_available_providers():
                try:
                    opts = onnxruntime.SessionOptions()
                    opts.enable_mem_pattern = False
                    opts.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
                    session = onnxruntime.InferenceSession(
                        model, sess_options=opts,
                        providers=["DmlExecutionProvider", "CPUExecutionProvider"],
                    )
                    self._kokoro = Kokoro.from_session(session, voices)
                    self._kokoro.create("warm up", voice=voice, speed=speed, lang=lang)
                    self.backend = "directml"
                    return
                except Exception as e:
                    print(f"[crier] GPU path failed ({type(e).__name__}: {e}); using CPU")

            self._kokoro = Kokoro(model, voices)
            self.backend = "cpu"
            # The CPU path skipped this warm-up call before - meaning the
            # model-load + phonemizer-init cost (~1-2s) landed on whatever
            # the user's first Read Selection happened to be. App.start()
            # calls load() in the background right after launch so this
            # already happened by the time they actually use the hotkey.
            self._kokoro.create("warm up", voice=voice, speed=speed, lang=lang)

    def split_into_chunks(self, text: str):
        """Break text into speakable chunks paired with the silence to
        insert after each one.

        Consecutive sentences within the same line are grouped together
        (up to ~_MAX_CHUNK_CHARS) rather than split one-per-chunk: handing
        Kokoro several sentences at once lets it carry natural connected
        prosody across them, whereas synthesizing every sentence in total
        isolation made each one sound like the start of a new paragraph -
        losing the actual distinction between "mid-paragraph" and "new
        paragraph". A run-on paragraph with no line breaks still gets cut
        into a few chunks (for a reasonably fast time-to-first-audio), just
        with a much smaller, near-inaudible gap between those pieces than
        the real pause used between lines/paragraphs.
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        chunks = []
        for li, line in enumerate(lines):
            sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(line) if s.strip()] or [line]

            groups = []
            current, current_len = [], 0
            for sentence in sentences:
                if current and current_len + len(sentence) > _MAX_CHUNK_CHARS:
                    groups.append(" ".join(current))
                    current, current_len = [], 0
                current.append(sentence)
                current_len += len(sentence) + 1
            if current:
                groups.append(" ".join(current))

            last_line = li == len(lines) - 1
            for gi, group in enumerate(groups):
                last_group_in_line = gi == len(groups) - 1
                if last_group_in_line and last_line:
                    pause = 0.0
                elif last_group_in_line:
                    pause = _LINE_GAP_SECONDS
                else:
                    pause = _GROUP_GAP_SECONDS
                chunks.append((group, pause))
        return chunks

    def synthesize_chunk(self, text: str, voice: str, speed: float, lang: str, pause_after: float = 0.0):
        """Synthesize one chunk. Returns (samples, sample_rate) with edge
        fades applied and pause_after seconds of trailing silence."""
        if self._kokoro is None:
            self.load(voice, speed, lang)
        samples, sr = self._kokoro.create(text, voice=voice, speed=speed, lang=lang)
        samples = _fade_edges(samples, sr)
        if pause_after > 0:
            gap = np.zeros(int(pause_after * sr), dtype=np.float32)
            samples = np.concatenate([samples, gap])
        return samples, sr
