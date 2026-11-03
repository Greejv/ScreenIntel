"""User settings: where they are stored, and the Settings window."""

import os
import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

from dotenv import dotenv_values, set_key

IS_MAC = sys.platform == "darwin"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FONT_SIZE = 14
MIN_FONT, MAX_FONT = 4, 72
PLACEHOLDER_KEY = "paste_your_key_here"
KEY_URL = "https://aistudio.google.com/apikey"
_ENV_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "FONT_SIZE")


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
    return {
        "api_key": None if key == PLACEHOLDER_KEY else key,
        "model": values.get("GEMINI_MODEL") or DEFAULT_MODEL,
        "font_size": max(MIN_FONT, min(MAX_FONT, font_size)),
    }


def save(settings):
    path = user_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    set_key(str(path), "GEMINI_API_KEY", settings["api_key"] or "")
    set_key(str(path), "GEMINI_MODEL", settings["model"])
    set_key(str(path), "FONT_SIZE", str(settings["font_size"]))


class SettingsWindow:
    """A normal window to edit the API key, model and text size. Calls on_save(settings)."""

    def __init__(self, root, current, on_save, shortcuts):
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
        lines = "\n".join(f"{combo.title()}:  {what}" for combo, what in shortcuts.items())
        ttk.Label(f, text=lines, foreground="gray", justify="left").grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )

        self.error = ttk.Label(f, text="", foreground="#c0392b")
        self.error.grid(row=10, column=0, columnspan=3, sticky="w")

        buttons = ttk.Frame(f)
        buttons.grid(row=11, column=0, columnspan=3, sticky="e", pady=(8, 0))
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
        self._on_save({
            "api_key": key,
            "model": self.model.get().strip() or DEFAULT_MODEL,
            "font_size": max(MIN_FONT, min(MAX_FONT, size)),
        })
        self.close()
