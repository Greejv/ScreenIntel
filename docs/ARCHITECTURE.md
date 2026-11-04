# Architecture

Screen Intel is a few small modules wired together by `main.py`.

```
 keyboard ──► hotkeys.py ──┐
                           │  App.events (queue.Queue)
 tray / menu bar icon ─────┼──────────────► main.App._poll()  (tk main thread, every 50 ms)
                           │                     │
 Gemini worker thread ─────┘                     ├─► overlay.Overlay   (draws the answer)
        ▲                                        │
        └──── ai.Answerer.answer(image) ◄────────┘  ImageGrab screenshot
```

## Modules

| File | Responsibility | Depends on |
|---|---|---|
| `main.py` | App lifecycle: show the welcome tour on first launch, create the overlay, start shortcuts and the tray icon (Windows, pystray) or menu bar icon (macOS, `MacMenuBarIcon` via AppKit, which pynput already pulls in), route events, take screenshots, run the Gemini call on a worker thread. | all modules below |
| `ai.py` | The prompt and the Gemini call. JPEG-encodes the image, retries on 503/429 with backoff, returns a stripped string (`"?"` if empty). | `google-genai`, Pillow |
| `hotkeys.py` | Global shortcuts. `WindowsHotkeys` uses Win32 `RegisterHotKey` on its own message-loop thread (no keyboard hook, so antivirus doesn't flag it). `MacHotkeys` uses a `pynput.keyboard.Listener` and matches keys by position (`mac_key_name`), because Option changes the typed character (Option+Q is "œ"). `HotkeyListener` picks one per platform. | ctypes / pynput |
| `settings.py` | Where settings live (`load`, `save`, per-user file path) and the Settings window (sidebar pages General, Appearance, Shortcuts, Background). `ACTIONS` lists every shortcut action with its default for this platform (`WINDOWS_DEFAULTS` / `MAC_DEFAULTS`). Opened from the tray / menu bar icon, or the macOS app menu / Dock icon. | tkinter, python-dotenv, keyring, `ui`, `overlay` (font list) |
| `welcome.py` | The first-launch tour: animated step screens (welcome, how it works, API key, macOS permissions, shortcuts, where the app lives). Calls back with the key; `main` saves it with `ONBOARDED=1`. | tkinter, `ui`, `settings` |
| `ui.py` | The shared look of Settings and the tour: dark theme colors, rounded `Button`, cards, `animate`/`fade_in`, the app icon (drawn with Pillow, also used for the tray), `bring_to_front`, and `pick_screen_color` (freezes the main screen, shows a magnifier, returns the clicked pixel). Plain tk widgets, because ttk ignores colors on macOS. | tkinter, Pillow |
| `overlay.py` | Borderless, topmost, transparent tk window showing the answer in the chosen font and color (default: white, system UI font, i.e. Segoe UI Variable on Windows 11 and SF Pro on macOS). `FONT_CHOICES` lists the extra fonts offered in Settings. Drag by the text, font size steps, show/hide. Windows: `WS_EX_NOACTIVATE` + `WS_EX_TOOLWINDOW`, so it never takes focus and has no taskbar button. | tkinter |

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

## Shutdown

`App.quit` stops the shortcuts and tray icon and destroys the tk root. `main()` then joins any non-daemon threads for up to 2 s and calls `os._exit(0)`, so nothing can keep the process alive after the user turns it off. The app creates no services, startup entries or files other than the settings file and the API key's entry in the credential store. `settings.uninstall()` (Settings → Background → Uninstall) removes both, plus what macOS keeps for the app (preferences, saved window state, privacy permissions via `tccutil reset`), and then `App.uninstall` shows the user where the .exe / .app is so they can delete it.

## Configuration

`settings.load()` merges, highest priority first:

1. Environment variables `GEMINI_API_KEY` / `GOOGLE_API_KEY`, `GEMINI_MODEL`, `FONT_SIZE`, `FONT_FAMILY`, `TEXT_COLOR`, `TEXT_OUTLINE`, `ONBOARDED`
2. The API key from the OS credential store via `keyring` (Windows Credential Manager / macOS Keychain, service `ScreenIntel`). `save()` writes the key there and leaves it blank in the file; `load()` moves a key left in the file by an older version into the store. Without a store the key stays in the file. On macOS the settings folder and file are chmod 700 / 600.
3. Per-user file written by the Settings window: `%APPDATA%\ScreenIntel\.env` or `~/Library/Application Support/ScreenIntel/.env`
4. `.env` next to the executable (or next to `main.py` when run from source)

On first launch (no `ONBOARDED=1`) the welcome tour opens. Later, with no key, the app starts anyway, shows a hint on the overlay and opens the Settings window. Saving applies immediately (`App._apply_settings` rebuilds the `Answerer`, resizes the text and re-registers changed shortcuts). Shortcuts are recorded by pressing them (`settings.ShortcutField` decodes tk key events with `hotkeys.mods_from_state` / `key_from_event`), checked against `hotkeys.SYSTEM_SHORTCUTS` and, on Windows, `hotkeys.is_free` (a test `RegisterHotKey`). The app pauses its own shortcuts while Settings is open and re-registers them when it closes. They are stored as `SHORTCUT_<ACTION>=ctrl+shift+q` in canonical modifier order (ctrl, shift, alt, win); if a hand-edited file has an invalid or duplicate one, all shortcuts fall back to the defaults. The placeholder value from `.env.example` is treated as "no key".

## Build and release

`.github/workflows/build.yml`:

| Job | Runs on | What it does |
|---|---|---|
| `test` | Ubuntu | `ruff check`, `pytest` |
| `build` | Windows, macOS | PyInstaller build (`--onefile` exe / `--windowed` .app zipped with `ditto`), then a smoke test: launch with a dummy key, require it to be running after 8 s, let it quit itself via `SCREENINTEL_QUIT_AFTER_MS`, and require exit code 0, no leftover process and (Windows) no leftover `_MEI` temp folder. Uploads the artifact. |
| `release` | Ubuntu, pushes only | If release `v$(cat VERSION)` (or the pushed tag) doesn't exist, creates it with both files attached. |

The macOS build targets Apple Silicon (`macos-latest`) and is not code-signed or notarized.
