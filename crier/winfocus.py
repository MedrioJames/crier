"""Read/restore the Windows foreground window.

grab_selection() copies from whichever window currently has OS focus, not
whichever one visually shows a text selection. Showing/activating Crier's
own popup - whether from the hotkey, a tray click, or the popup's own
"Read Selection" button - steals that focus, which breaks the copy unless
we restore it first. Plain SetForegroundWindow is unreliable here (Windows
restricts which process can steal foreground focus), so this uses the
documented AttachThreadInput workaround.
"""

import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_user32.AttachThreadInput.restype = wintypes.BOOL
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def get_foreground() -> int:
    return _user32.GetForegroundWindow() or 0


def set_foreground(hwnd: int) -> None:
    if not hwnd:
        return
    try:
        fg = _user32.GetForegroundWindow()
        if fg == hwnd:
            return
        fg_thread = _user32.GetWindowThreadProcessId(fg, None)
        target_thread = _user32.GetWindowThreadProcessId(hwnd, None)
        cur_thread = _kernel32.GetCurrentThreadId()
        _user32.AttachThreadInput(cur_thread, fg_thread, True)
        _user32.AttachThreadInput(target_thread, fg_thread, True)
        _user32.SetForegroundWindow(hwnd)
        _user32.AttachThreadInput(cur_thread, fg_thread, False)
        _user32.AttachThreadInput(target_thread, fg_thread, False)
    except Exception:
        pass
