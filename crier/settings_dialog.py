"""Settings dialog reachable from the tray menu."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QLineEdit, QCheckBox,
    QDialogButtonBox, QLabel, QVBoxLayout
)

# A curated subset; Kokoro ships 50+. Users can type any valid id.
VOICES = [
    "af_heart", "af_bella", "af_sarah", "af_nicole", "af_sky",
    "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
]


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
        self.voice.addItems(VOICES)
        if settings.voice not in VOICES:
            self.voice.addItem(settings.voice)
        self.voice.setCurrentText(settings.voice)
        form.addRow("Voice", self.voice)

        self.lang = QComboBox()
        self.lang.addItems(["en-us", "en-gb"])
        self.lang.setCurrentText(settings.lang)
        form.addRow("Language", self.lang)

        self.hotkey_read = QLineEdit(settings.hotkey_read)
        form.addRow("Read hotkey", self.hotkey_read)

        self.hotkey_stop = QLineEdit(settings.hotkey_stop)
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

        hint = QLabel("Hotkey format e.g. <ctrl>+<alt>+r")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to_settings(self):
        self.settings.voice = self.voice.currentText().strip()
        self.settings.lang = self.lang.currentText()
        self.settings.hotkey_read = self.hotkey_read.text().strip()
        self.settings.hotkey_stop = self.hotkey_stop.text().strip()
        self.settings.use_gpu = self.use_gpu.isChecked()
        self.settings.auto_update = self.auto_update.isChecked()
        self.settings.autostart = self.autostart.isChecked()
