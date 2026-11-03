"""Screen Intel: press a shortcut, the screen goes to Gemini, the answer appears in a tiny overlay."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

import settings
from ai import Answerer
from hotkeys import HotkeyListener
from overlay import Overlay

IS_MAC = sys.platform == "darwin"
SHORTCUTS = {
    "ctrl+shift+q": "capture",
    "ctrl+shift+d": "capture_detailed",
    "ctrl+shift+h": "toggle",
    "ctrl+shift+up": "bigger",
    "ctrl+shift+down": "smaller",
    "ctrl+shift+r": "restart",
    "ctrl+shift+x": "quit",
}
SHORTCUT_HELP = {
    "ctrl+shift+q": "answer the question on screen",
    "ctrl+shift+d": "answer with a short explanation",
    "ctrl+shift+h": "show / hide the answer",
    "ctrl+shift+up": "bigger text",
    "ctrl+shift+down": "smaller text",
    "ctrl+shift+r": "restart",
    "ctrl+shift+x": "turn off",
}
HIDE_DELAY_MS = 150  # let the overlay disappear before the screenshot is taken
KEEP_ON_TOP_MS = 250  # the taskbar and other topmost windows can cover the overlay; re-raise it this often


def make_tray(on_toggle, on_settings, on_quit):
    """Windows tray icon. macOS has no tray here: Settings and Quit live in the app menu and Dock."""
    import pystray
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((4, 4, 60, 60), fill=(40, 120, 255, 255))
    menu = pystray.Menu(
        pystray.MenuItem("Show / hide", on_toggle, default=True),
        pystray.MenuItem("Settings...", on_settings),
        pystray.MenuItem("Quit", on_quit),
    )
    return pystray.Icon("ScreenIntel", img, "Screen Intel", menu)


class App:
    def __init__(self):
        self.busy = False
        self.events = queue.Queue()

        self.settings = settings.load()
        self.answerer = self._make_answerer()
        self.settings_window = None

        self.root = tk.Tk()
        self.root.report_callback_exception = self._on_tk_error
        self.overlay = Overlay(self.root, font_size=self.settings["font_size"])

        self.hotkeys = HotkeyListener(
            {combo: (lambda name=name: self.events.put((name, None))) for combo, name in SHORTCUTS.items()}
        )
        self.hotkeys.start()
        self.hotkeys.ready.wait(2)

        self.tray = None
        if IS_MAC:
            self.root.createcommand("tk::mac::Quit", self.quit)
            self.root.createcommand("tk::mac::ShowPreferences", self.open_settings)  # app menu, Cmd+,
            self.root.createcommand("tk::mac::ReopenApplication", self.open_settings)  # Dock icon click
        else:
            self.tray = make_tray(
                lambda: self.events.put(("toggle", None)),
                lambda: self.events.put(("settings", None)),
                lambda: self.events.put(("quit", None)),
            )
            self.tray.run_detached()

        self.overlay.set_text(self._status_message())
        if not self.answerer:
            self.open_settings()

        quit_after = os.getenv("SCREENINTEL_QUIT_AFTER_MS")  # used by CI to test a clean shutdown
        if quit_after:
            self.root.after(int(quit_after), self.quit)
        self.root.after(50, self._poll)
        self.root.after(KEEP_ON_TOP_MS, self._keep_on_top)

    def _keep_on_top(self):
        self.overlay.raise_to_top()
        self.root.after(KEEP_ON_TOP_MS, self._keep_on_top)

    def _make_answerer(self):
        key = self.settings["api_key"]
        return Answerer(key, self.settings["model"]) if key else None

    def _status_message(self):
        if not self.answerer:
            where = "the app menu" if IS_MAC else "the tray icon"
            return f"No Gemini API key. Open Settings from {where}."
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
            self._capture(detailed=False)
        elif name == "capture_detailed":
            self._capture(detailed=True)
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
        elif name == "settings":
            self.open_settings()

    def open_settings(self):
        if self.settings_window and self.settings_window.is_open():
            self.settings_window.focus()
            return
        self.settings_window = settings.SettingsWindow(
            self.root, self.settings, self._apply_settings, SHORTCUT_HELP
        )

    def _apply_settings(self, new):
        settings.save(new)
        self.settings = new
        self.answerer = self._make_answerer()
        self.overlay.set_font_size(new["font_size"])
        self.overlay.set_text("Settings saved. " + self._status_message())
        self.overlay.set_visible(True)

    def _capture(self, detailed):
        if self.busy:
            return
        if not self.answerer:
            self.overlay.set_visible(True)
            return
        self.busy = True
        self.overlay.set_visible(False)
        self.root.update()
        self.root.after(HIDE_DELAY_MS, self._grab_and_ask, detailed)

    def _grab_and_ask(self, detailed):
        image = ImageGrab.grab(all_screens=not IS_MAC)  # macOS: main display only
        self.overlay.set_text("...")
        self.overlay.set_visible(True)
        threading.Thread(target=self._ask, args=(image, detailed), daemon=True).start()

    def _ask(self, image, detailed):
        try:
            text = self.answerer.answer(image, detailed=detailed)
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

    # Let background threads finish cleanly (e.g. the tray icon removing itself), then make sure
    # nothing keeps the process alive after the user turned the app off.
    for thread in threading.enumerate():
        if thread is not threading.main_thread() and not thread.daemon:
            thread.join(2)
    os._exit(0)


if __name__ == "__main__":
    main()
