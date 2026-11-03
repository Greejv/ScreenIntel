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

DETAILED_PROMPT = """You are looking at a full screenshot of a computer screen.
Most of it is clutter (browser bars, tabs, taskbar, ads, other windows, menus). Ignore all of that.
Find the quiz question(s) on the screen and answer them with a short explanation.

For each question:
- First line: the answer, in the same compact form as a quiz answer (option letter, word per blank, etc.).
- Then at most 3 short sentences explaining why, or the key steps for a calculation.
No markdown, no headings, no repeating the question. Several questions: number them.
No question found: reply only "?".
"""

FORMULA_PROMPT = """You are looking at a full screenshot of a computer screen.
Most of it is clutter (browser bars, tabs, taskbar, ads, other windows, menus). Ignore all of that.
Find the calculation problem(s) on the screen (math, physics, chemistry, finance, etc.).

Reply with only the formula(s) needed to solve it, using the problem's own symbols, in plain text
(e.g. v = s / t, x = (-b ± sqrt(b^2 - 4ac)) / 2a). One formula per line, in the order they are used.
Do not plug in numbers, do not solve, no explanations, no markdown, no LaTeX.
Several problems: number them. A question that needs no formula: reply "No formula needed".
No question found: reply only "?".
"""

STEPS_PROMPT = """You are looking at a full screenshot of a computer screen.
Most of it is clutter (browser bars, tabs, taskbar, ads, other windows, menus). Ignore all of that.
Find the question(s) on the screen and show, as briefly as possible, how to get the answer.

- Numbered steps, each one short line: the formula, the numbers put in, the result.
- At most 6 steps. Last line: "Answer: ..." in compact quiz form.
- For a question that is not a calculation, give the short reasoning steps instead.
- Plain text math only (x^2, sqrt(), *, /), no markdown, no LaTeX, no repeating the question.
Several questions: handle each in turn, labelled 1), 2), ...
No question found: reply only "?".
"""

PROMPTS = {"short": PROMPT, "detailed": DETAILED_PROMPT, "formula": FORMULA_PROMPT, "steps": STEPS_PROMPT}

_BUSY_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")


class Answerer:
    def __init__(self, api_key, model):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._configs = {
            mode: types.GenerateContentConfig(system_instruction=prompt) for mode, prompt in PROMPTS.items()
        }

    def answer(self, image, mode="short", tries=4):
        """Return Gemini's reply for a PIL image. mode is a key of PROMPTS.

        Retries while the model is busy.
        """
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        contents = [types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")]

        for attempt in range(1, tries + 1):
            try:
                resp = self._client.models.generate_content(
                    model=self._model, contents=contents, config=self._configs[mode]
                )
                return (resp.text or "").strip() or "?"
            except Exception as e:
                busy = any(m in str(e) for m in _BUSY_MARKERS)
                if not busy or attempt == tries:
                    raise
                time.sleep(2**attempt)
