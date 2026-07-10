"""Settings dialog reachable from the tray menu."""

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QCheckBox,
    QDialogButtonBox, QLabel, QVBoxLayout, QWidget, QTabWidget, QStackedWidget
)

from .hotkey_capture import HotkeyEdit
from .providers import PROVIDERS


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Crier - Settings")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Voice tab: a provider dropdown, and a stacked panel of that
        # provider's own settings (API key, voice, tone, etc.) - each
        # provider module supplies its own SettingsPanel, so adding a new
        # provider elsewhere never has to touch this dialog.
        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        provider_form = QFormLayout()
        self.provider = QComboBox()
        self._panels = {}
        self._panel_stack = QStackedWidget()
        for provider_id, module in PROVIDERS.items():
            self.provider.addItem(module.DISPLAY_NAME, provider_id)
            panel = module.SettingsPanel(settings)
            self._panels[provider_id] = panel
            self._panel_stack.addWidget(panel)
        idx = self.provider.findData(settings.voice_provider)
        self.provider.setCurrentIndex(idx if idx >= 0 else 0)
        self._panel_stack.setCurrentWidget(self._panels[self.provider.currentData()])
        self.provider.currentIndexChanged.connect(self._on_provider_changed)
        provider_form.addRow("Provider", self.provider)
        voice_layout.addLayout(provider_form)
        voice_layout.addWidget(self._panel_stack)
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

    def _on_provider_changed(self, index):
        provider_id = self.provider.itemData(index)
        self._panel_stack.setCurrentWidget(self._panels[provider_id])

    def apply_to_settings(self):
        self.settings.voice_provider = self.provider.currentData()
        for panel in self._panels.values():
            panel.apply_to_settings(self.settings)
        self.settings.hotkey_read = self.hotkey_read.value()
        self.settings.hotkey_stop = self.hotkey_stop.value()
        self.settings.hotkey_grab = self.hotkey_grab.value()
        self.settings.hotkey_smart = self.hotkey_smart.value()
        self.settings.auto_update = self.auto_update.isChecked()
        self.settings.autostart = self.autostart.isChecked()
