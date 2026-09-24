"""Readers from outside the world, of two kinds, behind two connectors.

There are two ways of getting an answer and they cost differently by an order of magnitude.

A **closed** question — which of these named options — comes back as a probability per option.
It is cheap, it is calibrated, and it is where the volume is: one per link. `Closed` is the
connector for it; `Jev` speaks to a hosted system-one model, `TypecastLM` to a Jev-class model
with open weights that can run on this machine. Which of them answers is a matter of where the
weights are and not of what the world is asking, and the second has a third answer the first
has not — `unsure`, read from the same forward pass, which is the abstention this world would
otherwise have to build out of thresholds.

An **open** question — where a word has to be invented — is the expensive kind and is asked
once per type, never per link. `Open` is the connector, `Nemotron` the implementation.

Measured on a hundred-fact world: 26 open questions against 115 closed ones. The closed side is
always the volume, which is why it is the side worth having a connector for.

Neither is required. A world with no reader does everything it did before; `inspector` checks
for one and marks what it could not read, so a later pass finds it.
"""
import json
import math
import os
import time
import urllib.error
import urllib.request

TTL = 10.0                      # how long the world waits; see inspector.TTL for why

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-1.13.0"        # pinned, not an alias: an alias moves and the answers move with it
NEMOTRON = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
NEBIUS = "https://api.tokenfactory.nebius.com/v1/"


class Closed:
    """A reader that answers questions with named options, returning a probability for each.

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


class TypecastLM(Closed):
    """A Jev-class model with open weights, over HTTP or in this process (`typecastlm`).

    The same four shapes of question under the same names, so what the world asks does not
    depend on where the weights are. One thing it has that Jev has not: `tfu`, the same question
    read over three answers — the two criteria and `unsure`, which is what is left when neither
    fits. That is the abstention this world wants and had to be built out of thresholds: a
    reader that must call something a yes will, and a link turned round on a forced yes is a
    wrong fact where there was a right one.

    `Client()` when a service is running (`TYPECASTLM_ENDPOINT`), `Reader(...)` for the weights
    in this process. Which one is a deployment question and not the world's.
    """

    def __init__(self, reader=None, endpoint: str | None = None, model: str | None = None):
        if reader is not None:
            self.reader = reader
        elif model:
            from typecastlm import Reader

            self.reader = Reader(model)
        else:
            from typecastlm import Client

            self.reader = Client(endpoint) if endpoint else Client()

    def ask(self, state: str, questions: dict) -> dict:
        """The Jev shape, answered question by question — `noul` becomes `tfu` for the third
        answer, and `unsure` is carried through beside the probability rather than thresholded
        into one."""
        out = {}
        for key, question in questions.items():
            criteria = question.get("criteria", {})
            if question.get("type") == "choice":
                said = self.reader.choice(state, question["instructions"],
                                          [(name, text) for name, text in criteria.items()])
                out[key] = {"probabilities": dict(said.get("probabilities", said)),
                            "choice": said.get("choice")}
                continue
            said = self.reader.tfu(state, question["instructions"],
                                   true=criteria.get("true", ""), false=criteria.get("false", ""))
            probabilities = said.get("probabilities", said)
            out[key] = {"noul": float(probabilities.get("true", 0.0)),
                        "unsure": float(probabilities.get("unsure", 0.0))}
        return out


# The name it had while there was only one of them.
Local = TypecastLM


class AsChoices(Closed):
    """A closed question put to a reader that answers in words, when no closed one is configured.

    The choice between classes is a closed question and belongs to a model that answers those —
    it is asked once per level of the tree, several times per thing, and a word-answering model
    is an order of magnitude dearer. This is the stand-in for a world with no such model to
    hand: the same question, the same options, one of them returned with all the weight.
    """

    def __init__(self, open_reader):
        self.reader = open_reader

    def ask(self, state: str, questions: dict) -> dict:
        out = {}
        for key, asked in questions.items():
            options = asked.get("criteria") or {}
            shown = "\n".join(f"    {name} — {why}" for name, why in options.items())
            said = self.reader.json(
                "You choose one of the named options and answer with JSON only.",
                f"{state}\n\n{asked.get('instructions', '')}\n\n{shown}\n\n"
                f'JSON only: {{"choice": "<exactly one of the option names above>"}}') or {}
            picked = str(said.get("choice") or "").strip()
            if picked not in options:
                picked = next((n for n in options if n.lower() in picked.lower()), None)
            out[key] = {"probabilities": {picked: 1.0} if picked else {}}
        return out


class Open:
    """A reader that answers in words, for the one kind of question options cannot hold."""

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
    """Nemotron through Nebius Token Factory."""

    def __init__(self, model: str = NEMOTRON, key: str | None = None, ttl: float = TTL,
                 thinking_room: int = 3000):
        from openai import OpenAI

        self.model, self.room = model, thinking_room
        self.client = OpenAI(base_url=NEBIUS, api_key=key or os.environ["NEBIUS_API_KEY"],
                             timeout=ttl)

    def say(self, system: str, asked: str) -> str:
        answer = self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=self.room,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": [{"type": "text", "text": asked}]}])
        return answer.choices[0].message.content or ""


# --- the two questions the inspector asks, each built on its connector ---

NAMER_IS = ("You name the parts of a link type in a record of facts. A link has a subject — the "
            "end it starts from — and an object — the end it leads to. You answer with JSON and "
            "nothing else.")

ASK_NAMES = """Link type: {kind}
What it is: {type_is}
Written like: {examples}

Name what each end IS, as a short noun phrase a thing could be checked against — "a city that
serves as a capital", not "the capital". Keep it wide enough for everything that honestly
belongs there: a religion's followers include people as well as organisations. A role written
too tightly turns every honest link into a false alarm.

Then: does the word '{kind}' tell a reader which end it starts from? `capital_of` does — "a
capital_of b" reads "a is b's capital". `author` does not: it could start from the writer or
from the book. Give a word that would, or the same word if it already does. It must be a name
for the link type, not for one of its ends.

JSON only:
{{"subject_is": "...", "object_is": "...", "clear_name": "..."}}"""

ENDS_FRAME = """One link out of a record of links. A link has two ends and they are not
interchangeable: the subject is the end it starts from, the object is the end it leads to.

    relation:    {kind} — {type_is}
    subject is:  {subject_is}
    object is:   {object_is}

    subject:  {s_name} (a {s_class}){s_said}
    object:   {o_name} (a {o_class}){o_said}
    {link_said}

Judge only whether each end holds the right KIND of thing for its role. Whether the claim is
TRUE is not asked and must not affect the answer: this record deliberately holds claims that
contradict common knowledge and they are meant to be kept. With subject "a city that is a
capital" and object "the country whose capital it is", the pair Rome / Japan is correct in kind
even though Rome is not Japan's capital."""

FITS = "yes — a thing of that sort fills that role"
DOESNT = "no — a thing of that sort does not fill that role"


def namer(reader: Open):
    """Name the two ends of a type, and say whether its word carries the direction."""
    def ask(account: dict) -> dict | None:
        if not account:
            return None
        return reader.json(NAMER_IS, ASK_NAMES.format(
            kind=account["kind"], type_is=account.get("type_is") or "(nobody said)",
            examples="; ".join(account.get("examples") or []) or "(nothing yet)"))
    return ask


def judge(reader: Closed, floor: float = 0.30, clear: float = 2.0):
    """Which way a link runs, as four closed questions about its two ends.

    Four, not one. Asked as a single judgement — "is this the right way round" — the same reader
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
        got = reader.ask(state, questions)
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
