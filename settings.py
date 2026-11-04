"""User settings: where they are stored, and the Settings window."""

import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path

from dotenv import dotenv_values, set_key

import hotkeys
import overlay
import ui

IS_MAC = sys.platform == "darwin"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
DEFAULT_FONT_SIZE = 14
DEFAULT_COLOR = "#ffffff"
MIN_FONT, MAX_FONT = 4, 72
PLACEHOLDER_KEY = "paste_your_key_here"
# The API key lives in the OS credential store (Windows Credential Manager / macOS Keychain), not in the file.
KEYRING_SERVICE, KEYRING_USER = "ScreenIntel", "gemini_api_key"
BUNDLE_ID = "io.github.greejv.screenintel"  # macOS app id, set by the build
KEY_URL = "https://aistudio.google.com/apikey"
# Swatches offered for the answer color (besides picking one from the screen).
COLORS = ("#ffffff", "#ffd60a", "#32d74b", "#64d2ff", "#bf5af2", "#ff6482", "#ff9f0a", "#9a9a9a", "#111111")

# action: description shown in Settings
ACTION_LABELS = {
    "capture": "Answer the question on screen",
    "capture_detailed": "Answer with a short explanation",
    "capture_formula": "Just the formula to calculate it",
    "capture_steps": "Short step-by-step working",
    "toggle": "Show / hide the answer",
    "bigger": "Bigger text",
    "smaller": "Smaller text",
    "restart": "Restart",
    "quit": "Turn off",
}
WINDOWS_DEFAULTS = {
    "capture": "ctrl+shift+q", "capture_detailed": "ctrl+shift+d", "capture_formula": "ctrl+shift+f",
    "capture_steps": "ctrl+shift+g", "toggle": "ctrl+shift+h", "bigger": "ctrl+shift+up",
    "smaller": "ctrl+shift+down", "restart": "ctrl+shift+r", "quit": "ctrl+shift+x",
}
# macOS: Control+Option, which no macOS shortcut uses (Control+letter edits text, Cmd belongs to apps,
# Control+arrows switch desktops).
MAC_DEFAULTS = {
    "capture": "ctrl+alt+q", "capture_detailed": "ctrl+alt+d", "capture_formula": "ctrl+alt+f",
    "capture_steps": "ctrl+alt+g", "toggle": "ctrl+alt+h", "bigger": "ctrl+alt+=",
    "smaller": "ctrl+alt+-", "restart": "ctrl+alt+r", "quit": "ctrl+alt+x",
}
# action: (default shortcut on this platform, description shown in Settings)
_DEFAULTS = MAC_DEFAULTS if IS_MAC else WINDOWS_DEFAULTS
ACTIONS = {action: (_DEFAULTS[action], label) for action, label in ACTION_LABELS.items()}
_ENV_NAMES = (
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "FONT_SIZE", "FONT_FAMILY", "TEXT_COLOR",
    "TEXT_OUTLINE", "ONBOARDED",
) + tuple(f"SHORTCUT_{a.upper()}" for a in ACTIONS)
_MOD_ALIASES = {"control": "ctrl", "option": "alt", "cmd": "win", "command": "win"}
_MAC_SYMBOLS = {"ctrl": "⌃", "alt": "⌥", "shift": "⇧", "win": "⌘", "up": "↑", "down": "↓", "left": "←",
                "right": "→", "space": "Space"}


def normalize_shortcut(text):
    """'Ctrl + Shift + Q' -> 'ctrl+shift+q'. Also accepts control/option/cmd."""
    parts = [_MOD_ALIASES.get(p, p) for p in text.lower().replace(" ", "").split("+") if p]
    if not parts:
        return ""
    return hotkeys.canonical(set(parts[:-1]), parts[-1])


def shortcut_label(combo, mac=IS_MAC):
    """'ctrl+shift+q' -> 'Ctrl+Shift+Q' on Windows, '⌃⌥Q' for 'ctrl+alt+q' on macOS."""
    *mods, key = combo.split("+")
    if mac:
        order = ("ctrl", "alt", "shift", "win")  # the order macOS menus use
        return "".join(_MAC_SYMBOLS[m] for m in order if m in mods) + _MAC_SYMBOLS.get(
            key, key.upper() if len(key) == 1 else key.capitalize()
        )
    return "+".join(p.upper() if len(p) == 1 else p.capitalize() for p in mods + [key])


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


def _keyring():
    """The keyring module if this system has a working credential store, else None."""
    try:
        import keyring
        from keyring.backends import fail

        return None if isinstance(keyring.get_keyring(), fail.Keyring) else keyring
    except Exception:  # not installed, or the store can't be reached
        return None


def read_secret():
    kr = _keyring()
    try:
        return kr.get_password(KEYRING_SERVICE, KEYRING_USER) if kr else None
    except Exception:
        return None


def write_secret(key):
    """Store the key in the credential store (or remove it when key is empty). False if there is none."""
    kr = _keyring()
    if not kr:
        return False
    try:
        if key:
            kr.set_password(KEYRING_SERVICE, KEYRING_USER, key)
        else:
            delete_secret()
        return True
    except Exception:
        return False


def delete_secret():
    kr = _keyring()
    try:
        if kr and kr.get_password(KEYRING_SERVICE, KEYRING_USER) is not None:
            kr.delete_password(KEYRING_SERVICE, KEYRING_USER)
            return True
    except Exception:
        pass
    return False


def _lock_down(path):
    """Only the current user may read the settings file (macOS; %APPDATA% on Windows is per-user already)."""
    if sys.platform != "win32":
        os.chmod(path.parent, 0o700)
        os.chmod(path, 0o600)


def app_location():
    """What the user deletes to finish uninstalling: the .exe, the .app bundle, or the source folder."""
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent
    exe = Path(sys.executable)
    return exe.parents[2] if IS_MAC and exe.parent.name == "MacOS" else exe


def uninstall():
    """Remove everything Screen Intel created on this computer; returns a description of each removed item.

    That is the API key in the credential store and the settings folder, and on macOS also the preferences
    and window state macOS keeps for the app and its privacy permissions. The app itself and a .env the user
    put next to it are left for the user to delete.
    """
    removed = []
    if delete_secret():
        removed.append("Your API key in " + ("the Keychain" if IS_MAC else "Windows Credential Manager"))
    path = user_config_file()
    if path.is_file():
        path.unlink()
        removed.append(f"Your settings: {path}")
    try:
        path.parent.rmdir()  # only if empty: never delete files we didn't create
    except OSError:
        pass
    if IS_MAC:
        library = Path.home() / "Library"
        subprocess.run(["defaults", "delete", BUNDLE_ID], capture_output=True, timeout=10)
        for leftover in (
            library / "Preferences" / f"{BUNDLE_ID}.plist",
            library / "Saved Application State" / f"{BUNDLE_ID}.savedState",
            library / "Caches" / BUNDLE_ID,
            library / "HTTPStorages" / BUNDLE_ID,
        ):
            if leftover.is_dir():
                shutil.rmtree(leftover, ignore_errors=True)
            elif leftover.exists():
                leftover.unlink()
            else:
                continue
            removed.append(str(leftover))
        for service in ("ScreenCapture", "Accessibility", "ListenEvent"):
            subprocess.run(["tccutil", "reset", service, BUNDLE_ID], capture_output=True, timeout=10)
        removed.append("The Screen Recording, Accessibility and Input Monitoring permissions")
    return removed


def load():
    """Settings from, lowest to highest priority: .env next to the app, the settings file, the credential
    store (API key only), environment. A key still in the settings file (older versions) moves to the store.
    """
    values = {}
    for path in (app_dir() / ".env", user_config_file()):
        if path.is_file():
            values.update({k: v for k, v in dotenv_values(path).items() if v})
    config = user_config_file()
    file_key = dotenv_values(config).get("GEMINI_API_KEY") if config.is_file() else None
    if file_key and file_key != PLACEHOLDER_KEY and write_secret(file_key):
        set_key(str(config), "GEMINI_API_KEY", "")  # moved to the credential store: no plain-text copy left
    secret = read_secret()
    if secret:
        values["GEMINI_API_KEY"] = secret
    values.update({k: os.environ[k] for k in _ENV_NAMES if os.environ.get(k)})

    key = values.get("GEMINI_API_KEY") or values.get("GOOGLE_API_KEY")
    try:
        font_size = int(values.get("FONT_SIZE", DEFAULT_FONT_SIZE))
    except ValueError:
        font_size = DEFAULT_FONT_SIZE
    color = values.get("TEXT_COLOR", DEFAULT_COLOR).lower()
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
        "font_family": values.get("FONT_FAMILY", ""),
        "text_color": color if re.fullmatch(r"#[0-9a-f]{6}", color) else DEFAULT_COLOR,
        "text_outline": values.get("TEXT_OUTLINE", "1") != "0",
        "shortcuts": shortcuts,
        "onboarded": values.get("ONBOARDED") == "1",
    }


def save(settings):
    path = user_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    _lock_down(path)
    key = settings["api_key"] or ""
    # Only fall back to the (user-only) file when the system has no credential store.
    set_key(str(path), "GEMINI_API_KEY", "" if write_secret(key) else key)
    set_key(str(path), "GEMINI_MODEL", settings["model"])
    set_key(str(path), "FONT_SIZE", str(settings["font_size"]))
    set_key(str(path), "FONT_FAMILY", settings["font_family"])
    set_key(str(path), "TEXT_COLOR", settings["text_color"])
    set_key(str(path), "TEXT_OUTLINE", "1" if settings["text_outline"] else "0")
    set_key(str(path), "ONBOARDED", "1" if settings["onboarded"] else "")
    for action, combo in settings["shortcuts"].items():
        set_key(str(path), f"SHORTCUT_{action.upper()}", combo)


class SettingsWindow:
    """The Settings window: a sidebar with General, Appearance, Shortcuts and Background pages.

    Calls on_save(settings) when saved and on_close() whenever the window closes. `actions` maps
    "welcome", "restart" and "quit" to callbacks for the buttons on the Background page. The app's
    own shortcuts must be paused while it is open, so pressing them here records them instead.
    """

    PAGES = (("general", "⚙", "General"), ("appearance", "◐", "Appearance"),
             ("shortcuts", "⌨", "Shortcuts"), ("background", "◉", "Background"))
    WIDTH, HEIGHT, SIDEBAR_W = 780, 600, 196

    def __init__(self, root, current, on_save, on_close, actions):
        self._on_save, self._on_close, self._actions = on_save, on_close, actions
        self._current = current
        self.win = tk.Toplevel(root, bg=ui.BG)
        self._fonts = overlay.available_fonts(self.win)  # [(name, family)], "" = system font
        self._system_family = overlay.system_font_family(self.win)
        self.win.title("Screen Intel Settings")
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        ui.set_window_icon(self.win)
        ui.dark_title_bar(self.win)

        self.key = tk.StringVar(value=current["api_key"] or "")
        self.model = tk.StringVar(value=current["model"])
        self.font_size = current["font_size"]
        self.font_family = current["font_family"]
        self.color = current["text_color"]
        self.outline = current["text_outline"]
        self.shortcuts = {}

        self._build_sidebar()
        self.content = tk.Frame(self.win, bg=ui.BG)
        self.content.place(x=self.SIDEBAR_W, y=0, width=self.WIDTH - self.SIDEBAR_W, height=self.HEIGHT - 64)
        self.pages = {
            "general": self._page_general(), "appearance": self._page_appearance(),
            "shortcuts": self._page_shortcuts(), "background": self._page_background(),
        }
        self._build_footer()
        self.page = None
        self.show_page("general", animate=False)

        self.win.bind("<Return>", lambda e: self._save())
        self.win.bind("<Escape>", lambda e: self.close())
        self.focus()
        ui.fade_in(self.win)

    # Layout

    def _build_sidebar(self):
        bar = tk.Frame(self.win, bg=ui.SIDEBAR)
        bar.place(x=0, y=0, width=self.SIDEBAR_W, height=self.HEIGHT)
        head = tk.Frame(bar, bg=ui.SIDEBAR)
        head.pack(fill="x", padx=18, pady=(22, 26))
        from PIL import ImageTk

        self._logo = ImageTk.PhotoImage(ui.app_icon(30))
        tk.Label(head, image=self._logo, bg=ui.SIDEBAR).pack(side="left")
        ui.label(head, "Screen Intel", 12, weight="bold").pack(side="left", padx=(10, 0))

        self._nav = {}  # page name -> (row, accent bar, icon, title)
        for name, icon, title in self.PAGES:
            row = tk.Frame(bar, bg=ui.SIDEBAR, cursor="hand2")
            row.pack(fill="x", padx=10, pady=1)
            accent = tk.Frame(row, bg=ui.SIDEBAR, width=3)
            accent.pack(side="left", fill="y")
            parts = [row, accent]
            for text, width in ((icon, 2), (title, 0)):
                part = tk.Label(row, text=text, bg=ui.SIDEBAR, fg=ui.MUTED, font=ui.font(bar, 11),
                                width=width, anchor="w", pady=9)
                part.pack(side="left", padx=(12, 0))
                parts.append(part)
            for w in parts:
                w.bind("<Button-1>", lambda e, n=name: self.show_page(n))
                w.bind("<Enter>", lambda e, n=name: self._nav_hover(n, True))
                w.bind("<Leave>", lambda e, n=name: self._nav_hover(n, False))
            self._nav[name] = parts
        ui.label(bar, "Shortcuts are paused\nwhile Settings is open.", 9, ui.MUTED).pack(
            side="bottom", anchor="w", padx=22, pady=20
        )

    def _nav_hover(self, name, on):
        if name != self.page:
            for w in self._nav[name][2:]:
                w.config(fg=ui.TEXT if on else ui.MUTED)

    def _build_footer(self):
        foot = tk.Frame(self.win, bg=ui.BG)
        foot.place(x=self.SIDEBAR_W, y=self.HEIGHT - 64, width=self.WIDTH - self.SIDEBAR_W, height=64)
        tk.Frame(foot, bg=ui.BORDER, height=1).pack(fill="x")
        ui.Button(foot, "Save", self._save, "primary", width=96).pack(side="right", padx=(8, 28), pady=13)
        ui.Button(foot, "Cancel", self.close, "secondary", width=96).pack(side="right", pady=13)
        self.error = ui.label(foot, "", 9, ui.DANGER, wraplength=320)
        self.error.pack(side="left", padx=28)

    def _page(self, title, subtitle, scroll=False):
        if scroll:
            outer, page = ui.scrollable(self.content, ui.BG)
            page.config(padx=28, pady=24)
            page.outer = outer  # what show_page places
        else:
            page = tk.Frame(self.content, bg=ui.BG, padx=28, pady=24)
        ui.label(page, title, 18, weight="bold").pack(anchor="w")
        ui.label(page, subtitle, 10, ui.MUTED).pack(anchor="w", pady=(2, 16))
        return page

    def show_page(self, name, animate=True):
        if name == self.page:
            return
        old, self.page = self.page, name
        for n, (row, accent, *labels) in self._nav.items():
            on = n == name
            row.config(bg=ui.CARD if on else ui.SIDEBAR)
            accent.config(bg=ui.ACCENT if on else ui.SIDEBAR)
            for w in labels:
                w.config(bg=ui.CARD if on else ui.SIDEBAR, fg=ui.TEXT if on else ui.MUTED)
        if old:
            getattr(self.pages[old], "outer", self.pages[old]).place_forget()
        page = getattr(self.pages[name], "outer", self.pages[name])  # a scrolling page is placed by its frame
        w = self.WIDTH - self.SIDEBAR_W
        if not animate:
            page.place(x=0, y=0, width=w, relheight=1)
            return
        ui.animate(page, 220, lambda t: page.place(x=0, y=round(18 * (1 - t)), width=w, relheight=1))

    def _page_general(self):
        page = self._page("General", "Connect Screen Intel to Google Gemini.")
        box = ui.card(page)
        box.pack(fill="x")
        c = box.inner
        ui.label(c, "Gemini API key", 11, weight="bold").pack(anchor="w")
        ui.label(c, "Saved only on this computer.", 9, ui.MUTED).pack(anchor="w", pady=(0, 8))
        row = tk.Frame(c, bg=ui.CARD)
        row.pack(fill="x")
        self.key_entry = ui.entry(row, self.key, show="•", width=38)
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self._show_btn = ui.Button(row, "Show", self._toggle_key, "secondary", width=70, height=34)
        self._show_btn.pack(side="left", padx=(8, 0))
        ui.link(c, "Get a free key  ↗", KEY_URL).pack(anchor="w", pady=(8, 0))

        box = ui.card(page)
        box.pack(fill="x", pady=(14, 0))
        c = box.inner
        ui.label(c, "Model", 11, weight="bold").pack(anchor="w")
        ui.label(c, f"Leave the default ({DEFAULT_MODEL}) unless it stops working.", 9, ui.MUTED).pack(
            anchor="w", pady=(0, 8)
        )
        ui.entry(c, self.model, width=38).pack(fill="x", ipady=6)
        return page

    def _page_appearance(self):
        page = self._page("Appearance", "How the answer looks on your screen.", scroll=True)
        # Live preview: the answer drawn over a fake quiz page.
        self.preview = tk.Canvas(page, height=104, bg="#2b2f3a", highlightthickness=1,
                                 highlightbackground=ui.BORDER)
        self.preview.pack(fill="x")
        self.preview.bind("<Configure>", lambda e: self._draw_preview())

        row = tk.Frame(page, bg=ui.BG)
        row.pack(fill="x", pady=(16, 6))
        ui.label(row, "Font", 11, weight="bold").pack(side="left")
        size = tk.Frame(row, bg=ui.BG)
        size.pack(side="right")
        ui.label(size, "Size", 11, weight="bold").pack(side="left", padx=(0, 10))
        ui.Button(size, "−", lambda: self._set_size(self.font_size - 1), "secondary", 34, 30, size=12).pack(
            side="left"
        )
        self._size_label = ui.label(size, "", 11, width=6, anchor="center")
        self._size_label.pack(side="left")
        ui.Button(size, "+", lambda: self._set_size(self.font_size + 1), "secondary", 34, 30, size=12).pack(
            side="left"
        )

        fonts = tk.Frame(page, bg=ui.BG)
        fonts.pack(fill="x")
        self._font_chips = {}
        for i, (name, fam) in enumerate(self._fonts):
            chip = tk.Label(fonts, text=name, font=(fam or ui.family(page), 11), bg=ui.CARD, fg=ui.TEXT,
                            padx=8, pady=6, cursor="hand2", highlightthickness=1)
            chip.grid(row=i // 3, column=i % 3, sticky="we", padx=(0, 6), pady=(0, 6))
            chip.bind("<Button-1>", lambda e, f=fam: self._set_font(f))
            self._font_chips[fam] = chip
        for col in range(3):
            fonts.columnconfigure(col, weight=1, uniform="font")

        ui.label(page, "Color", 11, weight="bold").pack(anchor="w", pady=(10, 6))
        colors = tk.Frame(page, bg=ui.BG)
        colors.pack(fill="x")
        self._swatches = {}
        for color in COLORS:
            sw = tk.Canvas(colors, width=30, height=30, bg=ui.BG, highlightthickness=0, cursor="hand2")
            sw.pack(side="left", padx=(0, 6))
            sw.bind("<Button-1>", lambda e, c=color: self._set_color(c))
            self._swatches[color] = sw
        tools = tk.Frame(page, bg=ui.BG)
        tools.pack(fill="x", pady=(10, 0))
        ui.Button(tools, "⊹  Pick a color from the screen", self._pick_color, "secondary", height=32).pack(
            side="left"
        )
        ui.Button(tools, "Custom…", self._custom_color, "ghost", height=32).pack(side="left", padx=6)
        self._hex = ui.label(tools, "", 10, ui.MUTED)
        self._hex.pack(side="right")

        if not IS_MAC:  # macOS draws transparent text without the dark edge
            row = tk.Frame(page, bg=ui.BG)
            row.pack(fill="x", pady=(18, 0))
            ui.Switch(row, self.outline, self._set_outline).pack(side="right")
            ui.label(row, "Dark outline", 11, weight="bold").pack(anchor="w")
            hint = "A thin dark edge that makes light text readable on white pages."
            ui.label(row, hint, 9, ui.MUTED).pack(anchor="w")
        self._refresh_appearance()
        return page

    def _page_shortcuts(self):
        page = self._page("Shortcuts", "Click a shortcut, then press the keys you want. Esc cancels.")
        box = ui.card(page, padding=14)
        box.pack(fill="x")
        for action, (_, label) in ACTIONS.items():
            row = tk.Frame(box.inner, bg=ui.CARD)
            row.pack(fill="x", pady=2)
            ui.label(row, label, 10).pack(side="left")
            field = ShortcutField(row, self._current["shortcuts"][action], self._check_shortcuts)
            field.widget.pack(side="right")
            self.shortcuts[action] = field
        ui.Button(page, "Reset to defaults", self._reset_shortcuts, "ghost").pack(anchor="w", pady=(10, 0))
        return page

    def _page_background(self):
        page = self._page("Background", "Screen Intel runs quietly until you press a shortcut.")
        box = ui.card(page)
        box.pack(fill="x")
        c = box.inner
        where = (
            "Click the lens icon in the menu bar (top right) for Show / hide, Settings and Quit. "
            "Clicking the Dock icon opens Settings."
            if IS_MAC
            else "Right-click the lens icon in the system tray (bottom right, maybe behind ^) for "
            "Show / hide, Settings and Quit. Click it to show or hide the answer."
        )
        ui.label(c, "Where to find it", 11, weight="bold").pack(anchor="w")
        ui.label(c, where, 10, ui.MUTED, wraplength=470).pack(anchor="w", pady=(4, 12))
        buttons = tk.Frame(c, bg=ui.CARD)
        buttons.pack(anchor="w")
        ui.Button(buttons, "Show welcome tour", lambda: self._run("welcome"), "secondary").pack(side="left")
        ui.Button(buttons, "Restart", lambda: self._run("restart"), "secondary").pack(side="left", padx=8)
        ui.Button(buttons, "Quit Screen Intel", lambda: self._run("quit"), "secondary").pack(side="left")

        box = ui.card(page)
        box.pack(fill="x", pady=(14, 0))
        c = box.inner
        ui.label(c, "Leaves nothing behind", 11, weight="bold").pack(anchor="w")
        store = "Keychain" if IS_MAC else "Windows Credential Manager"
        text = (
            "No services, startup entries or background helpers. When you turn it off it is gone. "
            f"It keeps only your API key (in the {store}) and your settings:\n{user_config_file()}"
        )
        ui.label(c, text, 10, ui.MUTED, wraplength=470).pack(anchor="w", pady=(4, 12))
        ui.Button(c, "Uninstall Screen Intel…", self._uninstall, "danger").pack(anchor="w")
        return page

    def _uninstall(self):
        from tkinter import messagebox

        app = "ScreenIntel.app" if IS_MAC else "ScreenIntel.exe"
        sure = messagebox.askyesno(
            "Uninstall Screen Intel?",
            "This deletes your API key, your settings and everything else Screen Intel saved on this "
            f"computer, then turns the app off. You delete {app} yourself afterwards.\n\n"
            "This can't be undone.",
            icon="warning", default="no", parent=self.win,
        )
        if sure:
            self._run("uninstall")

    # Appearance

    def _set_size(self, size):
        self.font_size = max(MIN_FONT, min(MAX_FONT, size))
        self._refresh_appearance()

    def _set_font(self, family):
        self.font_family = family
        self._refresh_appearance()

    def _set_color(self, color):
        if color:
            self.color = color.lower()
            self._refresh_appearance()

    def _custom_color(self):
        from tkinter import colorchooser

        _, color = colorchooser.askcolor(self.color, parent=self.win, title="Answer color")
        self._set_color(color)

    def _pick_color(self):
        """Hide Settings, let the user click a color anywhere on the screen, then come back."""
        self.win.withdraw()

        def done(color):
            self.focus()
            self.show_page("appearance", animate=False)
            self._set_color(color)

        self.win.after(250, lambda: ui.pick_screen_color(self.win, done))

    def _set_outline(self, on):
        self.outline = on
        self._draw_preview()

    def _refresh_appearance(self):
        self._size_label.config(text=f"{self.font_size}")
        self._hex.config(text=self.color.upper())
        for fam, chip in self._font_chips.items():
            on = fam == self.font_family
            chip.config(bg=ui.mix(ui.CARD, ui.ACCENT, 0.25) if on else ui.CARD,
                        highlightbackground=ui.ACCENT if on else ui.BORDER)
        for color, sw in self._swatches.items():
            sw.delete("all")
            if color == self.color:
                sw.create_oval(1, 1, 29, 29, outline=ui.ACCENT_HOVER, width=2)
            sw.create_oval(6, 6, 24, 24, fill=color, outline=ui.BORDER)
        self._draw_preview()

    def _draw_preview(self):
        c = self.preview
        c.delete("all")
        w = c.winfo_width() if c.winfo_width() > 1 else 500
        for i in range(3):  # a faint quiz page behind the answer
            c.create_rectangle(18, 18 + i * 26, w * (0.55 - i * 0.1), 30 + i * 26, fill="#363b48", outline="")
        pixels = max(1, round(self.font_size * c.winfo_fpixels("1p")))  # same sizing as the overlay
        font = (self.font_family or self._system_family, -pixels)
        text = "B   ·   Paris | 1789"
        if self.outline and not IS_MAC:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                c.create_text(w - 24 + dx, 52 + dy, text=text, font=font, fill="#010101", anchor="e")
        c.create_text(w - 24, 52, text=text, font=font, fill=self.color, anchor="e")

    # Window

    def focus(self):
        self.win.update_idletasks()
        x = (self.win.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.win.winfo_screenheight() - self.HEIGHT) // 3
        self.win.geometry(f"+{x}+{y}")  # centered, away from the overlay in the top-left
        ui.bring_to_front(self.win)

    def is_open(self):
        return bool(self.win.winfo_exists())

    def close(self):
        self.win.destroy()
        self._on_close()

    def _run(self, action):
        self.close()
        self._actions[action]()

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
        hidden = self.key_entry.cget("show") != ""
        self.key_entry.config(show="" if hidden else "•")
        self._show_btn.set_text("Hide" if hidden else "Show")

    def _save(self):
        key = self.key.get().strip()
        if not key:
            self.show_page("general")
            self.error.config(text="Please paste your Gemini API key.")
            return
        if self._check_shortcuts():
            self.show_page("shortcuts")
            return
        self._on_save(dict(
            self._current,
            api_key=key,
            model=self.model.get().strip() or DEFAULT_MODEL,
            font_size=self.font_size,
            font_family=self.font_family,
            text_color=self.color,
            text_outline=self.outline,
            shortcuts=self._current_shortcuts(),
        ))
        self.close()


class ShortcutField:
    """A key-shaped box that records a shortcut when you press it: click, then press e.g. Ctrl+Shift+Q."""

    def __init__(self, parent, combo, on_change):
        self.combo = combo
        self._on_change = on_change
        self._held = set()  # modifiers whose key is down (catches Win/Cmd that event.state may miss)
        self.widget = tk.Label(
            parent, width=16, bg=ui.INPUT, fg=ui.TEXT, font=ui.font(parent, 10, "bold"), pady=5,
            cursor="hand2", takefocus=True, highlightthickness=1, highlightbackground=ui.BORDER,
            highlightcolor=ui.ACCENT,
        )
        self.widget.bind("<Button-1>", lambda e: self.widget.focus_set())
        self.widget.bind("<FocusIn>", lambda e: self._recording("Press keys…"))
        self.widget.bind("<FocusOut>", lambda e: self._show())
        self.widget.bind("<KeyPress>", self._key_down)
        self.widget.bind("<KeyRelease>", self._key_up)
        self._show()

    def set(self, combo):
        self.combo = combo
        self._show()

    def _recording(self, text):
        self.widget.config(text=text, fg=ui.ACCENT_HOVER)

    def _show(self):
        self._held.clear()
        self.widget.config(text=shortcut_label(self.combo), fg=ui.TEXT)

    def _done(self):
        self.widget.winfo_toplevel().focus_set()

    def _key_down(self, event):
        mod = hotkeys.modifier_from_keysym(event.keysym)
        if mod:
            self._held.add(mod)
        mods = self._held | hotkeys.mods_from_state(event.state)
        if event.keysym == "Escape" and not mods:
            self._done()  # cancel: keep the old shortcut
            return "break"
        key = None if mod else hotkeys.key_from_event(event.keysym, event.keycode)
        if key is None:
            # Only modifiers so far (or an unusable key): show what is held.
            held = hotkeys.canonical(mods, "").rstrip("+")
            self._recording(shortcut_label(held + "+…") if held else "Press keys…")
            return "break"
        self.combo = hotkeys.canonical(mods, key)
        self._show()
        self._done()  # done recording
        self._on_change()
        return "break"

    def _key_up(self, event):
        mod = hotkeys.modifier_from_keysym(event.keysym)
        if mod:
            self._held.discard(mod)
        return "break"
