"""Application controller: wires hotkeys, tray, popup, engine, player, updater."""

import sys
import threading
import time

from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtWidgets import QApplication

from . import config
from .settings_store import Settings
from .single_instance import SingleInstance
from .hotkey import HotkeyManager
from .engine import Engine, grab_selection
from .player import Player
from .popup import ControlPopup
from .tray import Tray
from .settings_dialog import SettingsDialog
from .updater import Updater
from .autostart import set_autostart
from . import models
from . import winfocus


class App(QObject):
    # cross-thread status updates (emitted from the synth worker)
    sig_status = Signal(str)
    sig_ready = Signal(bool)          # True once audio is playing
    sig_show_popup = Signal()         # emitted from the read worker thread

    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = Settings()
        self.engine = Engine(use_gpu=self.settings.use_gpu)
        self.player = Player()
        self.player.set_volume(self.settings.volume)

        self.current_text = ""
        self._busy = False
        self._last_external_hwnd = 0   # last foreground window that wasn't our own popup

        self.tray = Tray()
        self.popup = ControlPopup(self.settings.speed, self.settings.volume, self.settings.hotkey_read)
        self._popup_hwnd = int(self.popup.winId())  # cached: winId() isn't safe to call off the GUI thread
        self.updater = Updater(self.popup)
        self.hotkeys = HotkeyManager(self.settings.hotkey_read, self.settings.hotkey_stop)

        # speed re-synth debounce
        self._speed_timer = QTimer(self)
        self._speed_timer.setSingleShot(True)
        self._speed_timer.setInterval(400)
        self._speed_timer.timeout.connect(self._resynth_current)

        self._connect()

    # ---------- wiring ----------
    def _connect(self):
        # Explicit QueuedConnection: hotkeys fire from pynput's own thread.
        self.hotkeys.read_triggered.connect(self.on_read, Qt.QueuedConnection)
        self.hotkeys.stop_triggered.connect(self.on_stop, Qt.QueuedConnection)

        self.tray.show_controls.connect(self.show_controls)
        self.tray.open_settings.connect(self.open_settings)
        self.tray.check_updates.connect(lambda: self.updater.check(silent=False))
        self.tray.quit_app.connect(self.quit)

        self.popup.play_pause.connect(self.on_play_pause)
        self.popup.stop.connect(self.on_stop)
        self.popup.reread.connect(self._resynth_current)
        self.popup.read_selection.connect(self.on_read)
        self.popup.volume_changed.connect(self.on_volume)
        self.popup.speed_changed.connect(self.on_speed)

        # Explicit QueuedConnection: these all cross from a worker thread
        # (PortAudio callback / synth / read-worker threads) onto the GUI thread.
        self.player.finished.connect(self._on_playback_finished, Qt.QueuedConnection)

        self.sig_status.connect(self.tray.tray.setToolTip, Qt.QueuedConnection)
        self.sig_status.connect(self.popup.set_status, Qt.QueuedConnection)
        self.sig_ready.connect(self.popup.set_playing, Qt.QueuedConnection)
        self.sig_show_popup.connect(self.popup.show_near_cursor, Qt.QueuedConnection)

    def start(self):
        self.tray.show()
        self.hotkeys.start()
        self.show_controls()
        if self.settings.auto_update:
            QTimer.singleShot(2500, lambda: self.updater.check(silent=True))

    # ---------- read / play ----------
    def on_read(self):
        # Remember whatever's focused *before* we might show/raise the popup -
        # both the hotkey path (nothing shown yet) and the button-click path
        # (popup already has focus) need this to grab the right selection.
        self._remember_foreground()
        if self._busy:
            self.popup.show_near_cursor()
            return
        self._busy = True
        threading.Thread(target=self._read_worker, daemon=True).start()

    def _remember_foreground(self):
        fg = winfocus.get_foreground()
        if fg and fg != self._popup_hwnd:
            self._last_external_hwnd = fg

    def _read_worker(self):
        try:
            # If our own popup currently has focus (e.g. the user clicked its
            # "Read Selection" button), restore focus to the app the text is
            # actually selected in before copying - Ctrl+C otherwise copies
            # from whatever window is focused, not whichever one shows a
            # visual selection.
            if winfocus.get_foreground() == self._popup_hwnd:
                winfocus.set_foreground(self._last_external_hwnd)
                time.sleep(0.08)

            text = grab_selection()
            self.sig_show_popup.emit()
            if not text:
                self.sig_status.emit("Crier - nothing selected")
                return
            self.current_text = text
            self.sig_status.emit("Crier - synthesizing...")
            samples, sr = self.engine.synthesize(
                text, self.settings.voice, self.settings.speed, self.settings.lang
            )
            self.player.set_volume(self.settings.volume)
            self.player.play(samples, sr)
            self.sig_status.emit(f"Crier ({self.engine.backend})")
            self.sig_ready.emit(True)
        except Exception as e:
            self.sig_status.emit(f"Crier - error: {type(e).__name__}")
        finally:
            self._busy = False

    def _resynth_current(self):
        if not self.current_text or self._busy:
            return
        self._busy = True
        threading.Thread(target=self._resynth_worker, daemon=True).start()

    def _resynth_worker(self):
        try:
            samples, sr = self.engine.synthesize(
                self.current_text, self.settings.voice, self.settings.speed, self.settings.lang
            )
            self.player.set_volume(self.settings.volume)
            self.player.play(samples, sr)
            self.sig_ready.emit(True)
        except Exception as e:
            self.sig_status.emit(f"Crier - error: {type(e).__name__}")
        finally:
            self._busy = False

    def on_play_pause(self):
        if not self.player.is_active():
            self._resynth_current()
            return
        self.player.toggle_pause()
        self.popup.set_playing(not self.player.is_paused())

    def on_stop(self):
        self.player.stop()
        self.popup.set_playing(False)

    def _on_playback_finished(self):
        # player.finished is emitted from the PortAudio callback thread; this
        # slot is a bound method of a QObject (App) so Qt queues it onto the
        # GUI thread instead of touching popup widgets from the audio thread.
        self.popup.set_playing(False)

    def on_volume(self, vol: float):
        self.settings.volume = vol
        self.player.set_volume(vol)

    def on_speed(self, speed: float):
        self.settings.speed = speed
        self._speed_timer.start()          # debounce; re-synth after the slider settles

    # ---------- tray actions ----------
    def show_controls(self):
        self._remember_foreground()
        self.popup.show_near_cursor()

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self.popup)
        if dlg.exec():
            old_gpu = self.settings.use_gpu
            dlg.apply_to_settings()
            self.hotkeys.rebind(self.settings.hotkey_read, self.settings.hotkey_stop)
            self.popup.set_hotkey_hint(self.settings.hotkey_read)
            set_autostart(self.settings.autostart)
            if self.settings.use_gpu != old_gpu:
                self.engine = Engine(use_gpu=self.settings.use_gpu)   # lazy reload

    def quit(self):
        self.hotkeys.stop()
        self.player.stop()
        self.qapp.quit()


def main():
    qapp = QApplication(sys.argv)
    qapp.setApplicationName(config.APP_NAME)
    qapp.setOrganizationName(config.ORG_NAME)
    qapp.setQuitOnLastWindowClosed(False)      # tray app: closing the popup doesn't exit

    # Single instance: a second launch just tells the first to show its controls.
    single = SingleInstance()
    if single.already_running():
        single.signal_existing()
        return 0
    single.start_server()

    # First-run model download (blocks with a progress dialog until done).
    if not models.ensure_models():
        return 1

    app = App(qapp)
    single.activate.connect(app.show_controls)
    app.start()
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main())
