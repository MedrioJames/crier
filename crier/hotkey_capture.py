"""A read-only line edit that captures a live key-combo press instead of
requiring the user to type pynput's "<ctrl>+<alt>+r" syntax by hand."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit

_SPECIAL_KEYS = {
    Qt.Key_Space: "space", Qt.Key_Tab: "tab", Qt.Key_Escape: "esc",
    Qt.Key_Return: "enter", Qt.Key_Enter: "enter", Qt.Key_Backspace: "backspace",
    Qt.Key_Delete: "delete", Qt.Key_Insert: "insert", Qt.Key_Home: "home",
    Qt.Key_End: "end", Qt.Key_PageUp: "page_up", Qt.Key_PageDown: "page_down",
    Qt.Key_Up: "up", Qt.Key_Down: "down", Qt.Key_Left: "left", Qt.Key_Right: "right",
}
for _i in range(1, 13):
    _SPECIAL_KEYS[getattr(Qt, f"Key_F{_i}")] = f"f{_i}"

_MODIFIER_KEYS = {Qt.Key_Control, Qt.Key_Alt, Qt.Key_AltGr, Qt.Key_Shift, Qt.Key_Meta}


class HotkeyEdit(QLineEdit):
    """Click, then press the combo you want. Escape cancels; needs >=1 modifier."""

    def __init__(self, combo: str, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setCursor(Qt.PointingHandCursor)
        self._combo = combo
        self._recording = False
        self._show_current()

    def value(self) -> str:
        return self._combo

    def _show_current(self):
        self.setText(pretty_hotkey(self._combo) if self._combo else "(none set)")

    def mousePressEvent(self, event):
        self._recording = True
        self.setText("Press a key combo... (Esc to cancel)")

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._recording = True
        self.setText("Press a key combo... (Esc to cancel)")

    def focusOutEvent(self, event):
        self._recording = False
        self._show_current()
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self._recording:
            return
        key = event.key()
        if key == Qt.Key_Escape:
            self._recording = False
            self._show_current()
            return
        if key in _MODIFIER_KEYS:
            return  # wait for the actual key to land on top of the modifiers

        parts = []
        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            parts.append("<ctrl>")
        if mods & Qt.AltModifier:
            parts.append("<alt>")
        if mods & Qt.ShiftModifier:
            parts.append("<shift>")
        if mods & Qt.MetaModifier:
            parts.append("<cmd>")

        if key in _SPECIAL_KEYS:
            parts.append(f"<{_SPECIAL_KEYS[key]}>")
        elif Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
            parts.append(chr(key).lower())
        else:
            return  # unsupported key (e.g. a dead/composition key) - keep waiting

        if len(parts) < 2:
            # A bare, unmodified key would fire on every keystroke system-wide.
            self.setText("Need at least one modifier (Ctrl/Alt/Shift) - try again")
            return

        self._combo = "+".join(parts)
        self._recording = False
        self._show_current()
        self.clearFocus()


def pretty_hotkey(combo: str) -> str:
    """"<ctrl>+<alt>+r" -> "Ctrl+Alt+R" """
    return "+".join(p.strip("<>").capitalize() for p in combo.split("+") if p.strip())
