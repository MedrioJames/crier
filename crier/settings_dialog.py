"""Settings dialog reachable from the tray menu."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QCheckBox,
    QDialogButtonBox, QLabel, QVBoxLayout
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


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Crier - Settings")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

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

        self.hotkey_read = HotkeyEdit(settings.hotkey_read)
        form.addRow("Read hotkey", self.hotkey_read)

        self.hotkey_stop = HotkeyEdit(settings.hotkey_stop)
        form.addRow("Stop hotkey", self.hotkey_stop)

        self.use_gpu = QCheckBox("Try GPU (DirectML - experimental, falls back to CPU)")
        self.use_gpu.setChecked(settings.use_gpu)
        form.addRow("", self.use_gpu)

        self.auto_update = QCheckBox("Check for updates on startup")
        self.auto_update.setChecked(settings.auto_update)
        form.addRow("", self.auto_update)

        self.autostart = QCheckBox("Start Crier when I log in")
        self.autostart.setChecked(settings.autostart)
        form.addRow("", self.autostart)

        hint = QLabel("Click a hotkey field, then press the combo you want.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to_settings(self):
        self.settings.voice = self._voice_id()
        self.settings.lang = self.lang.currentText()
        self.settings.hotkey_read = self.hotkey_read.value()
        self.settings.hotkey_stop = self.hotkey_stop.value()
        self.settings.use_gpu = self.use_gpu.isChecked()
        self.settings.auto_update = self.auto_update.isChecked()
        self.settings.autostart = self.autostart.isChecked()

    def _voice_id(self) -> str:
        idx = self.voice.currentIndex()
        typed = self.voice.currentText().strip()
        if idx >= 0 and self.voice.itemText(idx) == typed:
            return self.voice.itemData(idx)  # a listed voice: use its real id
        return typed                          # custom text: treat as a raw voice id
