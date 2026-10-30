"""One client to Nemotron over an API, in two roles: the LLM that writes, and the decision model.

**As an LLM** — `say` and `json`: an answer in words, thinking on, with room to think. A reasoning
model thinks inside the budget it answers in, so an answer cut off with nothing said raises
`CutOff` instead of coming back as an empty string that reads like "no opinion".

**As a decision model** — `noul`, `tfu`, `choice`, `scale`, and `ask` in Jev's request shape.
A generative model asked "A or B?" writes a letter. Ask it for one token with thinking off and
read the log-probabilities of that token instead, and you have a number per option from one
forward pass — the reading a decision model makes, from the same weights that write prose.
Three things make the number worth having:

- **Both orders.** The model leans towards the letter in first place (it wins 75–79% of the time
  where it should win half), so each question is read with its options as given and reversed and
  the two log-probabilities of each option averaged: the lean cancels instead of deciding.
- **A temperature per mode**, fitted on labelled public rows and shipped in `decision.json`
  with the model it was fitted for: it changes no ordering, only whether 0.8 means right four
  times in five.
- **A third answer.** `tfu` reads the same question over three options — the two criteria and
  "the text does not settle it".
"""
from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MODEL = os.environ.get("TERRAWEAVER_DECISION", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
TOKEN_FACTORY = "https://api.tokenfactory.nebius.com/v1/"
CALIBRATION = Path(__file__).with_name("decision.json")
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"
UNSETTLED = "neither — the text does not settle it"
SYSTEM = ("You answer a closed question about a text. Reply with the letter of exactly one "
          "option and nothing else.")
# A mark the model gave no weight among its top twenty is not impossible, only unlikely: it sits
# this far below the least likely mark that was seen, so a temperature can still move it.
UNSEEN = 4.0


def _spent(model: str, answer) -> None:
    """Every call's tokens, to the file `TERRAWEAVER_USAGE` names, with the memory's step that made
    it: what costs is read off a run instead of guessed."""
    path = os.environ.get("TERRAWEAVER_USAGE")
    usage = getattr(answer, "usage", None)
    if not path or usage is None:
        return
    import sys
    frame, step = sys._getframe(2), "?"
    while frame is not None:
        name = frame.f_code.co_filename
        if "/memory/" in name and not name.endswith(("nemotron.py", "models.py")):
            step = f"{Path(name).stem}.{frame.f_code.co_name}"
            break
        frame = frame.f_back
    details = getattr(usage, "completion_tokens_details", None)
    line = {"model": model.split("/")[-1], "step": step, "in": usage.prompt_tokens,
            "out": usage.completion_tokens, "thought": getattr(details, "reasoning_tokens", None)}
    with open(path, "a") as file:
        file.write(json.dumps(line) + "\n")


def softmax(logits: dict, temperature: float = 1.0) -> dict:
    top = max(logits.values())
    weights = {k: math.exp((v - top) / temperature) for k, v in logits.items()}
    total = sum(weights.values())
    return {k: w / total for k, w in weights.items()}


def fitted_for(path: Path, model: str) -> dict:
    """The per-mode calibration at `path` fitted for `model`; nothing for a model not fitted there.

    One entry per model (`{"models": {id: {"calibration": ...}}}`): another model's confidence is on
    another scale, so its temperature is noise here. Any Nemotron can be used; one with no entry reads
    both orders at temperature 1 until `experiments/09_decision` fits it.
    """
    shipped = json.loads(Path(path).read_text()) if Path(path).exists() else {}
    return (shipped.get("models") or {}).get(model, {}).get("calibration", {})


class CutOff(RuntimeError):
    """The model spent the whole budget thinking and said nothing: give it room, not another try."""


def messages(state: str, question: str, options: list[str], marks: str = LETTERS) -> list[dict]:
    """The chat a closed question is put as, options marked in the order given."""
    shown = "\n".join(f"{marks[i]}) {text}" for i, text in enumerate(options))
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{state}\n\nQuestion: {question}\n{shown}\n\n"
                                        f"Answer with one {'digit' if marks == DIGITS else 'letter'}."}]


class Nemotron:
    """One model behind an OpenAI-compatible endpoint, as an LLM and as a decision model.

    Nebius Token Factory by default (`NEBIUS_API_KEY`); any server that serves the same weights
    with `logprobs` and `top_logprobs` — vLLM, SGLang, llama-server — through `base_url`.
    `calibration`: the shipped file (default), a dict `{mode: {"temperature", "orders"}}`, or
    False for raw readings at temperature 1, both orders.
    """

    def __init__(self, model: str = MODEL, base_url: str = TOKEN_FACTORY, api_key: str | None = None,
                 calibration: Path | dict | bool = CALIBRATION, timeout: float = 60.0, workers: int = 8,
                 client=None):
        if client is None:
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key or os.environ["NEBIUS_API_KEY"],
                            timeout=timeout, max_retries=3)
        self.client, self.model, self.workers = client, model, workers
        if isinstance(calibration, (str, Path)):
            calibration = fitted_for(Path(calibration), model)
        self.calibration = calibration if isinstance(calibration, dict) else {}

    # --- as an LLM ----------------------------------------------------------------------------

    # Measured on Nano-30B-A3B: 3000 tokens came back cut off with nothing said and 8000 finished
    # the same question; over 25 readings 8000 still lost one. The cliff is per question.
    ROOM = 16000

    def say(self, system: str, prompt: str, room: int | None = None, thinking: bool = True) -> str:
        """An answer in words. Raises `CutOff` when the budget went on thinking and nothing was said."""
        room = room or self.ROOM
        answer = self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=room,
            extra_body={"chat_template_kwargs": {"enable_thinking": thinking}},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": [{"type": "text", "text": prompt}]}])
        _spent(self.model, answer)
        choice = answer.choices[0]
        said = choice.message.content or ""
        if not said.strip() and choice.finish_reason == "length":
            used = getattr(answer.usage, "completion_tokens", room)
            raise CutOff(f"cut off after {used} tokens with nothing said — it spent the whole budget "
                         f"thinking. Give it room: room={max(room * 2, 8000)}.")
        return said

    def json(self, system: str, prompt: str, room: int | None = None) -> dict | None:
        """The same, where the answer is meant to be a JSON object. None when none came back."""
        said = self.say(system, prompt, room) or ""
        start, end = said.find("{"), said.rfind("}")
        if start < 0 or end < start:
            return None
        try:
            return json.loads(said[start:end + 1])
        except ValueError:
            return None

    # --- as a decision model ------------------------------------------------------------------

    def marks(self, state: str, question: str, options: list[str], marks: str = LETTERS) -> dict:
        """The log-probability of each option's mark as the first token of the answer."""
        answer = self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=1, logprobs=True, top_logprobs=20,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            messages=messages(state, question, options, marks))
        _spent(self.model, answer)
        content = answer.choices[0].logprobs.content if answer.choices[0].logprobs else None
        allowed = set(marks[:len(options)])
        seen: dict[str, float] = {}
        for top in (content[0].top_logprobs if content else []):
            mark = top.token.strip().strip(")").upper()
            if len(mark) == 1 and mark in allowed:
                seen[mark] = max(seen.get(mark, -1e9), top.logprob)
        if not seen:
            raise RuntimeError(f"no option mark among the answer's first tokens ({self.model})")
        floor = min(seen.values()) - UNSEEN
        return {marks[i]: seen.get(marks[i], floor) for i in range(len(options))}

    def logits(self, mode: str, state: str, question: str, names: list, texts: list,
               marks: str = LETTERS) -> dict:
        """Each option's log-probability, averaged over the orders the mode is read in."""
        orders = self._fitted(mode)["orders"]
        ways = [list(range(len(names)))]
        if orders > 1:
            ways.append(ways[0][::-1])
        total = {name: 0.0 for name in names}
        for way in ways:
            raw = self.marks(state, question, [texts[i] for i in way], marks)
            for k, i in enumerate(way):
                total[names[i]] += raw[marks[k]] / len(ways)
        return total

    def _fitted(self, mode: str) -> dict:
        return {"temperature": 1.0, "orders": 2, **self.calibration.get(mode, {})}

    def _p(self, mode: str, logits: dict) -> dict:
        return softmax(logits, self._fitted(mode)["temperature"])

    # --- the four modes -----------------------------------------------------------------------

    def noul(self, state: str, question: str, true: str, false: str) -> dict:
        """Yes or no, two criteria: {"p": {"yes", "no"}, "logits"}."""
        z = self.logits("noul", state, question, ["true", "false"], [true, false])
        p = self._p("noul", z)
        return {"p": {"yes": p["true"], "no": p["false"]}, "logits": z}

    def tfu(self, state: str, question: str, true: str, false: str) -> dict:
        """The same question over three answers: {"p": {"true", "false", "unsure"}, "verdict", "logits"}."""
        z = self.logits("tfu", state, question, ["true", "false", "unsure"], [true, false, UNSETTLED])
        p = self._p("tfu", z)
        return {"p": p, "verdict": max(p, key=p.get), "logits": z}

    def choice(self, state: str, question: str, options: list[tuple[str, str]]) -> dict:
        """One of 2–26 options, exactly one right: {"p": {name: ...}, "choice", "logits"}."""
        if not 2 <= len(options) <= len(LETTERS):
            raise ValueError(f"2 to {len(LETTERS)} options, got {len(options)}")
        z = self.logits("choice", state, question, [n for n, _ in options], [t for _, t in options])
        p = self._p("choice", z)
        return {"p": p, "choice": max(p, key=p.get), "logits": z}

    def scale(self, state: str, question: str, levels: list[tuple[str, str]]) -> dict:
        """A level on an ordinal rubric of up to ten levels, marked with digits: {"p", "choice", "logits"}."""
        if not 2 <= len(levels) <= len(DIGITS):
            raise ValueError(f"2 to {len(DIGITS)} levels, got {len(levels)}")
        z = self.logits("scale", state, question, [n for n, _ in levels], [t for _, t in levels], DIGITS)
        p = self._p("scale", z)
        return {"p": p, "choice": max(p, key=p.get), "logits": z}

    # --- several questions, in the Jev shape --------------------------------------------------

    def answer(self, state: str, asked: dict) -> dict:
        """One question in the Jev request shape — {"type", "instructions", "criteria"} — answered
        with Jev's fields: `noul` → {"noul"}, `tfu` → {"noul", "unsure", "probabilities"},
        `choice`/`scale` → {"probabilities", "choice"}; `logits` on every one."""
        kind, question = asked.get("type", "noul"), asked.get("instructions", "")
        criteria = asked.get("criteria") or {}
        if kind == "noul":
            got = self.noul(state, question, str(criteria.get("true", "yes")), str(criteria.get("false", "no")))
            return {"noul": got["p"]["yes"], "logits": got["logits"]}
        if kind == "tfu":
            got = self.tfu(state, question, str(criteria.get("true", "yes")), str(criteria.get("false", "no")))
            return {"noul": got["p"]["true"], "unsure": got["p"]["unsure"], "probabilities": got["p"],
                    "logits": got["logits"]}
        options = [(name, str(text)) for name, text in criteria.items()]
        got = (self.scale if kind == "scale" else self.choice)(state, question, options)
        return {"probabilities": got["p"], "choice": got["choice"], "logits": got["logits"]}

    def ask(self, state: str, questions: dict) -> dict:
        """Every question about one state at once, each its own call of one token, side by side."""
        with ThreadPoolExecutor(min(self.workers, max(1, len(questions)))) as pool:
            done = {key: pool.submit(self.answer, state, asked) for key, asked in questions.items()}
        return {key: future.result() for key, future in done.items()}


# The name it had while it was only a decision model.
Reader = Nemotron


# --- fitting a temperature on your own rows ---------------------------------------------------
# A temperature adds no knowledge and reorders nothing: accuracy and AUC stay as they were. It
# corrects whether the probability means what it says, which is a property of how hard the material
# is, not of the weights. Two hundred rows are enough: one number is free.

def _ece(conf: list[float], ok: list[bool], bins: int = 10) -> float:
    buckets = [[0, 0.0, 0] for _ in range(bins)]
    for c, k in zip(conf, ok):
        b = buckets[min(bins - 1, int(c * bins))]
        b[0] += 1
        b[1] += c
        b[2] += k
    return sum(abs(b[1] - b[2]) for b in buckets) / len(conf)


def calibrate(rows: list[tuple[dict, str]], grid: tuple[float, float, float] = (0.3, 4.0, 0.01)) -> dict:
    """One temperature from rows `(logits, correct answer)`; the answer is one of the logits' keys.

    Chosen to minimise calibration error (ECE, ten bins). Returns the temperature and the error
    before (at 1.0) and after, so a fit that does not pay is visible.
    """
    if len(rows) < 30:
        raise ValueError(f"thirty rows is the floor, got {len(rows)}")
    for z, gold in rows:
        if gold not in z:
            raise ValueError(f"{gold!r} is not one of {list(z)}")

    def error(t: float) -> float:
        conf, ok = [], []
        for z, gold in rows:
            p = softmax(z, t)
            pick = max(p, key=p.get)
            conf.append(p[pick])
            ok.append(pick == gold)
        return _ece(conf, ok)

    lo, hi, step = grid
    ts = [round(lo + i * step, 4) for i in range(int((hi - lo) / step) + 1)]
    best = min(ts, key=error)
    return {"temperature": best, "ece_before": round(error(1.0), 4), "ece_after": round(error(best), 4),
            "rows": len(rows)}
