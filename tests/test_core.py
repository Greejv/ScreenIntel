import sys
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


def test_pynput_shortcuts():
    assert hotkeys.to_pynput("ctrl+shift+q") == "<ctrl>+<shift>+q"
    assert hotkeys.to_pynput("ctrl+shift+down") == "<ctrl>+<shift>+<down>"


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

    defaults = {action: default for action, (default, _) in settings.ACTIONS.items()}
    assert settings.load() == {
        "api_key": None, "model": settings.DEFAULT_MODEL, "font_size": 14, "shortcuts": defaults
    }

    (tmp_path / "app").mkdir()
    (tmp_path / "app" / ".env").write_text("GEMINI_API_KEY=paste_your_key_here\nFONT_SIZE=999\n")
    assert settings.load()["api_key"] is None  # placeholder means no key
    assert settings.load()["font_size"] == settings.MAX_FONT

    custom = dict(defaults, capture="alt+f2")
    settings.save({"api_key": "abc", "model": "m", "font_size": 9, "shortcuts": custom})
    assert settings.load() == {"api_key": "abc", "model": "m", "font_size": 9, "shortcuts": custom}

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


def test_shortcut_text_helpers():
    import settings

    assert settings.normalize_shortcut(" Control + Shift + F5 ") == "ctrl+shift+f5"
    assert settings.normalize_shortcut("cmd+option+a") == "alt+win+a"  # canonical modifier order
    assert settings.normalize_shortcut("shift+ctrl+q") == "ctrl+shift+q"
    assert settings.shortcut_label("ctrl+shift+up") == "Ctrl+Shift+Up"
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
