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
from . import screen_ocr
from .region_select import RegionSelectOverlay


class App(QObject):
    # cross-thread status updates (emitted from the synth worker)
    sig_status = Signal(str)
    sig_ready = Signal(bool)          # True once audio is playing
    sig_show_popup = Signal()         # emitted from the read worker thread
    sig_start_screen_grab = Signal()  # emitted from the smart-hotkey worker thread

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
        self._grab_overlay = None      # keeps the region-select overlay alive while shown
        self._speak_token = 0          # bumped to abandon an in-flight streaming synthesis

        self.tray = Tray()
        self.popup = ControlPopup(
            self.settings.speed, self.settings.volume, self.settings.hotkey_smart,
        )
        self._popup_hwnd = int(self.popup.winId())  # cached: winId() isn't safe to call off the GUI thread
        self.updater = Updater(self.popup)
        self.hotkeys = HotkeyManager(
            self.settings.hotkey_read, self.settings.hotkey_stop,
            self.settings.hotkey_grab, self.settings.hotkey_smart,
        )

        # speed re-synth debounce
        self._speed_timer = QTimer(self)
        self._speed_timer.setSingleShot(True)
        self._speed_timer.setInterval(400)
        self._speed_timer.timeout.connect(self._resynth_current)

        # seek bar / time label position updates
        self._position_timer = QTimer(self)
        self._position_timer.setInterval(150)
        self._position_timer.timeout.connect(self._update_position)
        self._position_timer.start()

        self._connect()

    # ---------- wiring ----------
    def _connect(self):
        # Explicit QueuedConnection: hotkeys fire from pynput's own thread.
        self.hotkeys.read_triggered.connect(self.on_read, Qt.QueuedConnection)
        self.hotkeys.stop_triggered.connect(self.on_stop, Qt.QueuedConnection)
        self.hotkeys.grab_triggered.connect(self.on_screen_grab, Qt.QueuedConnection)
        self.hotkeys.smart_triggered.connect(self.on_smart, Qt.QueuedConnection)

        self.tray.show_controls.connect(self.show_controls)
        self.tray.open_settings.connect(self.open_settings)
        self.tray.check_updates.connect(lambda: self.updater.check(silent=False))
        self.tray.screen_grab.connect(self.on_screen_grab)
        self.tray.smart_action.connect(self.on_smart)
        self.tray.quit_app.connect(self.quit)

        self.popup.play_pause.connect(self.on_play_pause)
        self.popup.stop.connect(self.on_stop)
        self.popup.reread.connect(self._resynth_current)
        self.popup.smart.connect(self.on_smart)
        self.popup.open_settings.connect(self.open_settings)
        self.popup.quit_app.connect(self.quit)
        self.popup.volume_changed.connect(self.on_volume)
        self.popup.speed_changed.connect(self.on_speed)
        self.popup.seek_requested.connect(self.on_seek)

        # Explicit QueuedConnection: these all cross from a worker thread
        # (PortAudio callback / synth / read-worker threads) onto the GUI thread.
        self.player.finished.connect(self._on_playback_finished, Qt.QueuedConnection)

        self.sig_status.connect(self.tray.tray.setToolTip, Qt.QueuedConnection)
        self.sig_status.connect(self.popup.set_status, Qt.QueuedConnection)
        self.sig_ready.connect(self.popup.set_playing, Qt.QueuedConnection)
        self.sig_show_popup.connect(self.popup.show_popup, Qt.QueuedConnection)
        self.sig_start_screen_grab.connect(self.on_screen_grab, Qt.QueuedConnection)

    def start(self):
        # Show the popup - with an explicit loading message - before
        # anything else, so there's visible feedback as early in startup
        # as possible instead of the tray/hotkeys/engine-warm-up work
        # happening silently first.
        self.popup.set_status("Crier is starting up - loading the voice model, please wait...")
        self.show_controls()
        self.tray.show()
        self.hotkeys.start()
        # Force the popup to actually paint *now*, on this thread, before
        # starting the load. Loading the ONNX model holds Python's GIL for
        # long stretches (measured 500ms+ single stalls just building the
        # inference session) - a background thread doesn't fully protect
        # the GUI thread from that, so without this the first paint can
        # itself get delayed until loading is already done, and "loading"
        # never actually appears on screen.
        self.qapp.processEvents()
        QTimer.singleShot(50, lambda: threading.Thread(target=self._warm_up_engine, daemon=True).start())
        if self.settings.auto_update:
            QTimer.singleShot(2500, lambda: self.updater.check(silent=True))

    def _warm_up_engine(self):
        # Loading the model + Kokoro's first-call phonemizer warm-up takes
        # a couple of seconds; do it now in the background so it isn't the
        # user's very first Read Selection that pays for it, and tell them
        # once it's actually ready instead of leaving the loading message up.
        try:
            self.engine.load(self.settings.voice, self.settings.speed, self.settings.lang)
            self.sig_status.emit(
                f"Crier ready ({self.engine.backend}) - select text anywhere, then use the hotkey or this button."
            )
        except Exception as e:
            self.sig_status.emit(f"Crier - voice model failed to load: {type(e).__name__}")

    # ---------- read / play ----------
    def on_read(self):
        # Remember whatever's focused *before* we might show/raise the popup -
        # both the hotkey path (nothing shown yet) and the button-click path
        # (popup already has focus) need this to grab the right selection.
        self._remember_foreground()
        if self._busy:
            self.popup.show_popup()
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
            self._speak_text(text)
        except Exception as e:
            self.sig_status.emit(f"Crier - error: {type(e).__name__}")
        finally:
            self._busy = False

    # ---------- smart hotkey: selection if there is one, else screen grab ----------
    def on_smart(self):
        self._remember_foreground()
        if self._busy:
            self.popup.show_popup()
            return
        self._busy = True
        threading.Thread(target=self._smart_worker, daemon=True).start()

    def _smart_worker(self):
        try:
            if winfocus.get_foreground() == self._popup_hwnd:
                winfocus.set_foreground(self._last_external_hwnd)
                time.sleep(0.08)

            text = grab_selection()
            if text:
                self.sig_show_popup.emit()
                self._speak_text(text)
                return

            # Nothing selected - hand off to screen grab instead of just
            # reporting "nothing selected". on_screen_grab() creates a
            # QWidget (the overlay) and must run on the GUI thread, and it
            # has its own busy-guard, so release ours first.
            self.sig_status.emit("Crier - nothing selected, starting screen grab...")
            self._busy = False
            self.sig_start_screen_grab.emit()
            return
        except Exception as e:
            self.sig_status.emit(f"Crier - error: {type(e).__name__}")
        finally:
            self._busy = False

    def _speak_text(self, text: str):
        """Synthesize in small chunks (roughly one sentence each) and start
        playback on the first one instead of waiting for the whole text -
        each later chunk gets appended to the still-playing stream as it
        finishes. `_speak_token` lets on_stop()/a newer _speak_text() call
        abandon an in-flight streaming loop instead of it pointlessly
        grinding through remaining chunks (or worse, appending audio after
        the user hit Stop)."""
        self.current_text = text
        self._speak_token += 1
        my_token = self._speak_token
        self.sig_status.emit("Crier - synthesizing...")
        self.player.set_volume(self.settings.volume)

        chunks = self.engine.split_into_chunks(text)
        if not chunks:
            return
        started = False
        for chunk_text, pause_after in chunks:
            if my_token != self._speak_token:
                return
            samples, sr = self.engine.synthesize_chunk(
                chunk_text, self.settings.voice, self.settings.speed, self.settings.lang, pause_after
            )
            if my_token != self._speak_token:
                return
            if not started:
                self.player.play(samples, sr, streaming=True)
                self.sig_status.emit(f"Crier ({self.engine.backend})")
                self.sig_ready.emit(True)
                started = True
            else:
                self.player.append(samples)
        self.player.finish_streaming()

    # ---------- screen grab -> OCR -> speech ----------
    def on_screen_grab(self):
        if self._busy:
            return
        overlay = RegionSelectOverlay()
        self._grab_overlay = overlay   # hold a ref so Python doesn't GC it while shown
        overlay.region_captured.connect(self._on_region_captured)
        overlay.cancelled.connect(self._on_grab_cancelled)
        overlay.show_and_focus()

    def _on_region_captured(self, pixmap):
        self._grab_overlay = None
        self._busy = True
        self.sig_status.emit("Crier - reading screen text...")
        threading.Thread(target=self._ocr_worker, args=(pixmap,), daemon=True).start()

    def _on_grab_cancelled(self):
        self._grab_overlay = None

    def _ocr_worker(self, pixmap):
        try:
            text = screen_ocr.recognize_text(pixmap).strip()
            self.sig_show_popup.emit()
            if not text:
                self.sig_status.emit("Crier - no text found in that region")
                return
            self._speak_text(text)
        except Exception as e:
            self.sig_status.emit(f"Crier - OCR error: {type(e).__name__}")
        finally:
            self._busy = False

    def _resynth_current(self):
        if not self.current_text or self._busy:
            return
        self._busy = True
        threading.Thread(target=self._resynth_worker, daemon=True).start()

    def _resynth_worker(self):
        try:
            self._speak_text(self.current_text)
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
        self._speak_token += 1   # abandon any in-flight streaming synthesis
        dur = self.player.duration_seconds()
        self.player.stop()
        self.popup.set_playing(False)
        self.popup.set_position(0.0, 0.0, dur)

    def on_seek(self, frac: float):
        self.player.seek_fraction(frac)

    def _update_position(self):
        if not self.player.is_active():
            return
        self.popup.set_position(
            self.player.position_fraction(),
            self.player.position_seconds(),
            self.player.duration_seconds(),
        )

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
        self.popup.show_popup()

    def open_settings(self):
        # The global hotkeys are a system-wide hook independent of Qt focus,
        # so capturing a new combo in the dialog (e.g. re-pressing the
        # current one) would also fire the live action underneath it unless
        # we pause listening for the whole dialog session.
        self.hotkeys.stop()
        dlg = SettingsDialog(self.settings, self.popup)
        if dlg.exec():
            old_gpu = self.settings.use_gpu
            dlg.apply_to_settings()
            self.hotkeys.rebind(
                self.settings.hotkey_read, self.settings.hotkey_stop,
                self.settings.hotkey_grab, self.settings.hotkey_smart,
            )
            self.popup.set_smart_hotkey_hint(self.settings.hotkey_smart)
            set_autostart(self.settings.autostart)
            if self.settings.use_gpu != old_gpu:
                self.engine = Engine(use_gpu=self.settings.use_gpu)
                self.popup.set_status("Crier is reloading the voice model, please wait...")
                threading.Thread(target=self._warm_up_engine, daemon=True).start()  # warm it up now, not on next read
        else:
            self.hotkeys.start()  # nothing changed - restore the still-current hotkeys

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
