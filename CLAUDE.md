# CLAUDE.md

Guidance for Claude (and other AI coding agents) working in this repository. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## What this is

Screen Intel is a small desktop app for Windows and macOS. A global shortcut takes a screenshot, sends it to Google Gemini, and shows the shortest possible answer to the quiz question on screen in a transparent, always-on-top overlay. Plain Python with tkinter, about 450 lines. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing behavior.

## Commands

```bash
pip install -r requirements.txt pytest ruff   # setup
ruff check .                                  # lint (config in ruff.toml)
pytest -q tests                               # unit tests (run anywhere, no GUI or key needed)
python main.py                                # run the app (Windows or macOS only)
.\build.bat                                   # Windows: build dist\ScreenIntel.exe
```

Run `ruff check .` and `pytest -q tests` before every commit. CI runs the same plus real Windows/macOS builds.

## Rules

- **Keep it small.** No new frameworks, no config systems, no abstractions for a single use. Prefer editing an existing module over adding one.
- **Keep the module boundaries** in docs/ARCHITECTURE.md: `ai.py` knows nothing about the GUI, `hotkeys.py`, `overlay.py` and `settings.py` know nothing about Gemini, `main.py` wires them together.
- **Threads:** only the tk main thread touches tkinter. Background threads (hotkeys, Gemini call, tray) talk to it only through `App.events` (a `queue.Queue`).
- **Platform code** lives behind `sys.platform == "darwin"` checks inside `hotkeys.py`, `overlay.py` and `main.py`. Import platform-only modules (`ctypes.windll`, `pystray`, `pynput`) lazily inside those branches so tests import cleanly on Linux.
- **Answers must stay as short as possible.** Prompts live in `ai.PROMPTS` (short, detailed, formula, steps); capture shortcuts map to them via `main.CAPTURE_MODES`. Prompt changes go there; keep the per-question-type rules and update the "How to read the answers" table in README.md to match.
- **Shortcuts** are defined once in `settings.ACTIONS` (action → default, label); `main.App._handle` maps actions to behavior. Add new actions in both places.
- **Never commit API keys** or `.env` files. All settings go through `settings.load()` / `settings.save()`; add new settings there and to the Settings window.
- **The default model** is `DEFAULT_MODEL` in `settings.py`. Keep README.md and docs in sync if it changes.
- Add or update a test in `tests/` for any change to `ai.py`, `settings.load/save`, or the shortcut parsing in `hotkeys.py`. GUI code is checked by the CI smoke test (the app must start, run for 8 s, then quit cleanly).

## Releasing

Bump `VERSION` (semver, no `v`) and push to `main`. CI builds both platforms and creates release `vX.Y.Z` if it doesn't exist yet. Pushing `v*` tags also works where tag pushes are allowed.

## Gotchas

- Windows overlay transparency uses `-transparentcolor` with `KEY_COLOR`; hidden means "draw nothing", never `withdraw()` (keeps the window from stealing focus).
- macOS needs Screen Recording and Accessibility permissions; without them screenshots show only the wallpaper and shortcuts do nothing, with no error.
- `ImageGrab.grab(all_screens=True)` only covers all monitors on Windows; macOS captures the main display.
- Other windows can push a topmost window down, so `App._keep_on_top` re-raises the overlay every 250 ms, after every redraw and while dragging (`SWP_NOACTIVATE`, never steals focus). This keeps it above the Windows taskbar too.
- Restart (`Ctrl+Shift+R`) spawns a new process with `PYINSTALLER_RESET_ENVIRONMENT=1` after unregistering the shortcuts; keep that order.
- Never add services, startup entries, registry keys or files beyond the settings file. CI checks that the app quits cleanly and leaves no `_MEI` temp folder; keep `main()`'s thread join + `os._exit(0)`.
- Settings pauses the app's shortcuts while open (`App._stop_hotkeys` / `_settings_closed`); otherwise RegisterHotKey swallows the keys being recorded and `is_free` reports our own shortcuts as taken.
- Shortcut strings are always canonical (`hotkeys.canonical`: ctrl, shift, alt, win, then key) so comparisons and the `SYSTEM_SHORTCUTS` lookup work.
- The one-file Windows exe takes several seconds to start. That's PyInstaller unpacking, not a bug.
