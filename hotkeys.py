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


_MOD_ORDER = ("ctrl", "shift", "alt", "win")

# Well-known OS and editing shortcuts that must not be taken over globally (combo: what it does).
_WINDOWS_SYSTEM = {
    "ctrl+c": "Copy", "ctrl+v": "Paste", "ctrl+x": "Cut", "ctrl+z": "Undo", "ctrl+y": "Redo",
    "ctrl+a": "Select all", "ctrl+s": "Save", "ctrl+f": "Find", "ctrl+p": "Print", "ctrl+n": "New",
    "ctrl+o": "Open", "ctrl+w": "Close tab", "ctrl+t": "New tab", "ctrl+r": "Reload",
    "ctrl+shift+z": "Redo", "ctrl+shift+s": "Save as", "ctrl+shift+v": "Paste as plain text",
    "ctrl+shift+t": "Reopen closed tab", "ctrl+shift+n": "New private window / new folder",
    "alt+tab": "Switch windows", "alt+f4": "Close window", "alt+space": "Window menu",
    "win+d": "Show desktop", "win+e": "File Explorer", "win+l": "Lock PC", "win+r": "Run",
    "win+i": "Settings", "win+s": "Search", "win+a": "Quick settings", "win+v": "Clipboard history",
    "win+x": "Quick link menu", "win+m": "Minimize all", "win+tab": "Task view",
    "win+space": "Switch input language", "win+up": "Maximize window", "win+down": "Minimize window",
    "win+left": "Snap window left", "win+right": "Snap window right", "win+shift+s": "Snipping Tool",
    "win+p": "Project to a screen", "win+k": "Cast", "win+h": "Voice typing",
}
_MAC_SYSTEM = {
    "win+c": "Copy", "win+v": "Paste", "win+x": "Cut", "win+z": "Undo", "win+shift+z": "Redo",
    "win+a": "Select all", "win+s": "Save", "win+f": "Find", "win+p": "Print", "win+n": "New",
    "win+o": "Open", "win+w": "Close window", "win+t": "New tab", "win+r": "Reload",
    "win+q": "Quit app", "win+h": "Hide app", "win+m": "Minimize", "win+tab": "Switch apps",
    "win+space": "Spotlight", "win+shift+3": "Screenshot", "win+shift+4": "Screenshot of area",
    "win+shift+5": "Screenshot tools", "ctrl+win+q": "Lock screen", "ctrl+win+f": "Full screen",
    "ctrl+win+space": "Emoji picker", "ctrl+space": "Switch input source", "ctrl+up": "Mission Control",
    "ctrl+down": "App windows", "ctrl+left": "Previous desktop", "ctrl+right": "Next desktop",
    "alt+win+d": "Show / hide Dock",
}
SYSTEM_SHORTCUTS = _MAC_SYSTEM if sys.platform == "darwin" else _WINDOWS_SYSTEM


def canonical(mods, key):
    """Modifiers in a fixed order, key last: ({'shift','ctrl'}, 'q') -> 'ctrl+shift+q'."""
    return "+".join([m for m in _MOD_ORDER if m in mods] + [key])


def is_free(combo):
    """True if no other app has this shortcut. Only Windows can tell; macOS always says True.

    Pause our own listener first, or our own shortcuts count as taken.
    """
    if sys.platform != "win32":
        return True
    import ctypes

    probe_id = 0xBFFF
    flags, vk = parse(combo)
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, probe_id, flags | MOD_NOREPEAT, vk):
        return False
    user32.UnregisterHotKey(None, probe_id)
    return True


# Recording shortcuts from tkinter key events.
_MOD_KEYSYMS = {
    "Shift_L": "shift", "Shift_R": "shift", "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt", "Option_L": "alt", "Option_R": "alt",
    "Meta_L": "win", "Meta_R": "win", "Win_L": "win", "Win_R": "win", "Super_L": "win", "Super_R": "win",
}
_VK_TO_KEY = {vk: k for k, vk in _KEYS.items()}


def modifier_from_keysym(keysym):
    """'Control_L' -> 'ctrl'; None if the key isn't a modifier."""
    return _MOD_KEYSYMS.get(keysym)


def mods_from_state(state):
    """Modifiers held during a tkinter key event (event.state bits differ per platform)."""
    mods = set()
    if state & 0x0004:
        mods.add("ctrl")
    if state & 0x0001:
        mods.add("shift")
    if sys.platform == "darwin":
        if state & 0x0010:
            mods.add("alt")  # Option
        if state & 0x0008:
            mods.add("win")  # Command
    elif state & 0x20000:
        mods.add("alt")
    return mods


def key_from_event(keysym, keycode):
    """The shortcut key name for a tkinter key event, or None if it can't be used in a shortcut.

    On Windows keycode is the virtual key code, which ignores Shift (Shift+1 is still '1').
    """
    if sys.platform == "win32":
        if keycode in _VK_TO_KEY:
            return _VK_TO_KEY[keycode]
        if 0x30 <= keycode <= 0x39 or 0x41 <= keycode <= 0x5A:
            return chr(keycode).lower()
        return None
    k = keysym.lower()
    if k in _KEYS or (len(k) == 1 and k.isalnum()):
        return k
    return None


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
