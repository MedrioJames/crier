"""OpenAI voice provider: cloud TTS via the /v1/audio/speech REST endpoint,
using gpt-4o-mini-tts (cheaper per-character than ElevenLabs, and supports a
free-text "tone"/style instruction unlike OpenAI's older tts-1 models).

Uses `requests` directly rather than the `openai` SDK - one HTTP call, no
extra dependency (the project already depends on requests for self-update
checks and model downloads).
"""

import numpy as np
import requests
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QWidget

from ..chunking import fade_edges, with_trailing_pause

PROVIDER_ID = "openai"
DISPLAY_NAME = "OpenAI (cloud, gpt-4o-mini-tts)"

_API_URL = "https://api.openai.com/v1/audio/speech"
_MODEL = "gpt-4o-mini-tts"
_SAMPLE_RATE = 24000   # OpenAI's documented rate for response_format="pcm"

VOICES = ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"]


class Engine:
    """Talks to OpenAI's hosted TTS model. Nothing to "load" locally - each
    chunk is one HTTP request - so load() just checks an API key is set."""

    def __init__(self, settings):
        self.settings = settings
        self.backend = "openai"

    def load(self):
        if not self.settings.openai_api_key.strip():
            raise RuntimeError("No OpenAI API key set - add one in Settings > Voice.")

    def synthesize_chunk(self, text: str, pause_after: float = 0.0):
        api_key = self.settings.openai_api_key.strip()
        if not api_key:
            raise RuntimeError("No OpenAI API key set - add one in Settings > Voice.")

        payload = {
            "model": _MODEL,
            "voice": self.settings.openai_voice,
            "input": text,
            "response_format": "pcm",
            "speed": max(0.25, min(4.0, self.settings.openai_speed)),
        }
        tone = self.settings.openai_tone.strip()
        if tone:
            payload["instructions"] = tone

        resp = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()

        # "pcm" is raw 16-bit signed little-endian mono samples, no header.
        samples = np.frombuffer(resp.content, dtype="<i2").astype(np.float32) / 32768.0
        samples = fade_edges(samples, _SAMPLE_RATE)
        samples = with_trailing_pause(samples, _SAMPLE_RATE, pause_after)
        return samples, _SAMPLE_RATE


class SettingsPanel(QWidget):
    def __init__(self, settings):
        super().__init__()
        form = QFormLayout(self)
        form.setContentsMargins(0, 8, 0, 0)

        self.api_key = QLineEdit(settings.openai_api_key)
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("sk-...")
        form.addRow("API key", self.api_key)
        key_hint = QLabel(
            "From platform.openai.com/api-keys. Stored locally in this PC's settings; "
            "sent only to OpenAI's API, never anywhere else."
        )
        key_hint.setWordWrap(True)
        key_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", key_hint)

        self.voice = QComboBox()
        self.voice.setEditable(True)
        self.voice.addItems(VOICES)
        if settings.openai_voice not in VOICES:
            self.voice.addItem(settings.openai_voice)
        self.voice.setCurrentText(settings.openai_voice)
        form.addRow("Voice", self.voice)

        self.tone = QLineEdit(settings.openai_tone)
        self.tone.setPlaceholderText('e.g. "calm and professional" (optional)')
        form.addRow("Tone", self.tone)

        self.voice_speed = QDoubleSpinBox()
        self.voice_speed.setRange(0.25, 4.0)
        self.voice_speed.setSingleStep(0.1)
        self.voice_speed.setDecimals(2)
        self.voice_speed.setSuffix("x")
        self.voice_speed.setValue(settings.openai_speed)
        form.addRow("Voice speed", self.voice_speed)
        speed_hint = QLabel(
            "How OpenAI itself paces speech. Separate from the popup's playback-speed "
            "control, which stretches whatever this produces rather than changing how "
            "it's synthesized."
        )
        speed_hint.setWordWrap(True)
        speed_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", speed_hint)

        cost_hint = QLabel(
            "This provider sends your text to OpenAI's API and bills your OpenAI "
            "account per character - unlike Kokoro, it isn't free or offline."
        )
        cost_hint.setWordWrap(True)
        cost_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", cost_hint)

    def apply_to_settings(self, settings):
        settings.openai_api_key = self.api_key.text().strip()
        settings.openai_voice = self.voice.currentText().strip()
        settings.openai_tone = self.tone.text().strip()
        settings.openai_speed = self.voice_speed.value()
