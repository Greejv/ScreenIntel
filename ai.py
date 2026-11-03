"""Send a screenshot to Gemini and get back the shortest possible answer."""

import io
import time

from google import genai
from google.genai import types

PROMPT = """You are looking at a full screenshot of a computer screen.
Most of it is clutter (browser bars, tabs, taskbar, ads, other windows, menus). Ignore all of that.
Find the quiz question(s) on the screen and answer them.

Answer as short as possible. No explanations, no repeating the question, no markdown.
- Multiple choice: give only the correct option (its letter if options are lettered, otherwise its text).
- Several correct options: list them separated by commas.
- Fill in the blank, dropdowns, drag and drop: only the word(s) for each blank, in order, separated by " | ".
- Matching / ordering: give the pairs or order as compactly as possible, e.g. 1-B, 2-A.
- Open question: the shortest correct answer, at most one sentence.
- Several questions visible: one line per question, numbered.
- No question found: reply only "?".
"""

_BUSY_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")


class Answerer:
    def __init__(self, api_key, model):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._config = types.GenerateContentConfig(system_instruction=PROMPT)

    def answer(self, image, tries=4):
        """Return Gemini's answer for a PIL image. Retries while the model is busy."""
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        contents = [types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")]

        for attempt in range(1, tries + 1):
            try:
                resp = self._client.models.generate_content(
                    model=self._model, contents=contents, config=self._config
                )
                return (resp.text or "").strip() or "?"
            except Exception as e:
                busy = any(m in str(e) for m in _BUSY_MARKERS)
                if not busy or attempt == tries:
                    raise
                time.sleep(2**attempt)
