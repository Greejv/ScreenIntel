"""Screen Intel: press a shortcut, the screen goes to Gemini, the answer appears in a tiny overlay."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog

from dotenv import load_dotenv, set_key
from PIL import ImageGrab

from ai import Answerer
from hotkeys import HotkeyListener
from overlay import Overlay

IS_MAC = sys.platform == "darwin"
DEFAULT_MODEL = "gemini-3.5-flash-lite"
PLACEHOLDER_KEY = "paste_your_key_here"
SHORTCUTS = {
    "ctrl+shift+q": "capture",
    "ctrl+shift+h": "toggle",
    "ctrl+shift+up": "bigger",
    "ctrl+shift+down": "smaller",
    "ctrl+shift+r": "restart",
    "ctrl+shift+x": "quit",
}
HIDE_DELAY_MS = 150  # let the overlay disappear before the screenshot is taken
KEEP_ON_TOP_MS = 250  # the taskbar and other topmost windows can cover the overlay; re-raise it this often


def app_dir():
    """Folder of the .exe when packaged, otherwise folder of this script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def user_config_file():
    """Per-user settings file, where the key is saved after the first-run prompt."""
    if IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("APPDATA") or Path.home())
    return base / "ScreenIntel" / ".env"


def load_api_key(root):
    """Key from .env next to the app, else the user config file, else ask once and save it."""
    load_dotenv(app_dir() / ".env")
    load_dotenv(user_config_file())
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key != PLACEHOLDER_KEY:
        return key

    key = simpledialog.askstring(
        "Screen Intel",
        "Paste your Gemini API key\n(free at https://aistudio.google.com/apikey):",
        parent=root,
    )
    key = (key or "").strip()
    if not key:
        return None
    path = user_config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    set_key(str(path), "GEMINI_API_KEY", key)
    return key


def make_tray(on_toggle, on_quit):
    """Windows tray icon. macOS has no tray here: quit from the Dock icon or Cmd+Q."""
    import pystray
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((4, 4, 60, 60), fill=(40, 120, 255, 255))
    menu = pystray.Menu(
        pystray.MenuItem("Show / hide", on_toggle, default=True),
        pystray.MenuItem("Quit", on_quit),
    )
    return pystray.Icon("ScreenIntel", img, "Screen Intel", menu)


class App:
    def __init__(self):
        self.busy = False
        self.events = queue.Queue()

        self.root = tk.Tk()
        self.root.withdraw()
        key = load_api_key(self.root)
        self.answerer = Answerer(key, os.getenv("GEMINI_MODEL", DEFAULT_MODEL)) if key else None
        self.root.deiconify()

        self.root.report_callback_exception = self._on_tk_error
        self.overlay = Overlay(self.root)

        self.hotkeys = HotkeyListener(
            {combo: (lambda name=name: self.events.put((name, None))) for combo, name in SHORTCUTS.items()}
        )
        self.hotkeys.start()
        self.hotkeys.ready.wait(2)

        self.tray = None
        if IS_MAC:
            self.root.createcommand("tk::mac::Quit", self.quit)
        else:
            self.tray = make_tray(
                lambda: self.events.put(("toggle", None)), lambda: self.events.put(("quit", None))
            )
            self.tray.run_detached()

        self.overlay.set_text(self._startup_message(key))
        self.root.after(50, self._poll)
        self.root.after(KEEP_ON_TOP_MS, self._keep_on_top)

    def _keep_on_top(self):
        self.overlay.raise_to_top()
        self.root.after(KEEP_ON_TOP_MS, self._keep_on_top)

    def _startup_message(self, key):
        if not key:
            return "No Gemini API key. Restart the app to enter one."
        if self.hotkeys.failed:
            return "Shortcut already used by another app: " + ", ".join(self.hotkeys.failed)
        return "Ready. Ctrl+Shift+Q to answer."

    def _poll(self):
        while True:
            try:
                name, value = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle(name, value)
        self.root.after(50, self._poll)

    def _handle(self, name, value):
        if name == "capture":
            self._capture()
        elif name == "toggle":
            self.overlay.toggle()
        elif name == "bigger":
            self.overlay.change_font(+1)
        elif name == "smaller":
            self.overlay.change_font(-1)
        elif name == "answer":
            self.busy = False
            self.overlay.set_text(value)
            self.overlay.set_visible(True)
        elif name == "quit":
            self.quit()
        elif name == "restart":
            self.restart()

    def _capture(self):
        if self.busy:
            return
        if not self.answerer:
            self.overlay.set_visible(True)
            return
        self.busy = True
        self.overlay.set_visible(False)
        self.root.update()
        self.root.after(HIDE_DELAY_MS, self._grab_and_ask)

    def _grab_and_ask(self):
        image = ImageGrab.grab(all_screens=not IS_MAC)  # macOS: main display only
        self.overlay.set_text("...")
        self.overlay.set_visible(True)
        threading.Thread(target=self._ask, args=(image,), daemon=True).start()

    def _ask(self, image):
        try:
            text = self.answerer.answer(image)
        except Exception as e:
            text = f"Error: {str(e)[:120]}"
        self.events.put(("answer", text))

    def _on_tk_error(self, exc_type, exc, tb):
        self.busy = False
        self.overlay.set_text(f"Error: {exc}"[:150])
        self.overlay.set_visible(True)

    def quit(self):
        self.hotkeys.stop()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def restart(self):
        """Start a fresh copy of the app (re-reads the key and settings), then quit this one."""
        self.hotkeys.stop()
        self.hotkeys.join(1)  # release the shortcuts before the new copy registers them
        if getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve())]
        # Tell a PyInstaller one-file exe to unpack itself again instead of reusing our temp folder.
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        subprocess.Popen(cmd, env=env)
        self.quit()

    def run(self):
        self.root.mainloop()


def main():
    if not IS_MAC:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # sharp text and full-resolution screenshots
        except (AttributeError, OSError):
            pass
    App().run()


if __name__ == "__main__":
    main()
