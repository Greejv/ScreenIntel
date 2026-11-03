# Screen Intel

Press a shortcut and Screen Intel sends your screen to Google Gemini and shows the shortest possible answer to the quiz question on it, in a small transparent overlay that stays on top.

Works with multiple choice, fill-in-the-blank, dropdowns, drag and drop, and open questions.

## Download

Get the latest version from the [Releases page](../../releases/latest):

- **Windows:** `ScreenIntel.exe`
- **macOS (Apple Silicon):** `ScreenIntel-mac.zip`

You also need a free Gemini API key from <https://aistudio.google.com/apikey>. The app asks for it the first time it starts and remembers it.

### Windows

Run `ScreenIntel.exe`. If SmartScreen warns you, click **More info → Run anyway** (the app isn't code-signed). It takes a few seconds to start, then shows "Ready" in the top-left corner. Quit from the blue tray icon.

### macOS

1. Unzip and move `ScreenIntel.app` to Applications.
2. The app isn't signed by Apple, so the first time **right-click it → Open → Open**.
3. In **System Settings → Privacy & Security**, allow Screen Intel under **Screen Recording** and **Accessibility** (needed for the screenshot and the shortcuts), then restart the app.

Quit from the Dock icon or with Cmd+Q. On macOS only the main display is captured.

## Shortcuts

| Keys | Action |
|---|---|
| Ctrl+Shift+Q | Screenshot and answer |
| Ctrl+Shift+H | Show / hide the overlay |
| Ctrl+Shift+Up / Down | Bigger / smaller text |

Move the overlay by dragging its text.

## Settings

The key is saved in `%APPDATA%\ScreenIntel\.env` (Windows) or `~/Library/Application Support/ScreenIntel/.env` (macOS). A `.env` file next to the app also works. Optional: `GEMINI_MODEL=...` (default `gemini-3.5-flash-lite`).

## Run from source

```
pip install -r requirements.txt
python main.py
```

Windows build: `.\build.bat` → `dist\ScreenIntel.exe`.

## Releasing

Every push to `main` is tested and built on Windows and macOS. Pushing a tag like `v1.0.1` also publishes a GitHub Release with both downloads:

```
git tag v1.0.1
git push origin v1.0.1
```
