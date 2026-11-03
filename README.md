<div align="center">

# 🧠 Screen Intel

**Press one shortcut. Get the answer.**

Screen Intel looks at your screen, finds the quiz question, and shows the shortest correct answer in a small see-through overlay that floats on top of everything.

[![Build](https://github.com/Greejv/ScreenIntel/actions/workflows/build.yml/badge.svg)](https://github.com/Greejv/ScreenIntel/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/Greejv/ScreenIntel?label=download)](https://github.com/Greejv/ScreenIntel/releases/latest)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows)
![macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-000000?logo=apple)

[**⬇️ Download**](https://github.com/Greejv/ScreenIntel/releases/latest) · [Get an API key](#-step-1-get-your-free-gemini-api-key) · [Install](#-step-2-install) · [How to use](#-step-3-use-it) · [Help](#-troubleshooting) · [Developers](#-for-developers)

</div>

---

## ✨ What it does

| | |
|---|---|
| ⌨️ **One shortcut** | Press `Ctrl` + `Shift` + `Q` and the whole screen is sent to Google Gemini. |
| 🎯 **Short answers** | Just the letter, the word, or one short sentence. No explanations. |
| 👻 **Invisible window** | Only the answer text is visible. No border, no background, always on top. |
| 🧩 **Many question types** | Multiple choice, fill in the blank, dropdowns, drag and drop, matching, open questions. |
| 🧹 **Ignores clutter** | Browser tabs, taskbar and other windows around the question don't confuse it. |
| 🔒 **Your key stays with you** | Your API key is saved only on your computer. |

**Example answers:**

```
B
Paris | 1789 | Napoleon
1-C, 2-A, 3-B
Photosynthesis turns light into chemical energy.
```

---

## 🔑 Step 1: Get your free Gemini API key

Screen Intel uses Google's Gemini AI. You need your own key. It's free and takes about a minute.

1. Go to **<https://aistudio.google.com/apikey>** and sign in with your Google account.
2. Click **Create API key**.
3. Click **Copy**. Your key looks something like `AIzaSy...` (about 39 characters).
4. Keep it somewhere safe for the next step.

> [!WARNING]
> Treat your key like a password. Don't share it or post it online.

---

## 📦 Step 2: Install

### 🪟 Windows

1. Open the [**latest release**](https://github.com/Greejv/ScreenIntel/releases/latest) and download **`ScreenIntel.exe`**.
2. Move it somewhere permanent, for example a `ScreenIntel` folder in Documents.
3. Double-click **`ScreenIntel.exe`**.
4. If Windows shows **"Windows protected your PC"**, click **More info** → **Run anyway**. This appears because the app isn't code-signed.
5. A box asks for your API key. **Paste it** and click **OK**.
6. After a few seconds you'll see **"Ready. Ctrl+Shift+Q to answer."** in the top-left corner. 🎉

A blue dot appears in the system tray (bottom-right, you may need to click `^`). Right-click it to **Show / hide** or **Quit**, or press `Ctrl` + `Shift` + `X` to turn it off.

> [!TIP]
> **Start automatically with Windows:** press `Win` + `R`, type `shell:startup`, press Enter, and put a shortcut to `ScreenIntel.exe` in that folder.

### 🍎 macOS (Apple Silicon: M1, M2, M3, M4 and newer)

1. Open the [**latest release**](https://github.com/Greejv/ScreenIntel/releases/latest) and download **`ScreenIntel-mac.zip`**.
2. Double-click the zip, then drag **`ScreenIntel.app`** into your **Applications** folder.
3. The first time, **right-click** `ScreenIntel.app` → **Open** → **Open**. This is needed once because the app isn't signed by Apple.
4. Paste your API key when asked and click **OK**.
5. Give it two permissions in **System Settings** → **Privacy & Security**:
   - **Screen Recording** → turn on **ScreenIntel** (so it can see the question)
   - **Accessibility** → turn on **ScreenIntel** (so the shortcuts work)
6. **Quit and reopen** the app so the permissions take effect.

Turn it off any time with `Ctrl` + `Shift` + `X`, from the Dock icon, or with `Cmd` + `Q`.

---

## 🚀 Step 3: Use it

1. Open your quiz so the question is visible on screen.
2. Press **`Ctrl` + `Shift` + `Q`**.
3. You'll see `...` while it thinks, then the answer appears, usually within 2 to 4 seconds.

### ⌨️ Shortcuts

| Shortcut | What it does |
|:--|:--|
| `Ctrl` + `Shift` + `Q` | 📸 Read the screen and answer |
| `Ctrl` + `Shift` + `H` | 👁️ Hide / show the answer |
| `Ctrl` + `Shift` + `↑` | 🔠 Bigger text |
| `Ctrl` + `Shift` + `↓` | 🔡 Smaller text |
| `Ctrl` + `Shift` + `R` | 🔄 Restart the app (e.g. after changing your key) |
| `Ctrl` + `Shift` + `X` | ⏻ Turn the app off |

The same shortcuts work on Mac (use `Ctrl`, not `Cmd`).

### 🖱️ Moving the answer

Click directly **on the text** and drag it wherever you like. Clicks on the empty space around the text go straight through to the window behind it. On Windows, clicking the answer never takes focus away from your quiz page.

### 📖 How to read the answers

| Question type | Example answer |
|:--|:--|
| Multiple choice | `B` |
| Several correct options | `A, C` |
| Fill in the blanks / dropdowns / drag and drop | `mitochondria \| ATP` (one per blank, in order) |
| Matching / ordering | `1-C, 2-A, 3-B` |
| Open question | One short sentence |
| More than one question on screen | One numbered line per question |
| No question found | `?` |

---

## 🛠️ Troubleshooting

<details>
<summary><b>"No Gemini API key. Restart the app to enter one."</b></summary>

You closed the key box without entering a key. Press `Ctrl` + `Shift` + `R` to restart the app and enter it.
</details>

<details>
<summary><b>"Error: ... API key not valid"</b> or I want to change my key</summary>

Delete the saved settings file, then restart the app (`Ctrl` + `Shift` + `R`) and paste the new key:

- **Windows:** press `Win` + `R`, paste `%APPDATA%\ScreenIntel` and press Enter, then delete `.env`.
- **macOS:** in Finder press `Cmd` + `Shift` + `G`, paste `~/Library/Application Support/ScreenIntel` and delete `.env`. (Press `Cmd` + `Shift` + `.` to show hidden files.)
</details>

<details>
<summary><b>"Error: ... 503 / UNAVAILABLE" or "429 / RESOURCE_EXHAUSTED"</b></summary>

Google's servers are busy or you hit the free limit. The app already retries automatically. Wait a minute and press `Ctrl` + `Shift` + `Q` again.
</details>

<details>
<summary><b>"Shortcut already used by another app: ..."</b></summary>

Another program is using that shortcut. Close it (common ones: screenshot tools, game overlays, Discord) and restart Screen Intel.
</details>

<details>
<summary><b>Nothing happens when I press the shortcut (Mac)</b></summary>

Check **System Settings → Privacy & Security → Accessibility** and **Input Monitoring**, make sure **ScreenIntel** is turned on, then quit and reopen the app.
</details>

<details>
<summary><b>The answer is about the wrong thing (Mac)</b></summary>

Make sure **Screen Recording** is allowed for ScreenIntel. Without it macOS only gives the app your wallpaper. On Mac only the main display is captured, so keep the quiz on your main screen.
</details>

<details>
<summary><b>I can't see the answer text</b></summary>

Press `Ctrl` + `Shift` + `H` in case it's hidden, and `Ctrl` + `Shift` + `↑` to make it bigger. It starts in the top-left corner of the main screen.
</details>

<details>
<summary><b>The app takes a few seconds to start (Windows)</b></summary>

That's normal. The single `.exe` unpacks itself on each launch.
</details>

---

## ⚙️ Advanced

<details>
<summary><b>Where settings are stored</b></summary>

| | Location |
|---|---|
| Windows | `%APPDATA%\ScreenIntel\.env` |
| macOS | `~/Library/Application Support/ScreenIntel/.env` |

A `.env` file placed next to the app also works and takes priority. Available settings:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite   # optional, this is the default
```
</details>

<details>
<summary><b>Run from source</b></summary>

Requires Python 3.10+.

```bash
git clone https://github.com/Greejv/ScreenIntel.git
cd ScreenIntel
pip install -r requirements.txt
python main.py
```

Build the Windows `.exe` yourself with `.\build.bat` (output: `dist\ScreenIntel.exe`).

Run the tests with `pip install pytest && pytest tests`.
</details>


---

## 👩‍💻 For developers

Want to fix something or add a feature? Start here:

| Doc | What's in it |
|:--|:--|
| [Developer guide](CONTRIBUTING.md) | Setup, code guidelines, testing checklist, how to release |
| [Architecture](docs/ARCHITECTURE.md) | How the modules fit together, threading, configuration, CI |
| [Roadmap](docs/ROADMAP.md) | What's planned next |
| [CLAUDE.md](CLAUDE.md) | Instructions for AI coding assistants |

New versions are released by bumping the [`VERSION`](VERSION) file and pushing to `main`: CI tests, builds Windows and macOS, and publishes the release.

---

<div align="center">
<sub>Screen Intel sends a screenshot of your screen to Google Gemini each time you press the shortcut. Nothing is sent otherwise. Use it responsibly and follow the rules of your school or platform.</sub>
</div>
