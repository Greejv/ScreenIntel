"""The first-launch welcome: a short animated tour that explains the app and asks for the API key."""

import math
import sys
import tkinter as tk
import webbrowser

import settings
import ui

IS_MAC = sys.platform == "darwin"
MAC_PRIVACY = "x-apple.systempreferences:com.apple.preference.security?Privacy_"


class WelcomeWindow:
    """Step-by-step onboarding. Calls on_finish(api_key) once when finished or closed ("" if no key)."""

    WIDTH, HEIGHT, FOOTER = 700, 500, 76

    def __init__(self, root, current, on_finish):
        self._on_finish = on_finish
        self._shortcuts = current["shortcuts"]
        self.key = tk.StringVar(value=current["api_key"] or "")
        self.win = tk.Toplevel(root, bg=ui.BG)
        self.win.title("Welcome to Screen Intel")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        self.win.protocol("WM_DELETE_WINDOW", self.finish)
        ui.set_window_icon(self.win)
        ui.dark_title_bar(self.win)
        x = (self.win.winfo_screenwidth() - self.WIDTH) // 2
        y = (self.win.winfo_screenheight() - self.HEIGHT) // 3
        self.win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self.steps = [self._step_welcome, self._step_how, self._step_key]
        if IS_MAC:
            self.steps.append(self._step_permissions)
        self.steps += [self._step_shortcuts, self._step_done]
        self.index, self.page, self._busy = 0, None, False

        self.stage = tk.Frame(self.win, bg=ui.BG)
        self.stage.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT - self.FOOTER)
        self._build_footer()
        self._go(0, direction=0)
        self.key.trace_add("write", lambda *a: self._update_buttons())

        self.win.bind("<Return>", lambda e: self.next())
        self.win.bind("<Escape>", lambda e: self.finish())
        ui.bring_to_front(self.win)
        ui.fade_in(self.win, 400)

    def label(self, combo_action):
        return settings.shortcut_label(self._shortcuts[combo_action])

    # Navigation

    def _build_footer(self):
        foot = tk.Frame(self.win, bg=ui.BG)
        foot.place(x=0, y=self.HEIGHT - self.FOOTER, width=self.WIDTH, height=self.FOOTER)
        self.dots = tk.Canvas(foot, width=200, height=20, bg=ui.BG, highlightthickness=0)
        self.dots.pack(side="left", padx=32)
        self.next_btn = ui.Button(foot, "Next", self.next, "primary", width=170, height=40, size=11)
        self.next_btn.pack(side="right", padx=(8, 32))
        self.back_btn = ui.Button(foot, "Back", self.back, "ghost", width=80, height=40, size=11)
        self.back_btn.pack(side="right")
        self._dot_pos = 0.0

    def _draw_dots(self, pos):
        """pos is the (animated, fractional) current step; the active dot stretches into a pill."""
        c = self.dots
        c.delete("all")
        x = 2
        for i in range(len(self.steps)):
            active = max(0.0, 1 - abs(pos - i))
            w = 8 + 18 * active
            ui.rounded_rect(c, x, 6, x + w, 14, 4, fill=ui.mix(ui.BORDER, ui.ACCENT, active), outline="")
            x += w + 8

    def _update_buttons(self):
        last = self.index == len(self.steps) - 1
        text = "Start using it" if last else "Get started" if self.index == 0 else "Continue"
        if self.steps[self.index] == self._step_key and not self.key.get().strip():
            text = "Skip for now"
        self.next_btn.set_text(text)
        self.back_btn.set_enabled(self.index > 0)
        self.back_btn.set_text("Back" if self.index > 0 else "")

    def next(self):
        if self.index == len(self.steps) - 1:
            self.finish()
        else:
            self._go(self.index + 1, direction=1)

    def back(self):
        if self.index > 0:
            self._go(self.index - 1, direction=-1)

    def _go(self, index, direction):
        """Slide the current step out and the next one in (direction 1 = forward, -1 = back)."""
        if self._busy:
            return
        old, start = self.page, self._dot_pos
        self.index = index
        self.page = tk.Frame(self.stage, bg=ui.BG)
        self.steps[index](self.page)
        self._update_buttons()
        w, h = self.WIDTH, self.HEIGHT - self.FOOTER
        if not direction:
            self.page.place(x=0, y=0, width=w, height=h)
            self._dot_pos = index
            self._draw_dots(index)
            return
        self._busy = True

        def step(t):
            if old is not None and old.winfo_exists():
                old.place(x=round(-direction * w * t), y=0, width=w, height=h)
            self.page.place(x=round(direction * w * (1 - t)), y=0, width=w, height=h)
            self._dot_pos = start + (index - start) * t
            self._draw_dots(self._dot_pos)

        def done():
            if old is not None:
                old.destroy()
            self._busy = False

        ui.animate(self.page, 340, step, done)

    def finish(self):
        if not self.win.winfo_exists():
            return
        key = self.key.get().strip()
        self.win.destroy()
        self._on_finish(key)

    # Steps

    def _title(self, page, title, subtitle, top=34):
        ui.label(page, title, 22, weight="bold").pack(pady=(top, 6))
        ui.label(page, subtitle, 11, ui.MUTED, wraplength=540, justify="center").pack()

    def _rise(self, widgets, page, delay=120):
        """Make widgets drift up into place one after another."""
        for i, w in enumerate(widgets):
            info = w.place_info()
            y0 = int(info["y"])
            w.place(y=y0 + 30)
            page.after(delay + i * 90, lambda w=w, y0=y0: ui.animate(
                w, 380, lambda t, w=w, y0=y0: w.place(y=round(y0 + 30 * (1 - t)))
            ))

    def _step_welcome(self, page):
        from PIL import ImageTk

        c = tk.Canvas(page, width=220, height=200, bg=ui.BG, highlightthickness=0)
        c.pack(pady=(26, 0))
        page._icon = ImageTk.PhotoImage(ui.app_icon(96))
        c.create_image(110, 100, image=page._icon, tags="icon")

        def pulse(phase=0.0):
            if not c.winfo_exists():
                return
            c.delete("ring")
            for k in range(3):  # three rings expanding outward and fading
                t = (phase + k / 3) % 1
                r = 52 + 46 * t
                color = ui.mix(ui.ACCENT if k % 2 == 0 else ui.ACCENT_2, ui.BG, t)
                c.create_oval(110 - r, 100 - r, 110 + r, 100 + r, outline=color, width=2, tags="ring")
            c.tag_raise("icon")
            c.coords("icon", 110, 100 + 4 * math.sin(phase * 2 * math.pi))  # gentle float
            c.after(30, pulse, (phase + 0.008) % 1)

        pulse()
        ui.label(page, "Welcome to Screen Intel", 26, weight="bold").pack(pady=(6, 8))
        ui.label(page, "The answer to the question on your screen, one shortcut away.", 12, ui.MUTED).pack()

    def _step_how(self, page):
        self._title(page, "How it works", "Three steps, about three seconds.")
        cards = []
        items = (
            ("1", "Press " + self.label("capture"), "when a quiz question is on your screen."),
            ("2", "Gemini reads it", "Your screen goes to Google Gemini, which ignores everything "
             "except the question."),
            ("3", "See the answer", "The shortest answer floats on top of everything. Just the text, "
             "no window."),
        )
        for i, (num, head, text) in enumerate(items):
            box = ui.card(page, padding=18)
            box.place(x=40 + i * 210, y=130, width=196, height=200)
            c = box.inner
            badge = tk.Canvas(c, width=40, height=40, bg=ui.CARD, highlightthickness=0)
            badge.pack(anchor="w")
            badge.create_oval(2, 2, 38, 38, fill=ui.mix(ui.ACCENT, ui.ACCENT_2, i / 2), outline="")
            badge.create_text(20, 20, text=num, fill="white", font=ui.font(c, 13, "bold"))
            ui.label(c, head, 12, weight="bold").pack(anchor="w", pady=(12, 4))
            ui.label(c, text, 10, ui.MUTED, wraplength=158).pack(anchor="w")
            cards.append(box)
        self._rise(cards, page)

    def _step_key(self, page):
        self._title(page, "Connect Google Gemini", "Screen Intel uses your own free Gemini API key. "
                    "It is saved only on this computer.")
        box = ui.card(page, padding=22)
        box.place(x=110, y=140, width=480)
        c = box.inner
        for n, text in enumerate(("Open Google AI Studio and sign in", "Click Create API key, then Copy",
                                  "Paste it below"), start=1):
            row = tk.Frame(c, bg=ui.CARD)
            row.pack(anchor="w", pady=2)
            ui.label(row, f"{n}", 10, ui.ACCENT_HOVER, "bold", width=2).pack(side="left")
            ui.label(row, text, 10).pack(side="left")
        ui.link(c, "Open Google AI Studio  ↗", settings.KEY_URL).pack(anchor="w", pady=(6, 12))
        field = ui.entry(c, self.key, show="•", width=44)
        field.pack(fill="x", ipady=7)
        field.focus_set()
        self._rise([box], page, delay=60)

    def _step_permissions(self, page):
        self._title(page, "Two macOS permissions", "macOS asks you to allow these once. Without them "
                    "the app sees only your wallpaper and the shortcuts do nothing.")
        rows = (
            ("Screen Recording", "So Screen Intel can see the question.", "ScreenCapture"),
            ("Accessibility", "So your shortcuts work in every app.", "Accessibility"),
        )
        boxes = []
        for i, (head, text, pane) in enumerate(rows):
            box = ui.card(page, padding=18)
            box.place(x=110, y=150 + i * 96, width=480, height=84)
            c = box.inner
            ui.Button(c, "Open settings", lambda p=pane: webbrowser.open(MAC_PRIVACY + p), "secondary").pack(
                side="right"
            )
            ui.label(c, head, 12, weight="bold").pack(anchor="w")
            ui.label(c, text, 10, ui.MUTED).pack(anchor="w")
            boxes.append(box)
        restart = self.label("restart")
        note = f"Turn on ScreenIntel in both, then restart the app with {restart}."
        ui.label(page, note, 10, ui.MUTED).place(x=110, y=350)
        self._rise(boxes, page)

    def _step_shortcuts(self, page):
        self._title(page, "Your shortcuts", "They work in any app. Change them any time in Settings.", top=28)
        box = ui.card(page, padding=18)
        box.place(x=130, y=112, width=440)
        rows = (
            ("capture", "Answer"), ("capture_detailed", "Answer + explanation"),
            ("capture_formula", "Just the formula"), ("capture_steps", "Step by step"),
            ("toggle", "Show / hide the answer"), ("bigger", "Bigger text"), ("smaller", "Smaller text"),
            ("quit", "Turn off"),
        )
        for action, text in rows:
            row = tk.Frame(box.inner, bg=ui.CARD)
            row.pack(fill="x", pady=2)
            ui.label(row, text, 10).pack(side="left")
            ui.keycap(row, self.label(action)).pack(side="right")
        self._rise([box], page, delay=60)

    def _step_done(self, page):
        self._title(page, "You're all set", "Screen Intel now runs quietly in the background.")
        c = tk.Canvas(page, width=480, height=150, bg=ui.BG, highlightthickness=0)
        c.place(x=110, y=126)
        # A sketch of the menu bar (macOS) or taskbar tray (Windows) with the app's icon pulsing.
        y = 18 if IS_MAC else 104
        ui.rounded_rect(c, 0, y, 480, y + 34, 10, fill=ui.CARD, outline=ui.BORDER)
        for i in range(4):
            c.create_oval(330 + i * 34, y + 11, 342 + i * 34, y + 23, fill=ui.BORDER, outline="")
        from PIL import ImageTk

        page._icon = ImageTk.PhotoImage(ui.app_icon(20))
        ix, iy = 300, y + 17
        c.create_image(ix, iy, image=page._icon, tags="icon")
        where = "in the menu bar" if IS_MAC else "in the system tray"
        text_y = y + 72 if IS_MAC else y - 50
        c.create_text(240, text_y, text=f"Find Screen Intel {where}: Show / hide, Settings, Quit.",
                      fill=ui.TEXT, font=ui.font(c, 11))

        def pulse(phase=0.0):
            if not c.winfo_exists():
                return
            c.delete("ring")
            r = 12 + 10 * phase
            c.create_oval(ix - r, iy - r, ix + r, iy + r, outline=ui.mix(ui.ACCENT_2, ui.CARD, phase),
                          width=2, tags="ring")
            c.after(30, pulse, (phase + 0.025) % 1)

        pulse()
        tip = ui.label(page, f"Open a quiz and press {self.label('capture')}.", 13, weight="bold")
        tip.place(relx=0.5, y=310, anchor="n")
