"""Always-on-top, borderless, transparent window that shows only outlined text."""

import sys
import tkinter as tk

IS_MAC = sys.platform == "darwin"

# Windows: pixels of KEY_COLOR become fully transparent and click-through. macOS: native transparency.
KEY_COLOR = "systemTransparent" if IS_MAC else "#010101"
TEXT_COLOR = "white"
OUTLINE_COLOR = "black"
FONT_FAMILY = "Helvetica" if IS_MAC else "Segoe UI"
MIN_FONT, MAX_FONT = 6, 72
PAD = 4

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080  # no taskbar button, not in Alt+Tab
WS_EX_NOACTIVATE = 0x08000000  # clicking/dragging never steals focus from the quiz page


class Overlay:
    def __init__(self, root, font_size=14, position=(40, 40)):
        self.root = root
        self.font_size = font_size
        self.visible = True
        self._text = ""
        self._drag_from = None

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

        font = (FONT_FAMILY, self.font_size, "bold")
        wrap = self.font_size * 30
        o = max(1, self.font_size // 12)
        for dx in (-o, 0, o):
            for dy in (-o, 0, o):
                if dx or dy:
                    c.create_text(PAD + dx, PAD + dy, text=self._text, font=font,
                                  fill=OUTLINE_COLOR, anchor="nw", width=wrap)
        c.create_text(PAD, PAD, text=self._text, font=font, fill=TEXT_COLOR, anchor="nw", width=wrap)

        _, _, x2, y2 = c.bbox("all")
        c.config(width=x2 + PAD, height=y2 + PAD)

    def _start_drag(self, event):
        self._drag_from = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event):
        dx, dy = self._drag_from
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")
