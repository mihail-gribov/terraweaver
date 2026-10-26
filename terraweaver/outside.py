"""Readers from outside the world, of two kinds, behind two connectors.

There are two ways of getting an answer and they cost differently by an order of magnitude.

A **closed** question — which of these named options — comes back as a probability per option.
It is cheap, it is calibrated, and it is where the volume is: one per link. `Closed` is the
connector for it; `decision.Decision` answers it with Nemotron reading option letters, the same
model family that writes the world's code, and has a third answer — `unsure`, read from the same
forward pass, which is the abstention this world would otherwise have to build out of thresholds.
`Jev`, TypeSafe's hosted model, is kept for the experiments that measured it and is wired nowhere.

An **open** question — where a word has to be invented — is the expensive kind and is asked
once per type, never per link. `Open` is the connector, `Nemotron` the implementation.

Measured on a hundred-fact world: 26 open questions against 115 closed ones. The closed side is
always the volume, which is why it is the side worth having a connector for.

Neither is required. A world with neither does everything it did before; `inspector` checks
for one and marks what it could not read, so a later pass finds it.
"""
import json
from terraweaver import prompts
import os
import time
import urllib.error
import urllib.request

TTL = 10.0                      # how long the world waits; see inspector.TTL for why

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-1.13.0"        # pinned, not an alias: an alias moves and the answers move with it
# The engineer, one step up from the Nano. Three sizes are on offer — Nano-30B-A3B (3B active),
# super-120b-a12b (12B) and Ultra-550b-a55b (55B) — and the engineer is the one party here doing
# open work: it writes the lines that declare a word and fill a thing in. Measured 2026-09-30 on the
# Nano, the failures of the names pass were its code and not its judgement: `it.performer = true`,
# an indented block, a `get` for a thing nobody had recorded. Two of those the world now takes as
# written; the third is the kind of care a larger model is better at. The closed questions are not
# affected — they go to the decision model, which is a different party entirely.
# Two engineers, and the junior does most of the work. Both are open-question models — they write
# the lines — and the split is by how the work went, not by what it is: the first go is the junior's,
# and the senior is called only where the junior's lines came back refused. Measured 2026-09-30, 106
# of 136 readings finished on the first go, so the expensive one is asked about the remaining fifth.
NEMOTRON = os.environ.get("TERRAWEAVER_ENGINEER", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
NEMOTRON_SENIOR = os.environ.get("TERRAWEAVER_ENGINEER_AGAIN", "nvidia/nemotron-3-super-120b-a12b")
NEBIUS = "https://api.tokenfactory.nebius.com/v1/"


class Closed:
    """The picker: one question with named options, and a probability for each.

    One state, several questions: everything asked about one thing goes in one call, because
    the state is billed once however many questions ride on it. That is why `ask` takes a
    mapping rather than a question — four questions about one link cost one link's worth.
    """

    def ask(self, state: str, questions: dict) -> dict:
        raise NotImplementedError

    def choose(self, state: str, question: str, options: dict) -> dict:
        """One question, one mapping of option name to probability."""
        got = self.ask(state, {"q": {"type": "choice", "instructions": question,
                                     "criteria": options}})["q"]
        return got.get("probabilities", {})

    def yes(self, state: str, question: str, true: str, false: str) -> float:
        """One closed question with two answers: the probability of the first."""
        return self.ask(state, {"q": {"type": "noul", "instructions": question,
                                      "criteria": {"true": true, "false": false}}})["q"]["noul"]


class Jev(Closed):
    """TypeSafe's system-one model, asked over HTTP."""

    def __init__(self, key: str | None = None, model: str = JEV_MODEL, ttl: float = TTL,
                 tries: int = 2):
        self.key = key or os.environ["TYPESAFE_API_KEY"]
        self.model, self.ttl, self.tries = model, ttl, tries

    def ask(self, state: str, questions: dict) -> dict:
        body = json.dumps({"state": state, "model": self.model,
                           "questions": questions}).encode()
        wait = 1.0
        for attempt in range(self.tries + 1):
            request = urllib.request.Request(
                JEV_ENDPOINT, data=body,
                headers={"Authorization": f"Bearer {self.key}",
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=self.ttl) as answer:
                    return json.load(answer)["answers"]
            except urllib.error.HTTPError as wrong:
                if wrong.code not in (408, 429, 500, 502, 503, 504, 529) or attempt == self.tries:
                    raise
            except OSError:
                if attempt == self.tries:
                    raise
            time.sleep(wait)
            wait = min(wait * 2, 8.0)
        raise RuntimeError("unreachable")


def _one_of(options: dict, said: str) -> str | None:
    """The option the picker meant, when it did not echo the name exactly.

    A picker asked to repeat a name repeats it nearly: different case, a trailing full stop, the
    name wrapped in a sentence. Insisting on the character-for-character match threw away every
    answer and the walk never moved.
    """
    said = (said or "").strip()
    if said in options:
        return said
    flat = {"".join(ch for ch in n.lower() if ch.isalnum()): n for n in options}
    asked = "".join(ch for ch in said.lower() if ch.isalnum())
    if asked in flat:
        return flat[asked]
    for key, name in flat.items():
        if key and (key in asked or asked in key):
            return name
    return None


class AsChoices(Closed):
    """A closed question put to the engineer, when there is no picker configured.

    The choice between classes is a closed question and belongs to a model that answers those —
    it is asked once per level of the tree, several times per thing, and a word-answering model
    is an order of magnitude dearer. This is the stand-in for a world with no such model to
    hand: the same question, the same options, one of them returned with all the weight.
    """

    def __init__(self, engineer):
        self.engineer = engineer

    def ask(self, state: str, questions: dict) -> dict:
        out = {}
        for key, asked in questions.items():
            options = asked.get("criteria") or {}
            shown = "\n".join(f"    {name} — {why}" for name, why in options.items())
            said = self.engineer.json(
                "You choose one of the named options and answer with JSON only.",
                f"{state}\n\n{asked.get('instructions', '')}\n\n{shown}\n\n"
                f'JSON only: {{"choice": "<exactly one of the option names above>"}}') or {}
            picked = _one_of(options, str(said.get("choice") or ""))
            out[key] = {"probabilities": {picked: 1.0} if picked else {}}
        return out


class Logged:
    """Everything that crosses the boundary to an outside model, written down as it happens.

    Not for debugging one answer — for seeing the boundary whole. What the world asks, from
    where, and how many different shapes of question there really are: three defects in one day
    were the world telling a model something other than what was so, and none of them is visible
    from inside a single answer. The caller is recorded too, because "the engineer got a bad
    word" and "the engineer got that question from the portrait door at the close" are different
    problems.

    Wraps either kind — the one that answers in words and the one that answers with options —
    and adds nothing to what the world sees.
    """

    def __init__(self, party, where):
        import pathlib

        self.party, self.where = party, pathlib.Path(where)
        self.where.parent.mkdir(parents=True, exist_ok=True)

    def _note(self, how: str, asked, said) -> None:
        import inspect
        import json as _json
        from datetime import datetime, timezone

        came_from = "?"
        for frame in inspect.stack()[2:8]:
            module = frame.frame.f_globals.get("__name__", "")
            if module.startswith("terraweaver.") and not module.endswith(".outside"):
                came_from = f"{module.split('.')[-1]}.{frame.function}"
                break
        with self.where.open("a") as log:
            log.write(_json.dumps({
                "at": datetime.now(timezone.utc).isoformat(),
                "how": how, "from": came_from,
                "asked": asked, "said": said,
            }, ensure_ascii=False, default=str) + "\n")

    def json(self, system: str, asked: str):
        said = self.party.json(system, asked)
        self._note("json", asked, said)
        return said

    def say(self, system: str, asked: str):
        said = self.party.say(system, asked)
        self._note("say", asked, said)
        return said

    def ask(self, state: str, questions: dict) -> dict:
        said = self.party.ask(state, questions)
        self._note("ask", {"state": state, "questions": questions}, said)
        return said

    def choose(self, state: str, question: str, options: dict) -> dict:
        said = self.party.choose(state, question, options)
        self._note("choose", {"state": state, "question": question,
                              "options": list(options)}, said)
        return said

    def __getattr__(self, name):
        return getattr(self.party, name)


class Open:
    """The engineer: answers in words, for the one kind of question options cannot hold."""

    def say(self, system: str, asked: str) -> str:
        raise NotImplementedError

    def json(self, system: str, asked: str) -> dict | None:
        """The same, where the answer is meant to be JSON. None when nothing usable came back."""
        said = self.say(system, asked) or ""
        start, end = said.find("{"), said.rfind("}")
        if start < 0 or end < start:
            # A reasoning model spends its budget thinking first, and an empty answer is a
            # budget that ran out rather than a refusal. Worth nothing, not worth guessing at.
            return None
        try:
            return json.loads(said[start:end + 1])
        except ValueError:
            return None


class Nemotron(Open):
    """Nemotron through Nebius Token Factory, as the engineer: the LLM role of `terraweaver.nemotron`.

    One client to the model serves both roles — this one writes, `decision.Decision` decides — so
    the request, the room to think and the cut-off are `nemotron.Nemotron`'s.
    What is kept here is the world's side: the `Open` connector and the room it gives.

    A reasoning model thinks inside the same budget it answers in, so a budget that is merely
    generous for the answer is a cliff for the pair: measured on one question of experiment 01,
    3000 tokens came back `finish_reason='length'` with **nothing at all** and 8000 finished the
    same question in 2845 with the right answer; on 2026-09-28 over 25 readings 8000 still lost one,
    so the cliff is per question and not per size. 16000 is that argument applied once more, and
    the cut-off is said out loud (`CutOff`, a RuntimeError) rather than returned as an empty string
    that every caller would read as "the engineer had nothing to say".
    """

    ROOM = 16000

    def __init__(self, model: str = NEMOTRON, key: str | None = None, ttl: float = TTL,
                 thinking_room: int = ROOM):
        from terraweaver.nemotron import Nemotron as Client

        self.model, self.room = model, thinking_room
        self.client = Client(model=model, base_url=NEBIUS, api_key=key, timeout=ttl,
                             calibration=False)

    def say(self, system: str, asked: str) -> str:
        return self.client.say(system, asked, room=self.room)


# --- the two questions the inspector asks, each built on its connector ---

NAMER_IS = prompts.NAMER_IS

ASK_NAMES = prompts.ASK_NAMES

ENDS_FRAME = prompts.ENDS_FRAME

FITS = "yes — a thing of that sort fills that role"
DOESNT = "no — a thing of that sort does not fill that role"


def namer(engineer: Open):
    """Name the two ends of a type, and say whether its word carries the direction."""
    def ask(account: dict) -> dict | None:
        if not account:
            return None
        return engineer.json(NAMER_IS, ASK_NAMES.format(
            kind=account["kind"], type_is=account.get("type_is") or "(nobody said)",
            examples="; ".join(account.get("examples") or []) or "(nothing yet)"))
    return ask


def judge(picker: Closed, floor: float = 0.30, clear: float = 2.0):
    """Which way a link runs, as four closed questions about its two ends.

    Four, not one. Asked as a single judgement — "is this the right way round" — the same picker
    inverted correct links at p=0.93; asked as four questions about whether each thing fits each
    end, it answered or abstained (12 of 14, every miss an abstention). The difference is not
    the model, it is that the second shape has somewhere to be uncertain.
    """
    def ask(a: dict):
        subject_is = a["subject_is"] or f"the end '{a['kind'].replace('_', ' ')}' starts from"
        object_is = a["object_is"] or f"the end '{a['kind'].replace('_', ' ')}' leads to"
        state = ENDS_FRAME.format(
            kind=a["kind"], type_is=a["type_is"] or "(nobody said)",
            subject_is=subject_is, object_is=object_is,
            s_name=a["subject"]["name"], s_class=a["subject"]["class"],
            s_said=(" — " + "; ".join(a["subject"]["described"])) if a["subject"]["described"] else "",
            o_name=a["object"]["name"], o_class=a["object"]["class"],
            o_said=(" — " + "; ".join(a["object"]["described"])) if a["object"]["described"] else "",
            link_said=("said of the link: " + "; ".join(a["link_described"]))
                      if a["link_described"] else "")
        questions = {key: {"type": "noul", "instructions": asked,
                           "criteria": {"true": FITS, "false": DOESNT}}
                     for key, asked in (
                         ("a_s", f"Is '{a['subject']['name']}' {subject_is}?"),
                         ("b_o", f"Is '{a['object']['name']}' {object_is}?"),
                         ("b_s", f"Is '{a['object']['name']}' {subject_is}?"),
                         ("a_o", f"Is '{a['subject']['name']}' {object_is}?"))}
        got = picker.ask(state, questions)
        as_written = got["a_s"]["noul"] * got["b_o"]["noul"]
        swapped = got["b_s"]["noul"] * got["a_o"]["noul"]
        said = (f"{a['subject']['name']} {a['kind'].replace('_', ' ')} {a['object']['name']}: "
                f"as written {as_written:.2f}, the other way round {swapped:.2f}")
        if max(as_written, swapped) < floor:
            return "impossible", said
        if swapped > as_written * clear:     # clear of it, not merely ahead of it
            return "reversed", said
        if as_written >= 0.5:
            return "right", said
        return "unsure", said
    return ask
