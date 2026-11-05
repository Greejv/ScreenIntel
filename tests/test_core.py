import sys
import threading
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai  # noqa: E402
import hotkeys  # noqa: E402


def test_parse_windows_shortcuts():
    assert hotkeys.parse("ctrl+shift+q") == (hotkeys.MOD_CONTROL | hotkeys.MOD_SHIFT, ord("Q"))
    assert hotkeys.parse("ctrl+shift+up") == (hotkeys.MOD_CONTROL | hotkeys.MOD_SHIFT, 0x26)
    with pytest.raises(ValueError):
        hotkeys.parse("ctrl+f13")


def test_mac_key_names():
    assert hotkeys.mac_key_name("q", 0x0C) == "q"
    assert hotkeys.mac_key_name("œ", 0x0C) == "q"  # Option+Q types œ: match by key position
    assert hotkeys.mac_key_name("\x11", 0x0C) == "q"  # Control+Q
    assert hotkeys.mac_key_name(None, 0x7E) == "up"
    assert hotkeys.mac_key_name("≠", 0x18) == "="
    assert hotkeys.mac_modifier("ctrl_l") == "ctrl" and hotkeys.mac_modifier("cmd_r") == "win"
    assert hotkeys.mac_modifier("up") is None


def make_answerer(replies):
    a = ai.Answerer("key", "model")
    a._client = mock.Mock()
    a._client.models.generate_content.side_effect = replies
    return a


def test_answer_retries_when_busy(monkeypatch):
    monkeypatch.setattr(ai.time, "sleep", lambda s: None)
    a = make_answerer([Exception("503 UNAVAILABLE"), mock.Mock(text="  B \n")])
    assert a.answer(Image.new("RGBA", (50, 50))) == "B"
    kwargs = a._client.models.generate_content.call_args.kwargs
    assert kwargs["contents"][0].inline_data.mime_type == "image/jpeg"
    assert "quiz" in kwargs["config"].system_instruction


@pytest.mark.parametrize("mode", ["short", "detailed", "formula", "steps"])
def test_each_mode_uses_its_prompt(mode):
    a = make_answerer([mock.Mock(text="v = s / t")])
    assert a.answer(Image.new("RGB", (5, 5)), mode=mode) == "v = s / t"
    config = a._client.models.generate_content.call_args.kwargs["config"]
    assert config.system_instruction == ai.PROMPTS[mode]


def test_every_capture_shortcut_has_a_prompt():
    import main
    import settings

    capture_actions = {a for a in settings.ACTIONS if a.startswith("capture")}
    assert capture_actions == set(main.CAPTURE_MODES)
    assert set(main.CAPTURE_MODES.values()) <= set(ai.PROMPTS)


def test_answer_raises_other_errors():
    a = make_answerer([Exception("400 API key not valid")])
    with pytest.raises(Exception, match="400"):
        a.answer(Image.new("RGB", (5, 5)))


def test_empty_reply_becomes_question_mark():
    assert make_answerer([mock.Mock(text=None)]).answer(Image.new("RGB", (5, 5))) == "?"


def test_settings_roundtrip(tmp_path, monkeypatch):
    import settings

    for name in settings._ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "app")
    monkeypatch.setattr(settings, "user_config_file", lambda: tmp_path / "user" / ".env")
    monkeypatch.setattr(settings, "_keyring", lambda: None)  # no credential store: key goes to the file

    defaults = {action: default for action, (default, _) in settings.ACTIONS.items()}
    fresh = {
        "api_key": None, "model": settings.DEFAULT_MODEL, "font_size": 14, "font_family": "",
        "text_color": "#ffffff", "text_outline": True, "shortcuts": defaults, "onboarded": False,
    }
    assert settings.load() == fresh

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / ".env").write_text("GEMINI_API_KEY=paste_your_key_here\nFONT_SIZE=999\n")
    assert settings.load()["api_key"] is None  # placeholder means no key
    assert settings.load()["font_size"] == settings.MAX_FONT

    custom = dict(defaults, capture="alt+f2")
    saved = dict(fresh, api_key="abc", model="m", font_size=9, font_family="Georgia", text_color="#ffd60a",
                 text_outline=False, shortcuts=custom, onboarded=True)
    settings.save(saved)
    assert settings.load() == saved

    with (tmp_path / "user" / ".env").open("a") as f:
        f.write("TEXT_COLOR=not-a-color\n")
    assert settings.load()["text_color"] == "#ffffff"

    with (tmp_path / "user" / ".env").open("a") as f:
        f.write("SHORTCUT_TOGGLE=ctrl+banana\n")  # broken by hand
    assert settings.load()["shortcuts"] == defaults

    monkeypatch.setenv("GEMINI_API_KEY", "from-env")
    assert settings.load()["api_key"] == "from-env"  # environment wins


def test_shortcut_validation():
    import settings

    good = {action: default for action, (default, _) in settings.ACTIONS.items()}
    assert settings.shortcut_errors(good) is None
    assert "valid" in settings.shortcut_errors(dict(good, capture="ctrl+shift+??"))
    assert "needs Ctrl" in settings.shortcut_errors(dict(good, capture="q"))
    assert "used twice" in settings.shortcut_errors(dict(good, capture="ctrl+shift+h"))
    system_combo = next(iter(hotkeys.SYSTEM_SHORTCUTS))
    assert "system shortcut" in settings.shortcut_errors(dict(good, capture=system_combo))
    assert all(c not in hotkeys.SYSTEM_SHORTCUTS for c in good.values())  # defaults are safe


def test_mac_defaults_avoid_macos_shortcuts():
    import settings

    defaults = settings.MAC_DEFAULTS
    assert set(defaults) == set(settings.ACTION_LABELS) == set(settings.WINDOWS_DEFAULTS)
    assert len(set(defaults.values())) == len(defaults)
    for combo in defaults.values():
        assert combo not in hotkeys._MAC_SYSTEM
        assert hotkeys.parse(combo)[0]  # valid, with a modifier
        assert "win" not in combo  # Cmd shortcuts belong to the app in front
    assert "ctrl+shift+f" in hotkeys._MAC_SYSTEM  # old Mac defaults reset to the new ones on load


def test_shortcut_text_helpers():
    import settings

    assert settings.normalize_shortcut(" Control + Shift + F5 ") == "ctrl+shift+f5"
    assert settings.normalize_shortcut("cmd+option+a") == "alt+win+a"  # canonical modifier order
    assert settings.normalize_shortcut("shift+ctrl+q") == "ctrl+shift+q"
    assert settings.shortcut_label("ctrl+shift+up", mac=False) == "Ctrl+Shift+Up"
    assert settings.shortcut_label("ctrl+alt+q", mac=True) == "⌃⌥Q"
    assert settings.shortcut_label("ctrl+shift+alt+win+up", mac=True) == "⌃⌥⇧⌘↑"
    assert settings.normalize_shortcut("Ctrl+Option+=") == "ctrl+alt+="
    assert hotkeys.parse("ctrl+alt+-") == (hotkeys.MOD_CONTROL | hotkeys.MOD_ALT, 0xBD)
    assert hotkeys.parse("alt+f12") == (hotkeys.MOD_ALT, 0x7B)


def test_recording_helpers():
    assert hotkeys.canonical({"shift", "ctrl"}, "q") == "ctrl+shift+q"
    assert hotkeys.modifier_from_keysym("Control_L") == "ctrl"
    assert hotkeys.modifier_from_keysym("q") is None
    assert hotkeys.mods_from_state(0x0004 | 0x0001) == {"ctrl", "shift"}
    if sys.platform == "win32":
        assert hotkeys.key_from_event("exclam", 0x31) == "1"  # Shift+1 still records as 1
        assert hotkeys.key_from_event("Up", 0x26) == "up"
    else:
        assert hotkeys.key_from_event("Q", 0) == "q"
        assert hotkeys.key_from_event("F5", 0) == "f5"
        assert hotkeys.key_from_event("Escape", 0) is None
        assert hotkeys.key_from_event("equal", 0) == "="
        assert hotkeys.key_from_event("underscore", 0) == "-"


def test_mac_listener_matches_by_key_and_fires_once():
    from types import SimpleNamespace as K

    hits = []
    listener = object.__new__(hotkeys.MacHotkeys)  # skip __init__, which needs pynput on a Mac
    listener._bindings, listener._held, listener._fired = {"ctrl+alt+q": lambda: hits.append(1)}, set(), set()
    ctrl, alt = K(name="ctrl_l", value=K(vk=0x3B)), K(name="alt", value=K(vk=0x3A))
    q = K(char="œ", vk=0x0C)  # Option+Q types œ
    for key in (ctrl, alt, q, q):  # the second q is key repeat
        listener._press(key)
    assert hits == [1]
    listener._release(q)
    listener._press(q)
    assert hits == [1, 1]
    listener._release(q)
    listener._release(alt)
    listener._press(q)  # Control+Q alone is not the shortcut
    assert hits == [1, 1]


def test_mac_listener_reads_keyboard_layout_on_the_calling_thread(monkeypatch):
    """pynput's Listener reads the keyboard layout on its own thread, which crashes macOS 14+."""
    import contextlib
    import types

    reads = []

    @contextlib.contextmanager
    def keycode_context():  # stands in for pynput's layout lookup
        reads.append(threading.current_thread())
        yield "layout"

    darwin = types.ModuleType("pynput.keyboard._darwin")
    darwin.keycode_context = keycode_context

    class Listener:  # stands in for pynput.keyboard.Listener on macOS, whose _run uses keycode_context
        def __init__(self, on_press, on_release):
            pass

        def _run(self):
            with darwin.keycode_context() as self.layout:
                pass

    keyboard = types.ModuleType("pynput.keyboard")
    keyboard.Listener, keyboard._darwin = Listener, darwin
    pynput = types.ModuleType("pynput")
    pynput.keyboard = keyboard
    for module in (pynput, keyboard, darwin):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    listener = hotkeys.MacHotkeys({})._listener
    thread = threading.Thread(target=listener._run)
    thread.start()
    thread.join()
    assert reads == [threading.main_thread()]
    assert listener.layout == "layout"


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def get_password(self, service, user):
        return self.store.get((service, user))

    def set_password(self, service, user, value):
        self.store[(service, user)] = value

    def delete_password(self, service, user):
        del self.store[(service, user)]


def test_key_lives_in_credential_store_and_uninstall_removes_everything(tmp_path, monkeypatch):
    import settings

    for name in settings._ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    config = tmp_path / "user" / ".env"
    monkeypatch.setattr(settings, "app_dir", lambda: tmp_path / "app")
    monkeypatch.setattr(settings, "user_config_file", lambda: config)
    fake = FakeKeyring()
    monkeypatch.setattr(settings, "_keyring", lambda: fake)

    config.parent.mkdir()
    config.write_text("GEMINI_API_KEY=old-plain-key\nFONT_SIZE=20\n")  # written by an older version
    loaded = settings.load()
    assert loaded["api_key"] == "old-plain-key"
    assert "old-plain-key" not in config.read_text()  # moved into the credential store
    assert fake.store == {(settings.KEYRING_SERVICE, settings.KEYRING_USER): "old-plain-key"}

    settings.save(dict(loaded, api_key="new-key"))
    assert "new-key" not in config.read_text()
    assert settings.load()["api_key"] == "new-key"
    if sys.platform != "win32":
        assert config.stat().st_mode & 0o077 == 0  # only the user can read it

    removed = settings.uninstall()
    assert not config.exists() and not config.parent.exists()
    assert fake.store == {}
    assert len(removed) >= 2
    assert settings.load()["api_key"] is None


def test_outline_off_uses_a_background_next_to_the_text_color(monkeypatch):
    import overlay

    monkeypatch.setattr(overlay, "IS_MAC", False)
    assert overlay.key_color("#ffffff", outline=True) == overlay.KEY_COLOR
    assert overlay.key_color("#ffffff", outline=False) == "#fefefe"
    assert overlay.key_color("#000000", outline=False) == "#010101"
    assert overlay.key_color("#ffd60a", outline=False) not in ("#ffd60a", overlay.KEY_COLOR)
