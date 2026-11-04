"""Screen Intel: press a shortcut, the screen goes to Gemini, the answer appears in a tiny overlay."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path

from PIL import ImageGrab

import overlay
import settings
import ui
from ai import Answerer
from hotkeys import HotkeyListener
from welcome import WelcomeWindow

IS_MAC = sys.platform == "darwin"
CAPTURE_MODES = {  # shortcut action -> ai.PROMPTS mode
    "capture": "short",
    "capture_detailed": "detailed",
    "capture_formula": "formula",
    "capture_steps": "steps",
}
HIDE_DELAY_MS = 150  # let the overlay disappear before the screenshot is taken
KEEP_ON_TOP_MS = 250  # the taskbar and other topmost windows can cover the overlay; re-raise it this often


# Menu of the tray icon (Windows) and menu bar icon (macOS): (title, event), None = separator.
MENU = (
    ("Show / hide answer", "toggle"), ("Settings…", "settings"), ("Welcome tour", "welcome"), None,
    ("Restart", "restart"), ("Quit Screen Intel", "quit"),
)


def make_tray(put, tooltip):
    """Windows tray icon; clicking it shows or hides the answer. Runs on pystray's own thread."""
    import pystray

    def action(event):
        return lambda: put(event)  # pystray rejects callbacks with extra (default) arguments

    items = [
        pystray.Menu.SEPARATOR if item is None
        else pystray.MenuItem(item[0], action(item[1]), default=item[1] == "toggle")
        for item in MENU
    ]
    return pystray.Icon("ScreenIntel", ui.app_icon(64), tooltip, pystray.Menu(*items))


class MacMenuBarIcon:
    """macOS menu bar icon with the same menu as the Windows tray, built with AppKit (comes with pynput).

    tk already runs the macOS event loop on the main thread, so the menu's callbacks arrive there.
    If anything goes wrong it simply doesn't appear; the Dock icon and app menu still work.
    """

    def __init__(self, put, header):
        import AppKit
        from Foundation import NSObject

        events = {}

        class ScreenIntelMenuTarget(NSObject):
            def clicked_(self, sender):  # the menu items' action, "clicked:"
                put(events[sender.tag()])

        self._target = ScreenIntelMenuTarget.alloc().init()
        self._bar = AppKit.NSStatusBar.systemStatusBar()
        self._item = self._bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        button = self._item.button()
        symbol = getattr(AppKit.NSImage, "imageWithSystemSymbolName_accessibilityDescription_", None)
        image = symbol("text.viewfinder", "Screen Intel") if symbol else None  # macOS 11+
        if image:
            image.setTemplate_(True)  # follows the light/dark menu bar
            button.setImage_(image)
        else:
            button.setTitle_("SI")
        button.setToolTip_("Screen Intel")

        menu = AppKit.NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        title = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(header, None, "")
        title.setEnabled_(False)
        menu.addItem_(title)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        for tag, item in enumerate(MENU):
            if item is None:
                menu.addItem_(AppKit.NSMenuItem.separatorItem())
                continue
            entry = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(item[0], "clicked:", "")
            entry.setTarget_(self._target)
            entry.setTag_(tag)
            events[tag] = item[1]
            menu.addItem_(entry)
        self._item.setMenu_(menu)

    def stop(self):
        self._bar.removeStatusItem_(self._item)


class App:
    def __init__(self):
        self.busy = False
        self.events = queue.Queue()

        self.settings = settings.load()
        self.answerer = self._make_answerer()
        self.settings_window = None
        self.welcome_window = None

        self.root = tk.Tk()
        self.root.report_callback_exception = self._on_tk_error
        s = self.settings
        self.overlay = overlay.Overlay(self.root, s["font_size"], s["font_family"], s["text_color"])

        self.hotkeys = None
        self._start_hotkeys()

        self.tray = None
        put = lambda event: self.events.put((event, None))  # noqa: E731
        header = f"Screen Intel · {settings.shortcut_label(s['shortcuts']['capture'])} to answer"
        if IS_MAC:
            self.root.createcommand("tk::mac::Quit", self.quit)
            self.root.createcommand("tk::mac::ShowPreferences", self.open_settings)  # app menu, Cmd+,
            self.root.createcommand("tk::mac::ReopenApplication", self.open_settings)  # Dock icon click
            try:
                self.tray = MacMenuBarIcon(put, header)
            except Exception:  # no AppKit or an old macOS: Dock icon and app menu still work
                self.tray = None
        else:
            self.tray = make_tray(put, header)
            self.tray.run_detached()

        self.overlay.set_text(self._status_message())
        if not s["onboarded"]:
            self.open_welcome()
        elif not self.answerer:
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

    def _stop_hotkeys(self):
        if self.hotkeys:
            self.hotkeys.stop()
            self.hotkeys.join(1)  # wait until the shortcuts are released
            self.hotkeys = None

    def _start_hotkeys(self):
        """(Re)register the shortcuts from settings; each one puts its action on the event queue."""
        self._stop_hotkeys()
        bindings = {
            combo: (lambda action=action: self.events.put((action, None)))
            for action, combo in self.settings["shortcuts"].items()
        }
        self.hotkeys = HotkeyListener(bindings)
        self.hotkeys.start()
        self.hotkeys.ready.wait(2)

    def _status_message(self):
        if not self.answerer:
            where = "the menu bar icon" if IS_MAC else "the tray icon"
            return f"No Gemini API key. Open Settings from {where}."
        if self.hotkeys and self.hotkeys.failed:
            used = ", ".join(settings.shortcut_label(c) for c in self.hotkeys.failed)
            return f"Shortcut already used by another app: {used}. Change it in Settings."
        return f"Ready. {settings.shortcut_label(self.settings['shortcuts']['capture'])} to answer."

    def _poll(self):
        while True:
            try:
                name, value = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle(name, value)
        self.root.after(50, self._poll)

    def _handle(self, name, value):
        if name in CAPTURE_MODES:
            self._capture(CAPTURE_MODES[name])
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
        elif name == "welcome":
            self.open_welcome()

    def open_welcome(self):
        if self.welcome_window and self.welcome_window.win.winfo_exists():
            ui.bring_to_front(self.welcome_window.win)
            return
        self.welcome_window = WelcomeWindow(self.root, self.settings, self._welcome_finished)

    def _welcome_finished(self, key):
        new = dict(self.settings, onboarded=True, api_key=key or self.settings["api_key"])
        settings.save(new)
        self.settings = new
        self.answerer = self._make_answerer()
        self.overlay.set_text(self._status_message())
        self.overlay.set_visible(True)

    def open_settings(self):
        if self.settings_window and self.settings_window.is_open():
            self.settings_window.focus()
            return
        # Pause our shortcuts so pressing them in Settings records them (and they don't count as taken).
        self._stop_hotkeys()
        actions = {"welcome": self.open_welcome, "restart": self.restart, "quit": self.quit}
        self.settings_window = settings.SettingsWindow(
            self.root, self.settings, self._apply_settings, self._settings_closed, actions
        )

    def _settings_closed(self):
        self._start_hotkeys()
        if self.hotkeys.failed:
            self.overlay.set_text(self._status_message())
            self.overlay.set_visible(True)

    def _apply_settings(self, new):
        settings.save(new)
        self.settings = new  # shortcuts are re-registered when the window closes
        self.answerer = self._make_answerer()
        self.overlay.set_font_size(new["font_size"])
        self.overlay.set_style(new["font_family"], new["text_color"])
        if self.tray and not IS_MAC:
            capture = settings.shortcut_label(new["shortcuts"]["capture"])
            self.tray.title = f"Screen Intel · {capture} to answer"
        self.overlay.set_text("Settings saved. " + self._status_message())
        self.overlay.set_visible(True)

    def _capture(self, mode):
        if self.busy:
            return
        if not self.answerer:
            self.overlay.set_visible(True)
            return
        self.busy = True
        self.overlay.set_visible(False)
        self.root.update()
        self.root.after(HIDE_DELAY_MS, self._grab_and_ask, mode)

    def _grab_and_ask(self, mode):
        image = ImageGrab.grab(all_screens=not IS_MAC)  # macOS: main display only
        self.overlay.set_text("...")
        self.overlay.set_visible(True)
        threading.Thread(target=self._ask, args=(image, mode), daemon=True).start()

    def _ask(self, image, mode):
        try:
            text = self.answerer.answer(image, mode=mode)
        except Exception as e:
            text = f"Error: {str(e)[:120]}"
        self.events.put(("answer", text))

    def _on_tk_error(self, exc_type, exc, tb):
        self.busy = False
        self.overlay.set_text(f"Error: {exc}"[:150])
        self.overlay.set_visible(True)

    def quit(self):
        self._stop_hotkeys()
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def restart(self):
        """Start a fresh copy of the app (re-reads the key and settings), then quit this one."""
        self._stop_hotkeys()  # release the shortcuts before the new copy registers them
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
