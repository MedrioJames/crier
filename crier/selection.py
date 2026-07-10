"""Grab the current text selection from whichever app has OS focus."""

import time

import pyperclip
from pynput import keyboard

_kbd = keyboard.Controller()
COPY_DELAY = 0.12

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
