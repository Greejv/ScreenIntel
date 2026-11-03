"""Always-on-top, borderless, transparent window that shows only the answer text."""

import sys
import tkinter as tk
from tkinter import font as tkfont

IS_MAC = sys.platform == "darwin"

# Windows: pixels of KEY_COLOR become fully transparent and click-through. macOS: native transparency.
KEY_COLOR = "systemTransparent" if IS_MAC else "#010101"
TEXT_COLOR = "white"
# Windows 11 taskbar clock font, falling back to the Windows 10 one.
WINDOWS_FONTS = ("Segoe UI Variable Text", "Segoe UI")
MIN_FONT, MAX_FONT = 4, 72
PAD = 4

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080  # no taskbar button, not in Alt+Tab
WS_EX_NOACTIVATE = 0x08000000  # clicking/dragging never steals focus from the quiz page


def system_font_family(root):
    """The font the OS uses for its own UI: SF Pro on macOS, the taskbar clock font on Windows."""
    if IS_MAC:
        return tkfont.nametofont("TkDefaultFont", root=root).actual("family")
    installed = set(tkfont.families(root))
    return next((f for f in WINDOWS_FONTS if f in installed), "TkDefaultFont")


class Overlay:
    def __init__(self, root, font_size=14, position=(40, 40)):
        self.root = root
        self.font_size = font_size
        self.visible = True
        self._text = ""
        self._drag_from = None
        self._font_family = system_font_family(root)

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        if IS_MAC:
            root.attributes("-transparent", True)
        else:
            root.attributes("-transparentcolor", KEY_COLOR)
        root.config(bg=KEY_COLOR)
        root.geometry(f"+{position[0]}+{position[1]}")

        self.canvas = tk.Canvas(root, bg=KEY_COLOR, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)

        root.update_idletasks()
        if not IS_MAC:
            self._make_non_activating()

    def _make_non_activating(self):
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)

    def raise_to_top(self):
        """Put the overlay back on top without taking focus."""
        if IS_MAC:
            self.root.lift()
            return
        import ctypes

        hwnd_topmost = -1
        swp_flags = 0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        ctypes.windll.user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_flags)

    def set_text(self, text):
        self._text = text
        self._redraw()

    def set_visible(self, visible):
        self.visible = visible
        self._redraw()

    def toggle(self):
        self.set_visible(not self.visible)

    def change_font(self, step):
        self.font_size = max(MIN_FONT, min(MAX_FONT, self.font_size + step))
        self._redraw()

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        if not (self.visible and self._text):
            c.config(width=1, height=1)  # only transparent pixels left: invisible and click-through
            return

        font = (self._font_family, self.font_size)
        wrap = self.font_size * 30
        c.create_text(PAD, PAD, text=self._text, font=font, fill=TEXT_COLOR, anchor="nw", width=wrap)

        _, _, x2, y2 = c.bbox("all")
        c.config(width=x2 + PAD, height=y2 + PAD)
        self.raise_to_top()

    def _start_drag(self, event):
        self._drag_from = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event):
        dx, dy = self._drag_from
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")
        self.raise_to_top()  # stay above the taskbar while being dragged over it
