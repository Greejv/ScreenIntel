"""User settings: where they are stored, and the Settings window."""

import os
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

from dotenv import dotenv_values, set_key

from hotkeys import parse as parse_shortcut

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
    parts = [p for p in text.lower().replace(" ", "").split("+") if p]
    return "+".join(_MOD_ALIASES.get(p, p) for p in parts)


def shortcut_label(combo):
    """'ctrl+shift+q' -> 'Ctrl+Shift+Q' (macOS shows Cmd for the Windows key)."""
    names = {"win": "Cmd" if IS_MAC else "Win"}
    return "+".join(names.get(p, p.upper() if len(p) == 1 else p.capitalize()) for p in combo.split("+"))


def shortcut_errors(shortcuts):
    """Return a message for the first invalid or duplicate shortcut, or None if all are fine."""
    seen = {}
    for action, combo in shortcuts.items():
        label = ACTIONS[action][1]
        try:
            flags, _ = parse_shortcut(combo)
        except (ValueError, KeyError):
            return f'"{combo}" for "{label}" isn\'t a valid shortcut. Example: ctrl+shift+q'
        if not flags:
            return f'The shortcut for "{label}" needs Ctrl, Shift, Alt or Win/Cmd.'
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
    """A normal window to edit the API key, model, text size and shortcuts. Calls on_save(settings)."""

    def __init__(self, root, current, on_save):
        self._on_save = on_save
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
        hint = "Type them like ctrl+shift+q. Keys: A-Z, 0-9, up, down, left, right, space, F1-F12."
        ttk.Label(f, text=hint, foreground="gray", wraplength=380).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        self.shortcuts = {}
        row = 10
        for action, (_, label) in ACTIONS.items():
            ttk.Label(f, text=label).grid(row=row, column=0, sticky="w")
            var = tk.StringVar(value=shortcut_label(current["shortcuts"][action]))
            entry = ttk.Entry(f, textvariable=var, width=18)
            entry.grid(row=row, column=1, columnspan=2, sticky="we", pady=1)
            self.shortcuts[action] = var
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

    def _reset_shortcuts(self):
        for action, (default, _) in ACTIONS.items():
            self.shortcuts[action].set(shortcut_label(default))

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
        shortcuts = {action: normalize_shortcut(var.get()) for action, var in self.shortcuts.items()}
        problem = shortcut_errors(shortcuts)
        if problem:
            self.error.config(text=problem)
            return
        self._on_save({
            "api_key": key,
            "model": self.model.get().strip() or DEFAULT_MODEL,
            "font_size": max(MIN_FONT, min(MAX_FONT, size)),
            "shortcuts": shortcuts,
        })
        self.close()
