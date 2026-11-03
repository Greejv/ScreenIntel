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


def test_answer_raises_other_errors():
    a = make_answerer([Exception("400 API key not valid")])
    with pytest.raises(Exception, match="400"):
        a.answer(Image.new("RGB", (5, 5)))


def test_empty_reply_becomes_question_mark():
    assert make_answerer([mock.Mock(text=None)]).answer(Image.new("RGB", (5, 5))) == "?"
