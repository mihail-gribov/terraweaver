"""Entities, events and links an agent names as it likes, beside a memory of texts.

The agent describing a situation with two people should not have to know how the world is built:
it makes a variable for each, says what it knows about them, and says what joins them — always in
a sentence, because a fact is its text. The sentence goes to the memory's journal like any `tell`
(`memory/journal.py`), numbered and dated; the things it is about go beside it, in a structure
file, as an index over the texts and never as facts of their own (docs/decisions.md, 2026-10-15).

What the agent never settles here is identity across conversations. `entity("Anna")` makes a new
thing every time; if the memory holds an Anna already, the run's answer asks whether this is she,
and the agent answers with `same` or `different` in its next run. Nothing is merged on a guess.

    anna = entity("Anna", "Anna is the user's sister.", kind="person")
    olga = entity("Olga")
    link(anna, olga, "Anna and Olga work together at Brightwork.", as_="colleague")
    event("Anna's wedding", "Anna marries Tom on 2027-06-12 in Porto.", when="2027-06-12", who=[anna])
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable


class Thing:
    """Something the agent named: a person, a place, an event. Its variable is the handle."""

    def __init__(self, memory: "Structure", session: str, id: str, name: str, kind: str | None):
        self._memory, self._session = memory, session
        self.id, self.name, self.kind = id, name, kind

    def say(self, text: str, source: str = "conversation") -> str:
        """A fact about this thing, in a sentence that names it."""
        return self._memory.said(self._session, text, [self], source=source)

    def about(self) -> list[str]:
        """Every entry the memory holds about this thing, as told."""
        return self._memory.about(self)

    def set(self, attr: str, value, text: str, source: str = "conversation") -> str:
        """A value of this thing — `price_eur`, 299 — kept with the sentence that says it."""
        return self._memory.set_value(self._session, self, attr, value, text, source)

    def get(self, attr: str):
        """What the memory holds for `attr`: one value, an interval of numbers, or None."""
        return self._memory.value(self, attr)["value"]

    def values(self) -> dict:
        """Every attribute this thing has a value for, folded: {attr: value}."""
        return {a: self._memory.value(self, a)["value"] for a in self._memory.attrs(self)}

    def links(self, as_: str | None = None) -> list[tuple["Thing", str, str]]:
        """The things joined to this one: (thing, the link's word, its sentence)."""
        return self._memory.links(self, as_)

    def dates(self) -> dict:
        """When it came into the memory, when anything about it last did, and when it was last
        said to be so by the agent: {"created", "changed", "told"} — times as "YYYY-MM-DD HH:MM:SS"."""
        return self._memory.dates(self)

    def __repr__(self) -> str:
        return f"{self.name} ({self.id})"


class Structure:
    """The index beside the journal: which things there are, and which entries are about which.

    Append-only, one JSON record a line, so it is rebuilt by reading it and nothing in it is ever
    edited. `keep(text, source)` appends to the journal and returns the entry's number; `entries()`
    returns what the journal holds now, so an entry forgotten there is gone here too.

    Everything that comes in is kept, with when it came: a record's `n` is the order it arrived
    in and `at` the time. That holds for the structure as for the texts — a link given as a word
    and no sentence is taken and asked about, not refused — and for what the agent heard: the
    message or document as it came is kept in `heard.md`, and the facts told after it point back
    at it, so a fact the agent left out or retold is still there to find.
    """

    def __init__(self, path: Path, keep: Callable[[str, str], int],
                 entries: Callable[[], dict[int, str]]):
        self.path, self._keep, self._entries = path, keep, entries
        self.records: list[dict] = []
        # Read only what came since this time, when set: a collection gathered for a task reads
        # its values and texts as this task found them, not as a page said them last week.
        self.since: str | None = None
        if path.exists():
            self.records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        self.asked: list[str] = []      # what the world asks the agent, read off after each run
        self.kept: list[str] = []       # what each run wrote, for its answer
        self.heard_path = path.with_name("heard.md")
        # Per session: the latest text heard, and the record count when it was heard, so what was
        # told after it can be checked against it once.
        self.pending: dict[str, tuple[int, str, int]] = {}
        self.last_heard: dict[str, int] = {}
        # Per session: now as the agent knows it, for the run under way. The agent's word is when
        # a thing was said — the conversation's time; without it, this clock's.
        self.now: dict[str, datetime] = {}

    def _write(self, record: dict) -> None:
        # Past the last, not the count: a thing that outlived its time is gone from the records.
        record["n"] = max((r["n"] for r in self.records), default=0) + 1
        record["at"] = f"{datetime.now():%Y-%m-%d %H:%M:%S}"      # when it arrived here
        told = self.now.get(record.get("session"))
        if told:
            record["told"] = f"{told:%Y-%m-%d %H:%M:%S}"          # when it was said, by the agent
        self.records.append(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _things(self) -> dict[str, dict]:
        return {r["thing"]: r for r in self.records if "thing" in r}

    def thing(self, session: str, ref) -> Thing:
        """A thing by its id, for answering the world's questions about one from another run."""
        if isinstance(ref, Thing):
            return ref
        record = self._things().get(str(ref))
        if record is None:
            raise ValueError(f"The memory holds no thing {ref!r}.")
        return Thing(self, session, record["thing"], record["name"], record.get("kind"))

    # --- what the agent writes -------------------------------------------------------------

    def entity(self, session: str, name: str, text: str | None = None, kind: str | None = None,
               source: str = "conversation") -> Thing:
        name = " ".join(str(name or "").split())
        if not name:
            raise ValueError('entity(name) needs a name: entity("Anna"), entity("the flat on Rua Augusta").')
        thing = Thing(self, session, f"t{max((int(t[1:]) for t in self._things() if t[1:].isdigit()), default=0) + 1}", name, _word(kind))
        self._write({"thing": thing.id, "name": name, "kind": thing.kind, "session": session})
        self._ask_who(thing)
        if text:
            self.said(session, text, [thing], source=source)
        return thing

    def event(self, session: str, name: str, text: str, when: str | None = None, who=(),
              source: str = "conversation") -> Thing:
        thing = self.entity(session, name, kind="event")
        self.said(session, text, [thing, *who], when=when, source=source)
        return thing

    def link(self, session: str, one: Thing, other: Thing, text: str | None = None, as_: str | None = None,
             source: str = "conversation") -> str:
        return self.said(session, text, [one, other], as_=as_, source=source)

    def said(self, session: str, text: str, about: list, as_: str | None = None,
             when: str | None = None, source: str = "conversation", value=None) -> str:
        text = (text or "").strip()
        things = [self.thing(session, t) for t in about]
        if not text and (as_ or len(things) > 1):
            # A link given as a word: taken, since it says something, and asked about, since no
            # reader can tell from `capital` which of the two is the capital of which.
            self._write({"entry": None, "about": [t.id for t in things], "as": _word(as_),
                         "when": when, "session": session, "heard": self.last_heard.get(session)})
            names = " and ".join(t.name for t in things)
            self.kept.append(f"a link with no sentence ({names})")
            self.asked.append(
                f"The link between {names}{f' ({as_})' if as_ else ''} has no sentence. It is kept, "
                f"but nobody reading the memory will see it: say it in words, e.g. "
                f"link(a, b, \"<what one is to the other>\").")
            return "kept without a sentence"
        if not text:
            raise ValueError("A fact is a sentence: say what is true, e.g. "
                             "\"Anna moved from Lisbon to Porto in September 2026.\"")
        number = self._keep(text, " ".join((source or "").split())[:200] or "conversation",
                            self.now.get(session))
        record = {"entry": number, "about": [t.id for t in things], "as": _word(as_),
                  "when": when, "session": session, "heard": self.last_heard.get(session)}
        if value is not None:
            record["value"] = value
        self._write(record)
        self.kept.append(f"#{number} ({', '.join(t.name for t in things)})")
        # The journal is what every reader sees, alone: a sentence that does not name its thing
        # will be read as about nobody. Said, not refused — the agent knows what it meant.
        unnamed = [t for t in things if not _names(text, t.name)]
        if unnamed:
            self.asked.append(
                f"#{number} does not name {', '.join(t.name for t in unnamed)}, and whoever reads "
                f"the memory sees only the sentence. If it is about them, say it again with the "
                f"name in it; the memory keeps both.")
        return f"#{number}"

    def set_value(self, session: str, thing: Thing, attr: str, value, text: str,
            source: str = "conversation") -> str:
        """A value is a fact like any other: its sentence goes to the journal, and the record
        beside it says which attribute of which thing the sentence gives. A value without a
        sentence is refused, since nothing could show where it came from."""
        attr = _word(attr)
        if not attr:
            raise ValueError('set(attr, value, text) needs an attribute: x.set("price_eur", 299, "...").')
        if not isinstance(value, (int, float, str, bool)) or value == "":
            raise ValueError(f"{attr}: a value is a number, a word or True/False, not {value!r}.")
        return self.said(session, text, [thing], as_=attr, source=source, value=value)

    def dates(self, thing: Thing) -> dict:
        group = self.one_with(thing)
        mine = [r for r in self.records if r.get("thing") in group or group & set(r.get("about") or ())]
        made = [r["at"] for r in mine if "thing" in r]
        told = [r["told"] for r in mine if r.get("told")]
        return {"created": min(made) if made else None, "changed": max((r["at"] for r in mine), default=None),
                "told": max(told) if told else None}

    def attrs(self, thing: Thing) -> list[str]:
        group = self.one_with(thing)
        return sorted({r["as"] for r in self.records if "value" in r and group & set(r["about"]) and self._fresh(r)})

    def value(self, thing: Thing, attr: str) -> dict:
        """Every value said for `attr` of this thing (and those settled the same), with its
        sentence, and the values folded: numbers into [lowest, highest], words and yes/no into
        the one said most (a tie is None — not known, rather than a guess)."""
        group, held, attr = self.one_with(thing), self._entries(), _word(attr)
        said = [(r["value"], held[r["entry"]]) for r in self.records
                if "value" in r and r.get("as") == attr and group & set(r["about"]) and r["entry"] in held
                and self._fresh(r)]
        values = [v for v, _ in said]
        if not values:
            folded = None
        elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            folded = min(values) if min(values) == max(values) else [min(values), max(values)]
        else:
            counts: dict = {}
            for v in values:
                counts[v] = counts.get(v, 0) + 1
            top = sorted(counts.items(), key=lambda kv: -kv[1])
            folded = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else None
        return {"value": folded, "said": said}

    def links(self, thing: Thing, as_: str | None = None) -> list[tuple[Thing, str, str]]:
        group, held = self.one_with(thing), self._entries()
        things, out = self._things(), []
        for r in self.records:
            if "value" in r or "entry" not in r or len(r.get("about") or ()) < 2 or not group & set(r["about"]):
                continue
            if as_ and r.get("as") != _word(as_):
                continue
            for other in r["about"]:
                if other not in group and other in things:
                    o = things[other]
                    out.append((Thing(self, thing._session, other, o["name"], o.get("kind")),
                                r.get("as"), held.get(r["entry"], "")))
        return out

    def things(self, session: str, kind: str | None = None) -> list[Thing]:
        """Every thing the memory holds, or every one of a kind; one per group settled the same."""
        # A kind is a free word, said differently by each teller: "robot vacuum", robot_vacuum,
        # "robot vacuums". Matched by its words, any of them in the thing's kind or name.
        want = {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", (kind or "").lower())}
        seen, out = set(), []
        for r in self._things().values():
            has = {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", f"{r.get('kind') or ''} {r['name']}".lower())}
            if r["thing"] in seen or (want and not want & has):
                continue
            t = Thing(self, session, r["thing"], r["name"], r.get("kind"))
            seen |= self.one_with(t)
            out.append(t)
        return out

    def forgot(self, taken: list[int], request: int) -> None:
        """The journal's `forget` took `taken` out and kept the request as `request`: the request
        is about whatever they were about, so whoever looks a thing up sees that it was asked."""
        about = sorted({t for r in self.records if r.get("entry") in taken for t in r["about"]})
        self._write({"entry": request, "about": about, "as": "forget", "when": None, "session": None,
                     "heard": None})

    # --- what was heard, when something is forgotten ---------------------------------------

    def heard_messages(self) -> list[tuple[int, str, str]]:
        """`heard.md`'s messages: number, heading, text."""
        held = self.heard_path.read_text() if self.heard_path.exists() else ""
        out = []
        for part in held.split("## #")[1:]:
            heading, _, text = part.partition("\n")
            if heading.partition(" · ")[0].isdigit():
                out.append((int(heading.partition(" · ")[0]), heading, text.strip()))
        return out

    def heard_candidates(self, taken: list[tuple[int, str]]) -> list[tuple[int, str]]:
        """The heard sentences that may say what the forgotten entries said: every sentence of the
        messages they were told from, and any other sentence naming what they name. Which of
        them do is a reader's to judge; this only keeps the reading short."""
        numbers = {n for n, _ in taken}
        sources = {r.get("heard") for r in self.records if r.get("entry") in numbers} - {None}
        names = {w.lower() for _, text in taken for w in _specifics(text)}
        out = []
        for k, _, text in self.heard_messages():
            for sentence in _sentences(text):
                if k in sources or names & {w.lower() for w in _specifics(sentence)}:
                    out.append((k, sentence))
        return out

    def forget_heard(self, chosen: list[tuple[int, str]]) -> list[tuple[int, str]]:
        """Take these sentences out of `heard.md` and out of what is still to be checked, and
        return those taken. The rest of each message stays as it came. Bin them first."""
        by_message: dict[int, list[str]] = {}
        for k, sentence in chosen:
            by_message.setdefault(k, []).append(sentence)
        taken, parts = [], []
        for k, heading, text in self.heard_messages():
            for sentence in by_message.get(k, []):
                if sentence in text:
                    text = text.replace(sentence, "", 1)
                    taken.append((k, sentence))
            text = re.sub(r"[ \t]{2,}", " ", text).strip()
            parts.append(f"## #{heading}\n{text}\n\n")
        if taken:
            self.heard_path.write_text("".join(parts))
            # Not asked about later as untold: it is gone because the user asked.
            for session, (k, text, since) in list(self.pending.items()):
                for message, sentence in taken:
                    if message == k:
                        text = text.replace(sentence, "", 1)
                self.pending[session] = (k, text, since)
        return taken

    def settle(self, session: str, one, other, same: bool) -> str:
        a, b = self.thing(session, one), self.thing(session, other)
        self._write({"same" if same else "different": [a.id, b.id], "session": session})
        return f"{a} and {b}: {'the same' if same else 'different'}."

    # --- what came in as it came ---------------------------------------------------------

    def heard(self, session: str, text: str, source: str = "conversation") -> int:
        """Keep a message or a document as it came, before anything is told from it."""
        text = (text or "").strip()
        if not text:
            return 0
        held = self.heard_path.read_text() if self.heard_path.exists() else ""
        number = held.count("\n## #") + held.startswith("## #") + 1
        self.heard_path.parent.mkdir(parents=True, exist_ok=True)
        with self.heard_path.open("a") as file:
            file.write(f"## #{number} · {self.now.get(session) or datetime.now():%Y-%m-%d %H:%M:%S} · "
                       f"{source} · {session}\n{text}\n\n")
        self._write({"heard": number, "session": session})
        self.pending[session] = (number, text, len(self.records))
        self.last_heard[session] = number
        return number

    def check_heard(self, session: str) -> None:
        """Ask once about the names and numbers of the last text heard that nothing told since has.

        By what a sentence names, not by its words: the agent retells, and is meant to, so on
        words nearly every sentence of a MemOps conversation read as untold — "Thanks, yeah."
        among them — and the one real loss, Tyler's $150K offer, was the forty-first question.
        A sentence that names nothing and counts nothing is the agent's to judge, and not asked.
        """
        if session not in self.pending:
            return
        number, text, since = self.pending.pop(session)
        held = self._entries()
        told = [held[r["entry"]] for r in self.records[since:]
                if r.get("session") == session and r.get("entry") in held]
        said = " ".join(told).lower()
        said_numbers = {_bare_number(w) for w in re.findall(r"\S*\d\S*", said)}
        for sentence in _sentences(text):
            missing = [w for w in _specifics(sentence)
                       if (_bare_number(w) not in said_numbers if re.search(r"\d", w) else w.lower() not in said)]
            if missing:
                self.asked.append(f"Nothing told from heard #{number} has {', '.join(missing)}: "
                                  f"\"{sentence}\" If it is about the user's life, keep it.")

    # --- what the agent reads --------------------------------------------------------------

    def one_with(self, thing: Thing) -> set[str]:
        """This thing and every thing settled to be the same, in either direction, transitively."""
        group, grew = {thing.id}, True
        while grew:
            grew = False
            for r in self.records:
                pair = r.get("same")
                if pair and (pair[0] in group) != (pair[1] in group):
                    group |= set(pair)
                    grew = True
        return group

    def about(self, thing: Thing) -> list[str]:
        group, held = self.one_with(thing), self._entries()
        numbers = sorted({r["entry"] for r in self.records
                          if "entry" in r and group & set(r["about"]) and r["entry"] in held and self._fresh(r)})
        return [held[n] for n in numbers]

    def _fresh(self, record: dict) -> bool:
        return self.since is None or record.get("at", "") >= self.since

    def _ask_who(self, thing: Thing) -> None:
        """Ask whether a new thing is one the memory already holds under a name it shares."""
        settled = {frozenset(r.get("same") or r.get("different") or ()) for r in self.records}
        asked: set[str] = set()
        for other in self._things().values():
            if other["thing"] == thing.id or not _same_name(thing.name, other["name"]):
                continue
            if frozenset((thing.id, other["thing"])) in settled or other["thing"] in asked:
                continue
            known = Thing(self, thing._session, other["thing"], other["name"], other.get("kind"))
            # Things already settled as one are asked about once, as the first of them.
            asked |= self.one_with(known)
            said = self.about(known)[:1]
            seen = said[0].split(": ", 1)[-1].rstrip(".") if said else "nothing said about it yet"
            self.asked.append(
                f"Is {thing.name} ({thing.id}) the {other['name']} the memory holds as "
                f"{other['thing']} — {seen}? Answer with same({thing.id!r}, {other['thing']!r}) "
                f"or different({thing.id!r}, {other['thing']!r}).")

    def namespace(self, session: str) -> dict:
        """What a run sees: the four constructors, the two answers, and a lookup by id."""
        return {
            "entity": lambda name, text=None, kind=None, source="conversation":
                self.entity(session, name, text, kind, source),
            "event": lambda name, text, when=None, who=(), source="conversation":
                self.event(session, name, text, when, who, source),
            "link": lambda one, other, text=None, as_=None, source="conversation":
                self.link(session, one, other, text, as_, source),
            "same": lambda one, other: self.settle(session, one, other, True),
            "different": lambda one, other: self.settle(session, one, other, False),
            "thing": lambda ref: self.thing(session, ref),
            "things": lambda kind=None: self.things(session, kind),
        }


def _word(word: str | None) -> str | None:
    """A free word as given, lower case and one token, or nothing."""
    word = "_".join(str(word or "").lower().split())
    return word or None


def _names(text: str, name: str) -> bool:
    """Whether the sentence names the thing: its name, or a word of it longer than two letters."""
    said = text.lower()
    return name.lower() in said or any(w in said for w in re.findall(r"\w{3,}", name.lower()))


def _sentences(text: str) -> list[str]:
    """A heard text's sentences, list markers taken off."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip().lstrip("-*•").strip() for p in parts if len(re.findall(r"\w{3,}", p)) >= 2]


def _specifics(sentence: str) -> list[str]:
    """What a sentence names and counts: its numbers, and its capitalised words but the first."""
    out = []
    for i, word in enumerate(re.findall(r"[\w$'’.,-]+", sentence)):
        word = re.sub(r"['’]s$", "", word.strip(".,'’-"))
        if re.search(r"\d", word):
            out.append(word)
        elif word[:1].isupper() and len(word) > 2 and not re.search(r"['’](ve|d|ll|re|m|t)$", word) \
                and not (i == 0 and word.lower() in _STARTERS):
            out.append(word)
    return list(dict.fromkeys(out))


# Words that open a sentence with a capital and name nothing. A name opening one ("Tyler got an
# offer") is kept; a word missing here costs a question the agent can leave.
_STARTERS = set("""the a an he she they we it this that these those there here his her their our my
your you but and so or oh yeah yes no thanks thank anyway also hey right perfect good great okay ok
well just apparently honestly actually maybe if when what then now still after before since once
because although though even all one some every last next quick can could would will should do
does did is are was were how why where who which""".split())


def _bare_number(word: str) -> str:
    """A number as written, without what dresses it: "17th" is 17, "$150K," is $150k."""
    word = word.lower().strip(".,;:!?()\"'’")
    return re.sub(r"(?<=\d)(st|nd|rd|th)$", "", word)


def _same_name(one: str, other: str) -> bool:
    """"Anna" and "Anna Lee" may be one person; "Anna" and "Olga" are not asked about."""
    a, b = (set(re.findall(r"\w{3,}", n.lower())) for n in (one, other))
    return bool(a and b) and (a <= b or b <= a)
