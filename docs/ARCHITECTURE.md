# Architecture

Screen Intel is four small modules wired together by `main.py`.

```
 keyboard ──► hotkeys.py ──┐
                           │  App.events (queue.Queue)
 tray icon (Windows) ──────┼──────────────► main.App._poll()  (tk main thread, every 50 ms)
                           │                     │
 Gemini worker thread ─────┘                     ├─► overlay.Overlay   (draws the answer)
        ▲                                        │
        └──── ai.Answerer.answer(image) ◄────────┘  ImageGrab screenshot
```

## Modules

| File | Responsibility | Depends on |
|---|---|---|
| `main.py` | App lifecycle: load or ask for the API key, create the overlay, start shortcuts and tray, route events, take screenshots, run the Gemini call on a worker thread. | all modules below |
| `ai.py` | The prompt and the Gemini call. JPEG-encodes the image, retries on 503/429 with backoff, returns a stripped string (`"?"` if empty). | `google-genai`, Pillow |
| `hotkeys.py` | Global shortcuts. `WindowsHotkeys` uses Win32 `RegisterHotKey` on its own message-loop thread (no keyboard hook, so antivirus doesn't flag it). `MacHotkeys` uses `pynput.GlobalHotKeys`. `HotkeyListener` picks one per platform. | ctypes / pynput |
| `overlay.py` | Borderless, topmost, transparent tk window showing white text with a black outline. Drag by the text, font size steps, show/hide. Windows: `WS_EX_NOACTIVATE` + `WS_EX_TOOLWINDOW`, so it never takes focus and has no taskbar button. | tkinter |

## Flow of one answer

1. User presses `Ctrl+Shift+Q`. The hotkey thread puts `("capture", None)` on `App.events`.
2. `_poll` on the tk thread calls `_capture`. It ignores the press if a request is already running (`busy`), otherwise it hides the overlay text and waits `HIDE_DELAY_MS` so the old answer isn't in the screenshot.
3. `_grab_and_ask` takes the screenshot, shows `...`, and starts a worker thread.
4. The worker calls `Answerer.answer` and puts `("answer", text)` on the queue. Errors become `"Error: ..."` text.
5. `_poll` shows the text and clears `busy`.

## Threading rules

- tkinter is touched **only** on the main thread.
- Every other thread (hotkeys, tray, Gemini worker) communicates by putting `(name, value)` tuples on `App.events`.
- Unhandled exceptions in tk callbacks are shown on the overlay via `report_callback_exception`, because the packaged app has no console.

## Configuration

Read in this order (first found wins, environment variables beat files):

1. Environment variables `GEMINI_API_KEY` / `GOOGLE_API_KEY`, `GEMINI_MODEL`
2. `.env` next to the executable (or next to `main.py` when run from source)
3. Per-user file: `%APPDATA%\ScreenIntel\.env` or `~/Library/Application Support/ScreenIntel/.env`
4. Otherwise a dialog asks for the key and saves it to the per-user file.

The placeholder value from `.env.example` is treated as "no key".

## Build and release

`.github/workflows/build.yml`:

| Job | Runs on | What it does |
|---|---|---|
| `test` | Ubuntu | `ruff check`, `pytest` |
| `build` | Windows, macOS | PyInstaller build (`--onefile` exe / `--windowed` .app zipped with `ditto`), then a smoke test: launch with a dummy key and require it to still be running after 15 s. Uploads the artifact. |
| `release` | Ubuntu, pushes only | If release `v$(cat VERSION)` (or the pushed tag) doesn't exist, creates it with both files attached. |

The macOS build targets Apple Silicon (`macos-latest`) and is not code-signed or notarized.
