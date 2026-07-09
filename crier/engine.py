"""Grab the current selection from any app, and synthesize it with Kokoro."""

import time

import pyperclip
from pynput import keyboard

from . import config

_kbd = keyboard.Controller()
COPY_DELAY = 0.12


def grab_selection() -> str:
    """Copy whatever is selected in the foreground app, then restore the clipboard."""
    try:
        saved = pyperclip.paste()
    except Exception:
        saved = ""

    pyperclip.copy("")                      # sentinel to detect "nothing selected"
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

    def synthesize(self, text: str, voice: str, speed: float, lang: str):
        """Return (samples: np.float32 mono, sample_rate: int)."""
        if self._kokoro is None:
            self.load()
        return self._kokoro.create(text, voice=voice, speed=speed, lang=lang)
