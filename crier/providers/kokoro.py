"""Kokoro voice provider: a local, offline neural TTS model (CPU by default,
optional experimental DirectML)."""

import threading

from PySide6.QtWidgets import QComboBox, QCheckBox, QDoubleSpinBox, QFormLayout, QLabel, QWidget

from .. import config
from ..chunking import fade_edges, with_trailing_pause

PROVIDER_ID = "kokoro"
DISPLAY_NAME = "Kokoro (local, offline)"

# A curated subset with human-readable labels; Kokoro ships 50+. Users can
# still type any valid raw voice id if they know one that isn't listed here.
VOICE_LABELS = {
    "af_heart": "Heart (US Female)",
    "af_bella": "Bella (US Female)",
    "af_sarah": "Sarah (US Female)",
    "af_nicole": "Nicole (US Female)",
    "af_sky": "Sky (US Female)",
    "am_adam": "Adam (US Male)",
    "am_michael": "Michael (US Male)",
    "bf_emma": "Emma (UK Female)",
    "bf_isabella": "Isabella (UK Female)",
    "bm_george": "George (UK Male)",
    "bm_lewis": "Lewis (UK Male)",
}


class Engine:
    """Thin wrapper over kokoro-onnx."""

    def __init__(self, settings):
        self.settings = settings
        self.backend = "cpu"
        self._kokoro = None
        self._load_lock = threading.Lock()

    def load(self):
        """Load the model and run one warm-up synthesis using the current
        actual voice/speed/lang - kokoro-onnx builds some state lazily
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
            voice = self.settings.kokoro_voice
            speed = max(0.5, min(2.0, self.settings.kokoro_voice_speed))
            lang = self.settings.kokoro_lang

            if self.settings.kokoro_use_gpu and "DmlExecutionProvider" in onnxruntime.get_available_providers():
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

    def synthesize_chunk(self, text: str, pause_after: float = 0.0):
        """Synthesize one chunk. Returns (samples, sample_rate) with edge
        fades applied and pause_after seconds of trailing silence."""
        if self._kokoro is None:
            self.load()
        voice = self.settings.kokoro_voice
        speed = max(0.5, min(2.0, self.settings.kokoro_voice_speed))
        lang = self.settings.kokoro_lang
        samples, sr = self._kokoro.create(text, voice=voice, speed=speed, lang=lang)
        samples = fade_edges(samples, sr)
        samples = with_trailing_pause(samples, sr, pause_after)
        return samples, sr


class SettingsPanel(QWidget):
    """Kokoro-specific voice settings: voice, language, its own synthesis
    speed, and the GPU toggle. Kokoro's `create()` only exposes voice/
    speed/lang as tunables - no separate pitch/energy/etc. controls."""

    def __init__(self, settings):
        super().__init__()
        form = QFormLayout(self)
        form.setContentsMargins(0, 8, 0, 0)

        self.voice = QComboBox()
        self.voice.setEditable(True)
        for voice_id, label in VOICE_LABELS.items():
            self.voice.addItem(label, voice_id)
        if settings.kokoro_voice in VOICE_LABELS:
            self.voice.setCurrentText(VOICE_LABELS[settings.kokoro_voice])
        else:
            self.voice.addItem(settings.kokoro_voice, settings.kokoro_voice)
            self.voice.setCurrentText(settings.kokoro_voice)
        form.addRow("Voice", self.voice)

        self.lang = QComboBox()
        self.lang.addItems(["en-us", "en-gb"])
        self.lang.setCurrentText(settings.kokoro_lang)
        form.addRow("Language", self.lang)

        self.voice_speed = QDoubleSpinBox()
        self.voice_speed.setRange(0.5, 2.0)     # Kokoro's own hard limit
        self.voice_speed.setSingleStep(0.1)
        self.voice_speed.setDecimals(1)
        self.voice_speed.setSuffix("x")
        self.voice_speed.setValue(settings.kokoro_voice_speed)
        form.addRow("Voice speed", self.voice_speed)
        speed_hint = QLabel(
            "How Kokoro itself paces speech (0.5x-2.0x). This is separate from "
            "the popup's playback-speed control, which stretches whatever this "
            "produces rather than changing how it's synthesized."
        )
        speed_hint.setWordWrap(True)
        speed_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", speed_hint)

        self.use_gpu = QCheckBox("Try GPU (DirectML - experimental, falls back to CPU)")
        self.use_gpu.setChecked(settings.kokoro_use_gpu)
        form.addRow("", self.use_gpu)

    def apply_to_settings(self, settings):
        settings.kokoro_voice = self._voice_id()
        settings.kokoro_lang = self.lang.currentText()
        settings.kokoro_voice_speed = self.voice_speed.value()
        settings.kokoro_use_gpu = self.use_gpu.isChecked()

    def _voice_id(self) -> str:
        idx = self.voice.currentIndex()
        typed = self.voice.currentText().strip()
        if idx >= 0 and self.voice.itemText(idx) == typed:
            return self.voice.itemData(idx)  # a listed voice: use its real id
        return typed                          # custom text: treat as a raw voice id
