"""Global shortcuts. Windows uses RegisterHotKey (no keyboard hook); macOS uses pynput.

Both listeners take {"ctrl+shift+q": callback, ...}, call callbacks on a background
thread, expose .ready (Event) and .failed (shortcuts that could not be registered).
"""

import sys
import threading

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

_MODS = {"ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "alt": MOD_ALT, "win": MOD_WIN}
_KEYS = {"up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "space": 0x20}
_KEYS.update({f"f{n}": 0x6F + n for n in range(1, 13)})  # F1..F12


def parse(combo):
    """'ctrl+shift+q' -> (Windows modifier flags, virtual key code)."""
    *mods, key = combo.lower().split("+")
    flags = 0
    for m in mods:
        if m not in _MODS:
            raise ValueError(f"Unknown modifier in shortcut: {combo}")
        flags |= _MODS[m]
    if key in _KEYS:
        vk = _KEYS[key]
    elif len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    else:
        raise ValueError(f"Unknown key in shortcut: {combo}")
    return flags, vk


def to_pynput(combo):
    """'ctrl+shift+up' -> '<ctrl>+<shift>+<up>' (pynput hotkey syntax)."""
    *mods, key = combo.lower().split("+")
    names = {"win": "cmd"}
    parts = [f"<{names.get(m, m)}>" for m in mods]
    parts.append(f"<{key}>" if key in _KEYS else key)
    return "+".join(parts)


class WindowsHotkeys(threading.Thread):
    def __init__(self, bindings):
        super().__init__(daemon=True)
        self._bindings = list(bindings.items())
        self._thread_id = None
        self.ready = threading.Event()
        self.failed = []

    def run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT
        ]
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        registered = []
        for hk_id, (combo, _) in enumerate(self._bindings, start=1):
            flags, vk = parse(combo)
            if user32.RegisterHotKey(None, hk_id, flags | MOD_NOREPEAT, vk):
                registered.append(hk_id)
            else:
                self.failed.append(combo)
        self.ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and 1 <= msg.wParam <= len(self._bindings):
                self._bindings[msg.wParam - 1][1]()

        for hk_id in registered:
            user32.UnregisterHotKey(None, hk_id)

    def stop(self):
        if self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)


class MacHotkeys:
    """Needs Accessibility / Input Monitoring permission in System Settings > Privacy & Security."""

    def __init__(self, bindings):
        from pynput import keyboard

        self._listener = keyboard.GlobalHotKeys({to_pynput(c): cb for c, cb in bindings.items()})
        self.ready = threading.Event()
        self.failed = []

    def start(self):
        self._listener.start()
        self.ready.set()

    def stop(self):
        self._listener.stop()

    def join(self, timeout=None):
        self._listener.join(timeout)


HotkeyListener = MacHotkeys if sys.platform == "darwin" else WindowsHotkeys
