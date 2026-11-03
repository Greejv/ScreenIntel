"""User settings: where they are stored, and the Settings window."""

import os
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

from dotenv import dotenv_values, set_key

import hotkeys

IS_MAC = sys.platform == "darwin"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FONT_SIZE = 14
MIN_FONT, MAX_FONT = 4, 72
PLACEHOLDER_KEY = "paste_your_key_here"
KEY_URL = "https://aistudio.google.com/apikey"
# action: (default shortcut, description shown in Settings)
ACTIONS = {
    "capture": ("ctrl+shift+q", "Answer the question on screen"),
    "capture_detailed": ("ctrl+shift+d", "Answer with a short explanation"),
    "toggle": ("ctrl+shift+h", "Show / hide the answer"),
    "bigger": ("ctrl+shift+up", "Bigger text"),
    "smaller": ("ctrl+shift+down", "Smaller text"),
    "restart": ("ctrl+shift+r", "Restart"),
    "quit": ("ctrl+shift+x", "Turn off"),
}
_ENV_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "FONT_SIZE") + tuple(
    f"SHORTCUT_{a.upper()}" for a in ACTIONS
)
_MOD_ALIASES = {"control": "ctrl", "option": "alt", "cmd": "win", "command": "win"}


def normalize_shortcut(text):
    """'Ctrl + Shift + Q' -> 'ctrl+shift+q'. Also accepts control/option/cmd."""
    parts = [_MOD_ALIASES.get(p, p) for p in text.lower().replace(" ", "").split("+") if p]
    if not parts:
        return ""
    return hotkeys.canonical(set(parts[:-1]), parts[-1])


def shortcut_label(combo):
    """'ctrl+shift+q' -> 'Ctrl+Shift+Q' (macOS shows Cmd for the Windows key)."""
    names = {"win": "Cmd" if IS_MAC else "Win"}
    return "+".join(names.get(p, p.upper() if len(p) == 1 else p.capitalize()) for p in combo.split("+"))


def shortcut_errors(shortcuts, check_free=False):
    """Return a message for the first unusable shortcut, or None if all are fine.

    Checks: valid key, has a modifier, not a well-known system shortcut, not used twice, and with
    check_free (Windows only) not already taken by another app.
    """
    seen = {}
    for action, combo in shortcuts.items():
        label = ACTIONS[action][1]
        try:
            flags, _ = hotkeys.parse(combo)
        except (ValueError, KeyError):
            return f'"{combo}" for "{label}" isn\'t a valid shortcut.'
        if not flags:
            return f'The shortcut for "{label}" needs Ctrl, Shift, Alt or {"Cmd" if IS_MAC else "Win"}.'
        if combo in hotkeys.SYSTEM_SHORTCUTS:
            name = hotkeys.SYSTEM_SHORTCUTS[combo]
            return f'{shortcut_label(combo)} is a system shortcut ({name}). Pick another for "{label}".'
        if check_free and not hotkeys.is_free(combo):
            taken = "already used by Windows or another app"
            return f'{shortcut_label(combo)} is {taken}. Pick another for "{label}".'
        if combo in seen:
            return f'"{shortcut_label(combo)}" is used twice ("{seen[combo]}" and "{label}").'
        seen[combo] = label
    return None


def app_dir():
    """Folder of the .exe when packaged, otherwise folder of this script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def user_config_file():
    """Per-user settings file written by the Settings window."""
    if IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("APPDATA") or Path.home())
    return base / "ScreenIntel" / ".env"


def load():
    """Settings from, lowest to highest priority: .env next to the app, the settings file, environment."""
    values = {}
    for path in (app_dir() / ".env", user_config_file()):
        if path.is_file():
            values.update({k: v for k, v in dotenv_values(path).items() if v})
    values.update({k: os.environ[k] for k in _ENV_NAMES if os.environ.get(k)})

    key = values.get("GEMINI_API_KEY") or values.get("GOOGLE_API_KEY")
    try:
        font_size = int(values.get("FONT_SIZE", DEFAULT_FONT_SIZE))
    except ValueError:
        font_size = DEFAULT_FONT_SIZE
    shortcuts = {
        action: normalize_shortcut(values.get(f"SHORTCUT_{action.upper()}", default))
        for action, (default, _) in ACTIONS.items()
    }
    if shortcut_errors(shortcuts):  # a hand-edited file broke them: fall back to the defaults
        shortcuts = {action: default for action, (default, _) in ACTIONS.items()}
    return {
        "api_key": None if key == PLACEHOLDER_KEY else key,
        "model": values.get("GEMINI_MODEL") or DEFAULT_MODEL,
        "font_size": max(MIN_FONT, min(MAX_FONT, font_size)),
        "shortcuts": shortcuts,
    }


def save(settings):
    path = user_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    set_key(str(path), "GEMINI_API_KEY", settings["api_key"] or "")
    set_key(str(path), "GEMINI_MODEL", settings["model"])
    set_key(str(path), "FONT_SIZE", str(settings["font_size"]))
    for action, combo in settings["shortcuts"].items():
        set_key(str(path), f"SHORTCUT_{action.upper()}", combo)


class SettingsWindow:
    """A normal window to edit the API key, model, text size and shortcuts.

    Calls on_save(settings) when saved and on_close() whenever the window closes. The app's own
    shortcuts must be paused while it is open, so pressing them here records them instead.
    """

    def __init__(self, root, current, on_save, on_close):
        self._on_save = on_save
        self._on_close = on_close
        self.win = tk.Toplevel(root)
        self.win.title("Screen Intel Settings")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.close)

        f = ttk.Frame(self.win, padding=16)
        f.grid(sticky="nsew")

        ttk.Label(f, text="Gemini API key").grid(row=0, column=0, sticky="w")
        self.key = tk.StringVar(value=current["api_key"] or "")
        self.key_entry = ttk.Entry(f, textvariable=self.key, width=44, show="•")
        self.key_entry.grid(row=1, column=0, columnspan=2, sticky="we")
        self.show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Show", variable=self.show_key, command=self._toggle_key).grid(
            row=1, column=2, padx=(8, 0)
        )
        link = ttk.Label(f, text="Get a free key", foreground="#2a7ae2", cursor="hand2")
        link.grid(row=2, column=0, sticky="w", pady=(2, 12))
        link.bind("<Button-1>", lambda e: webbrowser.open(KEY_URL))

        ttk.Label(f, text="Model").grid(row=3, column=0, sticky="w")
        self.model = tk.StringVar(value=current["model"])
        ttk.Entry(f, textvariable=self.model, width=44).grid(row=4, column=0, columnspan=3, sticky="we")
        ttk.Label(f, text=f"Default: {DEFAULT_MODEL}", foreground="gray").grid(
            row=5, column=0, sticky="w", pady=(2, 12)
        )

        ttk.Label(f, text="Text size").grid(row=6, column=0, sticky="w")
        self.font_size = tk.IntVar(value=current["font_size"])
        ttk.Spinbox(f, from_=MIN_FONT, to=MAX_FONT, textvariable=self.font_size, width=6).grid(
            row=7, column=0, sticky="w", pady=(0, 12)
        )

        ttk.Label(f, text="Shortcuts").grid(row=8, column=0, sticky="w")
        hint = (
            "Click a box, then press the keys you want (Esc cancels). "
            "Shortcuts are paused while Settings is open."
        )
        ttk.Label(f, text=hint, foreground="gray", wraplength=380).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self.shortcuts = {}
        row = 10
        for action, (_, label) in ACTIONS.items():
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w")
            field = ShortcutField(f, current["shortcuts"][action], self._check_shortcuts)
            field.entry.grid(row=row, column=1, columnspan=2, sticky="we", pady=1)
            self.shortcuts[action] = field
            row += 1
        ttk.Button(f, text="Reset shortcuts", command=self._reset_shortcuts).grid(
            row=row, column=0, sticky="w", pady=(4, 12)
        )

        self.error = ttk.Label(f, text="", foreground="#c0392b", wraplength=380)
        self.error.grid(row=row + 1, column=0, columnspan=3, sticky="w")

        buttons = ttk.Frame(f)
        buttons.grid(row=row + 2, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.close).pack(side="right")
        ttk.Button(buttons, text="Save", command=self._save).pack(side="right", padx=(0, 8))
        self.win.bind("<Return>", lambda e: self._save())
        self.win.bind("<Escape>", lambda e: self.close())

        self.focus()

    def focus(self):
        self.win.update_idletasks()
        x = (self.win.winfo_screenwidth() - self.win.winfo_reqwidth()) // 2
        y = (self.win.winfo_screenheight() - self.win.winfo_reqheight()) // 3
        self.win.geometry(f"+{x}+{y}")  # centered, away from the overlay in the top-left
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.key_entry.focus_set()

    def is_open(self):
        return bool(self.win.winfo_exists())

    def close(self):
        self.win.destroy()
        self._on_close()

    def _reset_shortcuts(self):
        for action, (default, _) in ACTIONS.items():
            self.shortcuts[action].set(default)
        self._check_shortcuts()

    def _current_shortcuts(self):
        return {action: field.combo for action, field in self.shortcuts.items()}

    def _check_shortcuts(self):
        """Show the first problem with the shortcuts right away, or clear the message."""
        problem = shortcut_errors(self._current_shortcuts(), check_free=True)
        self.error.config(text=problem or "")
        return problem

    def _toggle_key(self):
        self.key_entry.config(show="" if self.show_key.get() else "•")

    def _save(self):
        key = self.key.get().strip()
        if not key:
            self.error.config(text="Please paste your Gemini API key.")
            return
        try:
            size = int(self.font_size.get())
        except (tk.TclError, ValueError):
            self.error.config(text=f"Text size must be a number from {MIN_FONT} to {MAX_FONT}.")
            return
        if self._check_shortcuts():
            return
        shortcuts = self._current_shortcuts()
        self._on_save({
            "api_key": key,
            "model": self.model.get().strip() or DEFAULT_MODEL,
            "font_size": max(MIN_FONT, min(MAX_FONT, size)),
            "shortcuts": shortcuts,
        })
        self.close()


class ShortcutField:
    """A box that records a shortcut when you press it: click, then press e.g. Ctrl+Shift+Q."""

    def __init__(self, parent, combo, on_change):
        self.combo = combo
        self._on_change = on_change
        self._held = set()  # modifiers whose key is down (catches Win/Cmd that event.state may miss)
        self._var = tk.StringVar(value=shortcut_label(combo))
        self.entry = ttk.Entry(parent, textvariable=self._var, width=18, justify="center")
        self.entry.bind("<FocusIn>", lambda e: self._var.set("Press keys..."))
        self.entry.bind("<FocusOut>", lambda e: self._show())
        self.entry.bind("<KeyPress>", self._key_down)
        self.entry.bind("<KeyRelease>", self._key_up)

    def set(self, combo):
        self.combo = combo
        self._show()

    def _show(self):
        self._held.clear()
        self._var.set(shortcut_label(self.combo))

    def _key_down(self, event):
        mod = hotkeys.modifier_from_keysym(event.keysym)
        if mod:
            self._held.add(mod)
        mods = self._held | hotkeys.mods_from_state(event.state)
        if event.keysym == "Escape" and not mods:
            self.entry.master.focus_set()  # cancel: keep the old shortcut
            return "break"
        key = None if mod else hotkeys.key_from_event(event.keysym, event.keycode)
        if key is None:
            # Only modifiers so far (or an unusable key): show what is held.
            held = hotkeys.canonical(mods, "").rstrip("+")
            self._var.set(shortcut_label(held) + "+..." if held else "Press keys...")
            return "break"
        self.combo = hotkeys.canonical(mods, key)
        self._show()
        self.entry.master.focus_set()  # done recording
        self._on_change()
        return "break"

    def _key_up(self, event):
        mod = hotkeys.modifier_from_keysym(event.keysym)
        if mod:
            self._held.discard(mod)
        return "break"
