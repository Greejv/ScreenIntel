# Developer guide

Thanks for helping with Screen Intel. This guide covers setup, conventions, and how changes get released. For how the code fits together, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first.

## Setup

Requires Python 3.10+ on Windows or macOS (tests also run on Linux).

```bash
git clone https://github.com/Greejv/ScreenIntel.git
cd ScreenIntel
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS: source .venv/bin/activate
pip install -r requirements.txt pytest ruff
cp .env.example .env                  # then paste your Gemini key into .env
python main.py
```

## Before you push

```bash
ruff check .
pytest -q tests
```

Both must pass; CI runs them on every push and pull request, then builds and launches the app on Windows and macOS.

If you changed anything visual or platform-specific, also run the app and check by hand:

- [ ] "Ready" appears in the top-left corner
- [ ] `Ctrl+Shift+Q` shows `...` and then an answer
- [ ] `Ctrl+Shift+H` hides and shows the text
- [ ] `Ctrl+Shift+Up/Down` resizes the text, down to the smallest size without vanishing
- [ ] `Ctrl+Shift+R` restarts the app (old copy gone, new one shows "Ready")
- [ ] The text can be dragged, and clicks next to it reach the window behind
- [ ] Quit works (tray icon on Windows, Cmd+Q on macOS)

## Code guidelines

- **Small and plain.** The whole app is a few hundred lines; keep it that way. Standard library + the four dependencies in `requirements.txt`. Ask before adding a dependency.
- **One job per module.** `ai.py` (Gemini), `hotkeys.py` (shortcuts), `overlay.py` (window), `main.py` (wiring). Don't let GUI code into `ai.py` or Gemini code into the GUI modules.
- **Threads talk through the queue.** Only the tk main thread touches tkinter; other threads put `(name, value)` on `App.events`.
- **Platform branches** go inside the module that needs them (`if IS_MAC:`), with platform-only imports inside the branch.
- **Readable names, short functions, comments only where the "why" isn't obvious.** Follow the existing style; `ruff` enforces the basics (line length 110).
- **Tests** for logic that runs without a screen: prompt and response handling in `ai.py`, shortcut parsing in `hotkeys.py`. Mock the Gemini client; never call the real API in tests.
- **Secrets** never go in code, commits, logs, or issues.

## Changing the AI behavior

- The prompt is `PROMPT` in `ai.py`. Keep answers as short as possible: that is the product.
- When you change answer formats, update the "How to read the answers" table in `README.md`.
- To try another model without code changes, set `GEMINI_MODEL=...` in `.env`. To change the default, edit `DEFAULT_MODEL` in `main.py` and the README.

## Commits and pull requests

- Branch from `main`, keep each PR to one change, and describe what you tested.
- Commit messages: imperative summary line under ~70 characters (`Add Linux overlay support`), then a short body if the why isn't obvious.
- CI must be green before merging.

## Releasing

1. Update `VERSION` using [semver](https://semver.org): patch for fixes (`1.0.1`), minor for features (`1.1.0`), major for breaking changes.
2. Push to `main` (or merge a PR that changes `VERSION`).
3. CI builds both platforms and publishes release `vX.Y.Z` with `ScreenIntel.exe` and `ScreenIntel-mac.zip`. Release notes are generated from merged PRs and commits.
4. Download both files from the release page and run the manual checklist above on at least one platform.

## Project docs

| File | Contents |
|---|---|
| [README.md](README.md) | User guide: download, API key, install, usage, troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, threading, configuration, CI |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Planned work and ideas |
| [CLAUDE.md](CLAUDE.md) | Instructions for AI coding agents |
