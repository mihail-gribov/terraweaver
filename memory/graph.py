"""Texts and the entities they mention: the memory's graph, built on the journal as it grows.

The texts are the links. An entry that says "my wife Mila loves jazz" joins the user, Mila and
jazz by being said; nothing is drawn out of it as a triple. What is added is which entities each
text mentions, and in what words — so every entity is reached through the texts that speak of it:

    entry      one user message, rewritten to stand alone, dated (the journal; read-only here)
    dialogue   the entries of one talk in a row, until a long pause: a stretch of the journal
    topic      a text the reader writes over the entries on one subject, layered; every version kept
    entity     a name and a kind from a flat set ("person", "TV"), within its dialogue; the user,
               the one entity every dialogue shares
    mention    a text naming an entity, with the words it names it by ("my wife")
    link       a relation between two entities, with the entry and the words it stands on; a few
               plain, common ones (spouse, parent, friend, works at…) are named the same way every
               time — a skeleton, not a fence: any other relation the entry states is kept too

The texts are the flesh, the entities and links the skeleton: the skeleton finds the texts, and an
answer is made from the texts. What is hard to formalise is never forced into a field; it stays
in the words that said it.

An entity's image is the texts that mention it, the newest first, each with its day: built when
asked for, never stored as the truth. Time is in the days: a newer text says what holds now, and
the reader of the image is told so. Nothing collapses: entities of two dialogues are one in an
image only by their name, a name the reader gave from the text's own words.

Each entry is read as soon as it is kept, in the background, beside the conversation: one call to
the reader with the entry, its dialogue so far, the entities and kinds in use, and the topics' last
texts. Everything here is derived from the journal and rebuilt from it (`rebuild`).
"""
import json
import logging
import math
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path

from memory.models import role

log = logging.getLogger("memory.graph")

# A pause longer than this ends a dialogue.
PAUSE = timedelta(hours=1)
# What the reader of one entry is shown, however large the memory grows: the topics nearest the
# entry and those its dialogue already touched, and the entities its dialogue and the user's own
# people bring — never everything, so a reading costs the same in the first week and the third year.
SHOWN_TOPICS, SHOWN_ENTITIES = 8, 40
USER = "the user"
# The words a reader may write for the user; every one of them is the user, by code.
SELF = {"the user", "user", "i", "me", "myself", "we", "us", "the user s"}
# The plainest and most frequent relations in a person's life, named the same way every time so that
# they can be followed: "<from> is the <relation> of <to>". The reader takes one of these when it
# fits and names any other relation itself; nothing is dropped for not being on the list.
RELATIONS = {
    "spouse": "husband or wife", "partner": "partner, boyfriend or girlfriend",
    "parent": "mother or father", "child": "son or daughter", "sibling": "brother or sister",
    "relative": "another relative", "friend": "friend", "colleague": "colleague",
    "manager": "manager or boss", "works_at": "works at or for (to: an organisation)",
    "studies_at": "studies at", "lives_in": "lives in (to: a place)", "pet": "pet",
}

READ = """You keep a personal memory. Below is one new entry: what the user just said, rewritten \
to stand alone. Say which entities it mentions and which topics it belongs to.

The entities already known (name — kind):
{entities}

The kinds in use: {kinds}

The topics so far (id. name: last text):
{topics}

What the user said earlier in this conversation:
{dialogue}

The new entry, said on {day}:
<entry>
{entry}
</entry>

Answer with JSON only:
{{"entities": [{{"name": "...", "kind": "...", "as": "the entry's exact words that name it"}}],
 "links": [{{"from": "<entity>", "relation": "...", "to": "<entity>", "quote": "the entry's exact words that say it"}}],
 "topics": [{{"topic": <id, or "new">, "name": "a short name", "text": "the topic's whole new text"}}]}}

Entities: the people, places, things, organisations and events the entry names. "I", "me", "my" \
are "{user}"; so are "we" and "us", with whoever the entry says is with them as entities of their own. \
Give a known entity its known name. A person is named by their name when the entry or the \
conversation says it ("My wife Mila" is "Mila", with a link "Mila — spouse — {user}"); by their \
relation to the user ("the user's sister") only when no name is said. A particular product, model, \
brand, place or event is its own entity ("Sony TV", "Samsung S90D"), never folded into a general \
one ("TV"). Take a kind in use before \
making a new one; a kind is one or two plain words.
Links: what the entry says joins two entities, read "<from> is the <relation> of <to>". When one \
of these fits, use its name: {relations}. Otherwise name the relation in a word or two ("landlord", \
"coach", "gave the gift to"). Only what the entry says.
Topics: the matters the user keeps coming back to and adding to — a personal problem, choosing a \
product, starting a business, a trip, a family event — named as one would name it a month later \
("choosing a TV", "starting the bakery", "back pain"). When the entry goes on with a topic above, \
join it, even in other words or months later; make a new one only for a new matter. An entry may \
belong to more than one, or to none if it is small talk. A topic's \
text says what it has come to, layered and dated: what was considered, what was ruled out and why, \
what was chosen, what changed — the latest last. Write it over the topic's last text and the new \
entry; keep what still matters, and never drop what was ruled out or why. Every layer keeps its \
day. A choice later changed stays a choice with its day, and the change is a new layer after it: \
"chose X (day); then changed to Y (day)" — never "looked at X". Summarise in your own \
short words, do not copy the entries. Only what the entries say. For example: "Planning a trip to \
Japan in spring with Tom. Looked at Kyoto and Osaka. Osaka ruled out, too crowded for Tom \
(2026-03-02). Settled on Kyoto, the ryokan in Gion (2026-03-02). Moved the trip from April to May \
(2026-03-20)." """

IMAGE_HEAD = ("What the memory has read of {names}, from the facts that mention them (fact numbers "
              "and days; the newest says what holds now):")


def _day(heading: str) -> str:
    parts = heading.split(" · ")
    return parts[1] if len(parts) > 1 else ""


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(text).lower()).split())


def _named(name) -> str:
    """The name as kept: the user under one name, whatever the reader wrote for them."""
    name = str(name or "").strip()
    return USER if _words(name) in SELF else name


class Graph:
    """The mentions and topics of one memory, under `where`; `entries()` gives the journal as
    (number, heading, text). `wake()` after every kept entry; `wait()` before reading the graph."""

    def __init__(self, where: Path, entries, reader=None, embed=None):
        self.where = Path(where)
        self.where.mkdir(parents=True, exist_ok=True)
        self.entries = entries
        self.reader = reader or (lambda system, prompt: role("reader").json(system, prompt, room=8000))
        # Texts -> vectors, to find topics by meaning; without it, by the words they share.
        self.embed = embed
        self._vectors: dict[tuple, list] = {}
        self.lock = threading.Lock()
        self.pending = threading.Event()
        self.idle = threading.Event()
        self.idle.set()
        self._load()
        threading.Thread(target=self._work, daemon=True, name="graph").start()

    # --- what is kept -------------------------------------------------------------------------

    def _load(self) -> None:
        self.mentions = self._lines("mentions.jsonl")
        self.links = self._lines("links.jsonl")
        self.topics = self._lines("topics.jsonl")
        state = self.where / "state.json"
        self.read_upto = json.loads(state.read_text())["read_upto"] if state.exists() else 0
        # Indexes, so that finding by an entity, an entry or a topic never walks everything.
        self.by_entity, self.by_text, self.links_of, self.latest, self.kinds = {}, {}, {}, {}, {}
        self._index(self.mentions, self.links, self.topics)

    def _index(self, mentions, links, topics) -> None:
        for m in mentions:
            self.by_entity.setdefault(m["entity"].lower(), []).append(m)
            self.by_text.setdefault(m["text"], []).append(m)
            self.kinds.setdefault(m["entity"], m["kind"])
        for l in links:
            for end in (l["from"], l["to"]):
                self.links_of.setdefault(end.lower(), []).append(l)
        for t in topics:
            self.latest[t["topic"]] = t

    def _lines(self, name: str) -> list[dict]:
        path = self.where / name
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []

    def _append(self, name: str, rows: list[dict]) -> None:
        with (self.where / name).open("a") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def rebuild(self) -> None:
        """Everything read again from the journal: what the graph holds is derived, never the truth."""
        with self.lock:
            for name in ("mentions.jsonl", "links.jsonl", "topics.jsonl", "state.json"):
                (self.where / name).unlink(missing_ok=True)
            self._load()
        self.wake()

    # --- reading, beside the conversation --------------------------------------------------------

    def wake(self) -> None:
        self.idle.clear()
        self.pending.set()

    def wait(self, seconds: float = 30) -> bool:
        """Until every kept entry is read, a bounded time. False when the time ran out."""
        if not any(n > self.read_upto for n, _, _ in self.entries()):
            return True
        self.wake()
        return self.idle.wait(seconds)

    def _work(self) -> None:
        self.wake()
        while True:
            self.pending.wait()
            self.pending.clear()
            try:
                while self._read_next():
                    pass
            except Exception:  # noqa: BLE001 - a reading that failed is tried again on the next entry
                log.exception("graph reading failed")
            if not self.pending.is_set():
                self.idle.set()

    def _read_next(self) -> bool:
        held = self.entries()
        new = [(n, h, t) for n, h, t in held if n > self.read_upto]
        if not new:
            return False
        n, heading, text = new[0]
        dialogue = self.dialogue_of(n, held)
        earlier = [(m, t) for m, _, t in held if m in dialogue and m < n][-20:]
        topics = self.near_topics(text, SHOWN_TOPICS, touched=[m for m, _ in earlier])
        entities = self.near_entities(text + " " + " ".join(t for _, t in earlier), [m for m, _ in earlier])
        got = self.reader("Answer with JSON only.", READ.format(
            entities="\n".join(f"- {name} — {kind}" for name, kind in entities) or "none yet",
            kinds=", ".join(sorted(set(self.kinds.values()))[:60]) or "none yet",
            topics="\n".join(f"{t['topic']}. {t['name']}: {t['text']}" for t in topics) or "none yet",
            dialogue="\n".join(f"{m}. {t}" for m, t in earlier) or "nothing yet", day=_day(heading)[:10], entry=text,
            user=USER, relations="; ".join(f"{k} ({v})" for k, v in RELATIONS.items()))) or {}
        with self.lock:
            self._keep_reading(n, heading, text, dialogue[0], got)
            self.read_upto = n
            (self.where / "state.json").write_text(json.dumps({"read_upto": n}))
        return True

    def _keep_reading(self, n: int, heading: str, text: str, dialogue: int, got: dict) -> None:
        plain, day = _words(text), _day(heading)
        mentions = []
        for e in got.get("entities") or []:
            if not isinstance(e, dict) or not str(e.get("name") or "").strip():
                continue
            name, said = _named(e["name"]), str(e.get("as") or "")
            # The words a mention stands on are the entry's own, by code; "I" and "my" are the user's.
            if name != USER and (not _words(said) or _words(said) not in plain):
                continue
            mentions.append({"text": n, "dialogue": 0 if name == USER else dialogue, "day": day, "entity": name,
                             "kind": "person" if name == USER else str(e.get("kind") or "thing").strip().lower(),
                             "as": said})
        # A link may join an entity this entry names to one known before ("the living room").
        named = ({k: ms[0]["entity"] for k, ms in self.by_entity.items()} | {m["entity"].lower(): m["entity"] for m in mentions}
                 | {USER: USER})
        links = []
        for l in got.get("links") or []:
            relation = "_".join(_words(l.get("relation")).split()) if isinstance(l, dict) else ""
            if not relation:
                continue
            a, b = (named.get(_named(l.get(end)).lower()) for end in ("from", "to"))
            if a and b and a != b and _words(l.get("quote")) and _words(l["quote"]) in plain:
                links.append({"from": a, "relation": relation, "common": relation in RELATIONS, "to": b, "text": n, "day": day,
                              "quote": l["quote"]})
        latest = dict(self.latest)
        versions = []
        for t in got.get("topics") or []:
            if not isinstance(t, dict) or not str(t.get("text") or "").strip():
                continue
            before = latest.get(t.get("topic"))
            topic = before["topic"] if before else max(list(self.latest) + [0]) + 1 + len(versions)
            versions.append({"topic": topic, "name": str(t.get("name") or (before or {}).get("name") or "").strip(),
                             "text": str(t["text"]).strip(), "day": day,
                             "entries": sorted(set((before or {}).get("entries", [])) | {n}),
                             "version": (before or {}).get("version", 0) + 1})
        self.mentions += mentions
        self.links += links
        self.topics += versions
        self._index(mentions, links, versions)
        self._append("mentions.jsonl", mentions)
        self._append("links.jsonl", links)
        self._append("topics.jsonl", versions)

    # --- what is read from it -------------------------------------------------------------------

    def dialogue_of(self, n: int, held=None) -> list[int]:
        """The entries of n's dialogue: those in a row with it, no pause longer than PAUSE between."""
        held = held if held is not None else self.entries()
        groups, before = [], None
        for m, h, _ in held:
            when = datetime.fromisoformat(_day(h)) if _day(h) else before
            if not groups or (when and before and when - before > PAUSE):
                groups.append([])
            groups[-1].append(m)
            before = when
        return next((g for g in groups if n in g), [n])

    def known(self) -> list[tuple[str, str]]:
        return sorted(self.kinds.items())

    def latest_topics(self) -> list[dict]:
        return [self.latest[k] for k in sorted(self.latest)]

    # --- finding, without walking everything ----------------------------------------------------

    def _vector(self, key: tuple, text: str):
        if key not in self._vectors:
            self._vectors[key] = list(next(iter(self.embed([text]))))
        return self._vectors[key]

    def near_topics(self, text: str, limit: int, touched=()) -> list[dict]:
        """The topics a text is about: those the given entries are in, then the nearest by meaning
        (or, without vectors, by the words they share)."""
        touched = set(touched)
        mine = [t for t in self.latest.values() if touched & set(t["entries"])]
        rest = [t for t in self.latest.values() if t not in mine]
        if not rest or limit <= len(mine):
            return mine[:max(limit, len(mine))]
        if self.embed is not None:
            try:
                q = self._vector(("q", text), text)
                def score(t):
                    v = self._vector((t["topic"], t["version"]), f"{t['name']}. {t['text']}")
                    dot = sum(a * b for a, b in zip(q, v))
                    return dot / (math.sqrt(sum(a * a for a in q)) * math.sqrt(sum(b * b for b in v)) or 1)
                self._vectors.pop(("q", text), None)
            except Exception:  # noqa: BLE001 - no vectors: the words
                score = None
        else:
            score = None
        if score is None:
            asked = set(_words(text).split())
            score = lambda t: len(asked & set(_words(t["name"] + " " + t["text"]).split()))  # noqa: E731
        return mine + sorted(rest, key=score, reverse=True)[:limit - len(mine)]

    def near_entities(self, text: str, dialogue=()) -> list[tuple[str, str]]:
        """The entities worth showing the reader of a text: the user's own people, those the
        dialogue so far mentioned, and those whose name is in the text — never all of them."""
        plain = f" {_words(text)} "
        out = {USER: "person"}
        for l in self.links_of.get(USER, []):
            if l["common"]:
                other = l["to"] if l["from"] == USER else l["from"]
                out[other] = self.kinds.get(other, "person")
        for n in dialogue:
            for m in self.by_text.get(n, []):
                out[m["entity"]] = m["kind"]
        for key, ms in self.by_entity.items():
            if len(out) >= SHOWN_ENTITIES:
                break
            if f" {_words(key)} " in plain:
                out[ms[0]["entity"]] = ms[0]["kind"]
        return list(out.items())[:SHOWN_ENTITIES]

    def image(self, name: str) -> dict:
        """One entity as the memory knows it now: every text that mentions it, the newest first."""
        held = {n: (h, t) for n, h, t in self.entries()}
        ms = self.by_entity.get(name.lower(), [])
        texts = sorted({m["text"] for m in ms if m["text"] in held}, reverse=True)
        said_as = sorted({m["as"] for m in ms if m["as"]})
        topics = [t for t in self.latest.values() if set(t["entries"]) & set(texts)]
        links = sorted(self.links_of.get(name.lower(), []), key=lambda l: l["text"], reverse=True)
        return {"name": name, "as": said_as, "links": links, "entries": [(n, _day(held[n][0])[:10], held[n][1]) for n in texts],
                "topics": topics}

    def facts_for(self, numbers: list[int], question: str = "") -> str:
        """For an answer: the topics the question is about — those the found entries are in, and the
        nearest by meaning, so "we talked about this last year" finds the talk even in other words —
        and the entities the found entries and the question name, each with what mentions it."""
        self.wait()
        asked = f" {_words(question)} "
        names = {m["entity"] for n in numbers for m in self.by_text.get(n, []) if m["entity"] != USER}
        names |= {ms[0]["entity"] for key, ms in self.by_entity.items()
                  if key != USER and _words(key) and f" {_words(key)} " in asked}
        topics = self.near_topics(question, 5, touched=numbers)
        if not names and not topics:
            return ""
        lines = []
        for t in topics:
            lines.append(f'Topic "{t["name"]}" (as of {t["day"][:10]}, version {t["version"]}, from facts '
                         f'{", ".join(map(str, t["entries"][-30:]))}): {t["text"]}')
        for name in sorted(names)[:20]:
            image = self.image(name)
            if not image["entries"]:
                continue
            said = f' (said as: {", ".join(image["as"][:4])})' if image["as"] else ""
            lines.append(f"{name}{said} — mentioned in facts "
                         + ", ".join(f"{n} [{day}]" for n, day, _ in image["entries"][:12]))
            for l in image["links"][:8]:
                lines.append(f'  {l["from"]} is the {l["relation"].replace("_", " ")} of {l["to"]} '
                             f'(fact {l["text"]} [{l["day"][:10]}]: "{l["quote"]}")')
        return IMAGE_HEAD.format(names="what the question bears on") + "\n" + "\n".join(lines) if lines else ""
