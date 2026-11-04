"""The shared look of the Settings and Welcome windows: colors, fonts, widgets, animation, the app icon,
and the on-screen color picker. Plain tkinter (no ttk), so it looks the same on Windows and macOS.
"""

import sys
import time
import tkinter as tk
from tkinter import font as tkfont

IS_MAC = sys.platform == "darwin"

# Dark theme.
BG = "#0e1016"
SIDEBAR = "#13161e"
CARD = "#181c25"
CARD_HOVER = "#1f2430"
INPUT = "#10131a"
BORDER = "#2a303d"
TEXT = "#eef0f6"
MUTED = "#8a92a6"
ACCENT = "#7c6cff"
ACCENT_HOVER = "#9184ff"
ACCENT_2 = "#22d3ee"  # second gradient color
DANGER = "#ff5d6c"
SUCCESS = "#3ddc97"

_family = None


def family(root):
    """The OS UI font: Segoe UI Variable on Windows 11, SF Pro on macOS."""
    global _family
    if _family is None:
        installed = set(tkfont.families(root))
        wanted = ("Segoe UI Variable Display", "Segoe UI")
        _family = next((f for f in wanted if f in installed), None) or tkfont.nametofont(
            "TkDefaultFont", root=root
        ).actual("family")
    return _family


def font(root, size, weight="normal"):
    return (family(root), size, weight)


def mix(c1, c2, t):
    """Blend two '#rrggbb' colors; t=0 gives c1, t=1 gives c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b, strict=True))


def ease(t):
    """Ease-out cubic: fast start, gentle stop."""
    return 1 - (1 - t) ** 3


def animate(widget, duration_ms, step, done=None):
    """Call step(eased t) from 0 to 1 over duration_ms on the tk thread, then done()."""
    start = time.perf_counter()

    def tick():
        if not widget.winfo_exists():
            return
        t = min(1.0, (time.perf_counter() - start) * 1000 / duration_ms)
        step(ease(t))
        if t < 1:
            widget.after(12, tick)
        elif done:
            done()

    tick()


def fade_in(window, duration_ms=260):
    """Fade a window in (where the window manager supports transparency)."""
    try:
        window.attributes("-alpha", 0.0)
    except tk.TclError:
        return
    animate(window, duration_ms, lambda t: window.attributes("-alpha", t))


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


def dark_title_bar(window):
    """Windows 10/11: dark title bar to match the window. Elsewhere nothing to do."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        on = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (newer, older builds)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(on), 4) == 0:
                break
    except (AttributeError, OSError):
        pass


def bring_to_front(window):
    """Show a window above everything and give it focus, even when the app runs in the background."""
    window.deiconify()
    window.lift()
    window.attributes("-topmost", True)
    if IS_MAC:
        try:
            import AppKit

            AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:  # PyObjC missing: tk's own focus is the best we can do
            pass
    window.focus_force()


def app_icon(size=64):
    """The app icon as a PIL image: a violet-to-cyan rounded square with a white lens."""
    from PIL import Image, ImageDraw

    s = size * 4  # draw large, then shrink for smooth edges
    a, b = [int(ACCENT[i:i + 2], 16) for i in (1, 3, 5)], [int(ACCENT_2[i:i + 2], 16) for i in (1, 3, 5)]
    gradient = Image.new("RGB", (s, s))
    px = gradient.load()
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * s)
            px[x, y] = tuple(round(p + (q - p) * t) for p, q in zip(a, b, strict=True))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 4, fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(gradient, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = s // 11
    d.ellipse((s * 0.22, s * 0.22, s * 0.70, s * 0.70), outline="white", width=w)  # lens
    d.line((s * 0.63, s * 0.63, s * 0.80, s * 0.80), fill="white", width=w)  # handle
    d.ellipse((s * 0.74, s * 0.74, s * 0.86, s * 0.86), fill="white")
    d.ellipse((s * 0.36, s * 0.34, s * 0.46, s * 0.44), fill="white")  # glint
    return img.resize((size, size), Image.LANCZOS)


def set_window_icon(window):
    from PIL import ImageTk

    window._icon = ImageTk.PhotoImage(app_icon(64))  # keep a reference or tk drops the image
    window.iconphoto(False, window._icon)


class Button(tk.Canvas):
    """A rounded button. kind: primary (filled accent), secondary (outlined), ghost (text only), danger."""

    def __init__(self, parent, text, command, kind="primary", width=None, height=36, bg=None, size=10):
        bg = bg or parent.cget("bg")
        self._font = font(parent, size, "bold" if kind == "primary" else "normal")
        width = width or tkfont.Font(root=parent, font=self._font).measure(text) + 36
        super().__init__(parent, width=width, height=height, bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2")
        self._text, self._command, self._kind = text, command, kind
        self._bw, self._bh, self._enabled = width, height, True
        self._draw(False)
        self.bind("<Enter>", lambda e: self._draw(True))
        self.bind("<Leave>", lambda e: self._draw(False))
        self.bind("<ButtonRelease-1>", self._click)

    def set_text(self, text):
        self._text = text
        self._draw(False)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self.config(cursor="hand2" if enabled else "arrow")
        self._draw(False)

    def _colors(self, hover):
        if not self._enabled:
            bg = self.cget("bg")
            return (bg, "", bg) if self._kind == "ghost" else (CARD, BORDER, MUTED)
        return {
            "primary": (ACCENT_HOVER if hover else ACCENT, "", "white"),
            "secondary": (CARD_HOVER if hover else CARD, BORDER, TEXT),
            "ghost": (CARD if hover else self.cget("bg"), "", TEXT if hover else MUTED),
            "danger": (mix(CARD, DANGER, 0.25) if hover else CARD, mix(BORDER, DANGER, 0.5), DANGER),
        }[self._kind]

    def _draw(self, hover):
        fill, outline, fg = self._colors(hover)
        self.delete("all")
        rounded_rect(self, 1, 1, self._bw - 1, self._bh - 1, 10, fill=fill, outline=outline)
        self.create_text(self._bw / 2, self._bh / 2, text=self._text, fill=fg, font=self._font)

    def _click(self, event):
        inside = 0 <= event.x <= self._bw and 0 <= event.y <= self._bh
        if self._enabled and inside:
            self._command()


def card(parent, padding=16):
    """A rounded-looking panel: returns the inner frame to put content in."""
    outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    inner = tk.Frame(outer, bg=CARD, padx=padding, pady=padding - 4)
    inner.pack(fill="both", expand=True)
    outer.inner = inner
    return outer


def label(parent, text, size=10, color=TEXT, weight="normal", **kw):
    kw = {"justify": "left", "anchor": "w", **kw}
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, font=font(parent, size, weight), **kw)


def entry(parent, var, show=None, width=40):
    return tk.Entry(
        parent, textvariable=var, show=show or "", width=width, relief="flat", bg=INPUT, fg=TEXT,
        insertbackground=TEXT, selectbackground=ACCENT, font=font(parent, 11), highlightthickness=1,
        highlightbackground=BORDER, highlightcolor=ACCENT,
    )


def link(parent, text, url):
    import webbrowser

    w = label(parent, text, size=10, color=ACCENT_HOVER, cursor="hand2")
    w.bind("<Button-1>", lambda e: webbrowser.open(url))
    return w


def keycap(parent, text, size=10):
    """A key-shaped label, e.g. for 'Ctrl+Shift+Q'."""
    return tk.Label(parent, text=text, bg=INPUT, fg=TEXT, font=font(parent, size, "bold"), padx=10, pady=3,
                    highlightthickness=1, highlightbackground=BORDER)


def pick_screen_color(parent, on_done):
    """Freeze the screen, let the user click any pixel, then call on_done('#rrggbb'), or on_done(None)
    for Esc / right-click. A magnifier follows the mouse.

    Captures the main screen. macOS needs the Screen Recording permission, otherwise it shows only the
    wallpaper.
    """
    from PIL import Image, ImageGrab, ImageTk

    shot = ImageGrab.grab().convert("RGB")
    top = tk.Toplevel(parent)
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
    top.geometry(f"{sw}x{sh}+0+0")
    scale_x, scale_y = shot.width / sw, shot.height / sh  # Retina screenshots have 2 pixels per point
    shown = shot if shot.size == (sw, sh) else shot.resize((sw, sh), Image.LANCZOS)
    top._photo = ImageTk.PhotoImage(shown)
    c = tk.Canvas(top, width=sw, height=sh, highlightthickness=0, bd=0, cursor="crosshair")
    c.pack()
    c.create_image(0, 0, image=top._photo, anchor="nw", tags="shot")
    hint = "Click to pick a color  ·  Esc to cancel"
    c.create_rectangle(0, 0, 0, 0, fill="#111318", outline=BORDER, tags="hintbg")
    c.create_text(sw / 2, 28, text=hint, fill="white", font=font(parent, 12, "bold"), tags="hint")
    x1, y1, x2, y2 = c.bbox("hint")
    c.coords("hintbg", x1 - 14, y1 - 6, x2 + 14, y2 + 6)
    zoom, cells = 12, 11  # magnifier: 11x11 pixels shown 12x larger

    def pixel_at(event):
        x = event.x_root - top.winfo_rootx()
        y = event.y_root - top.winfo_rooty()
        px = min(shot.width - 1, max(0, int(x * scale_x)))
        py = min(shot.height - 1, max(0, int(y * scale_y)))
        return x, y, px, py

    def move(event):
        x, y, px, py = pixel_at(event)
        half = cells // 2
        crop = shot.crop((px - half, py - half, px + half + 1, py + half + 1))
        top._loupe = ImageTk.PhotoImage(crop.resize((cells * zoom, cells * zoom), Image.NEAREST))
        color = "#%02x%02x%02x" % shot.getpixel((px, py))
        size = cells * zoom
        lx = x + 24 if x + 24 + size < sw else x - 24 - size
        ly = y + 24 if y + 24 + size + 34 < sh else y - 24 - size - 34
        c.delete("loupe")
        c.create_rectangle(lx - 3, ly - 3, lx + size + 3, ly + size + 37, fill="#111318", outline="white",
                           width=1, tags="loupe")
        c.create_image(lx, ly, image=top._loupe, anchor="nw", tags="loupe")
        m = lx + half * zoom
        n = ly + half * zoom
        c.create_rectangle(m, n, m + zoom, n + zoom, outline="white", width=2, tags="loupe")
        c.create_rectangle(lx + 6, ly + size + 9, lx + 26, ly + size + 29, fill=color, outline="white",
                           tags="loupe")
        c.create_text(lx + 36, ly + size + 19, text=color.upper(), fill="white", anchor="w",
                      font=font(parent, 11, "bold"), tags="loupe")

    def finish(color):
        top.destroy()
        on_done(color)

    def click(event):
        _, _, px, py = pixel_at(event)
        finish("#%02x%02x%02x" % shot.getpixel((px, py)))

    c.bind("<Motion>", move)
    c.bind("<ButtonRelease-1>", click)
    c.bind("<Button-3>", lambda e: finish(None))
    c.bind("<Button-2>", lambda e: finish(None))  # right-click on some macOS setups
    top.bind("<Escape>", lambda e: finish(None))
    bring_to_front(top)
    c.focus_set()


def reveal(path):
    """Show a file in Explorer / Finder with it selected."""
    import subprocess

    if sys.platform == "win32":
        subprocess.Popen(f'explorer /select,"{path}"')  # explorer needs the quotes after the comma
    elif IS_MAC:
        subprocess.Popen(["open", "-R", str(path)])


def notice(root, title, heading, body, buttons, on_close):
    """A small dark window with a heading, text and buttons [(text, command, kind)]. Closing it calls
    on_close."""
    win = tk.Toplevel(root, bg=BG, padx=32, pady=28)
    win.title(title)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.protocol("WM_DELETE_WINDOW", on_close)
    set_window_icon(win)
    dark_title_bar(win)
    label(win, heading, 16, weight="bold").pack(anchor="w")
    label(win, body, 10, MUTED, wraplength=460).pack(anchor="w", pady=(8, 20))
    row = tk.Frame(win, bg=BG)
    row.pack(anchor="e")
    for text, command, kind in buttons:
        Button(row, text, command, kind).pack(side="left", padx=(8, 0))
    win.update_idletasks()
    x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
    y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
    win.geometry(f"+{x}+{y}")
    bring_to_front(win)
    fade_in(win)
    return win
