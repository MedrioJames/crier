"""Settings dialog reachable from the tray menu."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QCheckBox, QDoubleSpinBox,
    QDialogButtonBox, QLabel, QVBoxLayout, QWidget, QTabWidget
)

from .hotkey_capture import HotkeyEdit

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

# Voice providers this build knows how to render with. Only Kokoro exists
# today - this is the seam for future non-Kokoro voice modules (e.g. a
# cloud TTS API): each would get its own entry here and its own settings
# panel below, keyed off voice_provider so switching providers doesn't
# clobber the other's saved settings.
VOICE_PROVIDERS = {
    "kokoro": "Kokoro (local, offline)",
}


class _KokoroPanel(QWidget):
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
        if settings.voice in VOICE_LABELS:
            self.voice.setCurrentText(VOICE_LABELS[settings.voice])
        else:
            self.voice.addItem(settings.voice, settings.voice)
            self.voice.setCurrentText(settings.voice)
        form.addRow("Voice", self.voice)

        self.lang = QComboBox()
        self.lang.addItems(["en-us", "en-gb"])
        self.lang.setCurrentText(settings.lang)
        form.addRow("Language", self.lang)

        self.voice_speed = QDoubleSpinBox()
        self.voice_speed.setRange(0.5, 2.0)     # Kokoro's own hard limit
        self.voice_speed.setSingleStep(0.1)
        self.voice_speed.setDecimals(1)
        self.voice_speed.setSuffix("x")
        self.voice_speed.setValue(settings.voice_speed)
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
        self.use_gpu.setChecked(settings.use_gpu)
        form.addRow("", self.use_gpu)

    def apply_to_settings(self, settings):
        settings.voice = self._voice_id()
        settings.lang = self.lang.currentText()
        settings.voice_speed = self.voice_speed.value()
        settings.use_gpu = self.use_gpu.isChecked()

    def _voice_id(self) -> str:
        idx = self.voice.currentIndex()
        typed = self.voice.currentText().strip()
        if idx >= 0 and self.voice.itemText(idx) == typed:
            return self.voice.itemData(idx)  # a listed voice: use its real id
        return typed                          # custom text: treat as a raw voice id


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Crier - Settings")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Voice tab ---
        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        provider_form = QFormLayout()
        self.provider = QComboBox()
        for provider_id, label in VOICE_PROVIDERS.items():
            self.provider.addItem(label, provider_id)
        idx = self.provider.findData(settings.voice_provider)
        self.provider.setCurrentIndex(idx if idx >= 0 else 0)
        provider_form.addRow("Provider", self.provider)
        voice_layout.addLayout(provider_form)

        # Only Kokoro exists today, so its panel is always shown; a second
        # provider would swap this based on self.provider's selection.
        self._kokoro_panel = _KokoroPanel(settings)
        voice_layout.addWidget(self._kokoro_panel)
        voice_layout.addStretch(1)
        tabs.addTab(voice_tab, "Voice")

        # --- General tab ---
        general_tab = QWidget()
        form = QFormLayout(general_tab)

        self.hotkey_read = HotkeyEdit(settings.hotkey_read)
        form.addRow("Read hotkey", self.hotkey_read)

        self.hotkey_stop = HotkeyEdit(settings.hotkey_stop)
        form.addRow("Stop hotkey", self.hotkey_stop)

        self.hotkey_grab = HotkeyEdit(settings.hotkey_grab)
        form.addRow("Screen grab hotkey", self.hotkey_grab)

        self.hotkey_smart = HotkeyEdit(settings.hotkey_smart)
        form.addRow("Smart hotkey", self.hotkey_smart)
        smart_hint = QLabel("Smart hotkey reads the selection if there is one, otherwise starts a screen grab.")
        smart_hint.setWordWrap(True)
        smart_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", smart_hint)

        hotkey_hint = QLabel("Click a hotkey field, then press the combo you want.")
        hotkey_hint.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow("", hotkey_hint)

        self.auto_update = QCheckBox("Check for updates on startup")
        self.auto_update.setChecked(settings.auto_update)
        form.addRow("", self.auto_update)

        self.autostart = QCheckBox("Start Crier when I log in")
        self.autostart.setChecked(settings.autostart)
        form.addRow("", self.autostart)

        tabs.addTab(general_tab, "General")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to_settings(self):
        self.settings.voice_provider = self.provider.currentData()
        self._kokoro_panel.apply_to_settings(self.settings)
        self.settings.hotkey_read = self.hotkey_read.value()
        self.settings.hotkey_stop = self.hotkey_stop.value()
        self.settings.hotkey_grab = self.hotkey_grab.value()
        self.settings.hotkey_smart = self.hotkey_smart.value()
        self.settings.auto_update = self.auto_update.isChecked()
        self.settings.autostart = self.autostart.isChecked()
