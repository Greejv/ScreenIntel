# Roadmap

What's planned next, roughly in priority order. Open an issue to discuss anything here before starting larger work.

## Now: confirm v1 works for real users

- [ ] Test the macOS build on a real Mac (shortcuts, transparency, permissions flow). CI only proves it launches.
- [ ] Try the prompt on a wide range of real quiz sites and collect cases where answers are wrong or too long; tune `ai.PROMPT`.
- [ ] Update GitHub Actions to Node 24 versions (`actions/checkout`, `setup-python`, artifact actions) before the Node 20 deprecation bites.

## Next: quality of life

- [ ] **Change the API key from the app** (tray menu item) instead of deleting the settings file.
- [ ] **Remember overlay position and text size** between launches (store next to the key in the per-user `.env`).
- [ ] **Customizable shortcuts** in the same settings file, for people whose shortcuts clash with other apps.
- [ ] **Faster startup on Windows**: ship a `--onedir` zip alongside the one-file exe.
- [ ] **Monitor choice**: capture only the monitor under the mouse to send smaller images and get faster answers.
- [ ] **Menu bar icon on macOS** (needs a tray library that coexists with tk's main loop).

## Later: bigger features

- [ ] **Region select** shortcut: drag a box to capture just part of the screen.
- [ ] **Follow-up question**: a shortcut to ask "why?" about the last answer.
- [ ] **Answer history** for the session.
- [ ] **Intel Mac build** (add a `macos-13` job or a universal2 build).
- [ ] **Code signing** (Windows certificate, Apple Developer ID + notarization) to remove the SmartScreen and Gatekeeper warnings.
- [ ] **Auto-update check** against the latest GitHub release.
- [ ] **Linux support** (X11 first; Wayland screenshots and global shortcuts need portals).

## Out of scope

- Other AI providers, unless Gemini stops being viable. One provider keeps the app simple.
- Sending anything to a server other than Google's Gemini API.
