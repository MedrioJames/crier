"""Grab the current selection from any app, and synthesize it with Kokoro."""

import re
import time

import numpy as np
import pyperclip
from pynput import keyboard

from . import config

_kbd = keyboard.Controller()
COPY_DELAY = 0.12

_SENTENCE_GAP_SECONDS = 0.28   # pause between sentences within the same line
_LINE_GAP_SECONDS = 0.65       # pause between lines/paragraphs (e.g. a title -> body)
_FADE_SECONDS = 0.02           # short edge fade on every chunk so splices don't click

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

    def load(self):
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
                self._kokoro.create("warm up", voice="af_heart", speed=1.0, lang="en-us")
                self.backend = "directml"
                return
            except Exception as e:
                print(f"[crier] GPU path failed ({type(e).__name__}: {e}); using CPU")

        self._kokoro = Kokoro(model, voices)
        self.backend = "cpu"

    def split_into_chunks(self, text: str):
        """Break text into small speakable chunks (roughly one sentence
        each) paired with the silence to insert after each one: a short
        gap between sentences, a longer one between lines/paragraphs -
        Kokoro's phonemizer treats a bare newline as just whitespace, so a
        title followed by a paragraph would otherwise run together with no
        pause at all. Small chunks also mean the caller can start playing
        the first one almost immediately instead of waiting for the whole
        text to synthesize."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        chunks = []
        for li, line in enumerate(lines):
            sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(line) if s.strip()] or [line]
            for si, sentence in enumerate(sentences):
                last_in_line = si == len(sentences) - 1
                last_line = li == len(lines) - 1
                if last_in_line and last_line:
                    pause = 0.0
                elif last_in_line:
                    pause = _LINE_GAP_SECONDS
                else:
                    pause = _SENTENCE_GAP_SECONDS
                chunks.append((sentence, pause))
        return chunks

    def synthesize_chunk(self, text: str, voice: str, speed: float, lang: str, pause_after: float = 0.0):
        """Synthesize one chunk. Returns (samples, sample_rate) with edge
        fades applied and pause_after seconds of trailing silence."""
        if self._kokoro is None:
            self.load()
        samples, sr = self._kokoro.create(text, voice=voice, speed=speed, lang=lang)
        samples = _fade_edges(samples, sr)
        if pause_after > 0:
            gap = np.zeros(int(pause_after * sr), dtype=np.float32)
            samples = np.concatenate([samples, gap])
        return samples, sr
