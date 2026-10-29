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
               time — a skeleton, not a fence: any other relation the entry states is kept too;
               a link from the user to what they did, have, like, plan or how a thing stands for
               them now carries the day it happened when said, and one of five classes (CLASSES)
               the decision model gives it — the same skeleton, over what the user says of themselves

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
from concurrent.futures import ThreadPoolExecutor
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
# The words a user calls their people by, to find "my wife" as the one the memory knows as the user's
# spouse.
CALLED = {
    "spouse": {"wife", "husband"}, "partner": {"partner", "boyfriend", "girlfriend"},
    "parent": {"mother", "father", "mom", "mum", "dad"}, "child": {"son", "daughter", "kid", "kids"},
    "sibling": {"brother", "sister"}, "friend": {"friend"}, "colleague": {"colleague", "coworker"},
    "manager": {"boss", "manager"}, "pet": {"dog", "cat", "pet"},
}
# Recalling a topic beside the user's message: sure enough to say where it stood, or only to name it
# in a line, for the agent to `ask` if it needs it — as a person who is sure says "oh, I thought about
# this", and one who is not keeps it in mind.
SURE, POSSIBLE = 0.7, 0.3
# The words a reader may write for the user; every one of them is the user, by code.
SELF = {"the user", "user", "i", "me", "myself", "we", "us", "the user s"}
# The user's personal world, half fixed: what every person can have, the same for the user and for
# each of their people, each a link the reader names the same way every time, so that it can be
# followed and gathered into a person's image. One value at a time (the newest holds, the older kept
# as was), or a list (each item holds until an entry ends it). Whatever does not fit is kept too,
# under the reader's own name for it: a skeleton, not a fence.
#
# A person's people, read "<from> is the <relation> of <to>".
PEOPLE = {
    "spouse": ("one", "husband or wife"), "partner": ("one", "partner, boyfriend or girlfriend"),
    "child": ("many", "son or daughter"), "parent": ("many", "mother or father"),
    "sibling": ("many", "brother or sister"), "relative": ("many", "another relative"),
    "friend": ("many", "friend"), "colleague": ("many", "colleague"),
    "manager": ("one", "manager or boss"), "pet": ("many", "pet animal"),
}
# What a person has and is, read "<from> <relation> <to>"; "to" may be a value in the entry's words.
OWN = {
    "born_on": ("one", "birthday or date of birth (to: the date as said)"),
    "age": ("one", "age (to: as said)"), "lives_in": ("one", "lives in (to: a place)"),
    "works_at": ("one", "works at or for (to: an organisation)"), "job": ("one", "occupation or role"),
    "studies_at": ("one", "studies at"), "owns": ("many", "has or owns (to: the thing)"),
    "skill": ("many", "can do, a skill"), "speaks": ("many", "speaks a language"),
    "hobby": ("many", "a hobby or pastime"), "health": ("many", "an allergy, condition or diet"),
    "likes": ("many", "likes or loves"), "dislikes": ("many", "dislikes"),
}
RELATIONS = {k: v for k, (_, v) in (PEOPLE | OWN).items()}
# Which parts of a person's world an entry speaks of, asked of the decision model down a tree: a group
# first, then the parts of the groups it says yes to — about ten closed questions for an entry instead
# of one for every part. The reader is then told which parts to fill: what it is not pointed at, it
# misses ("My wife Mila's birthday…" gave the birthday and lost the wife).
GROUPS = {
    "family": ("family or pets: a husband or wife, a partner, children, parents, brothers or sisters, other "
               "relatives, a pet", ["spouse", "partner", "child", "parent", "sibling", "relative", "pet"]),
    "people": ("friends, colleagues or a boss", ["friend", "colleague", "manager"]),
    "work": ("work or study: where someone works or studies, or someone's job", ["works_at", "job", "studies_at"]),
    "home": ("where someone lives or moved to live", ["lives_in"]),
    "things": ("things someone has: bought, got, owns, sold or gave away", ["owns"]),
    "self": ("personal details of anyone, the user included: a birthday, an age, skills, languages, hobbies, "
             "health, diet, what they like, love, prefer or dislike",
             ["born_on", "age", "skill", "speaks", "hobby", "health", "likes", "dislikes"]),
}
# How each part is asked about, in plain words.
PART_WORDS = {
    "spouse": "a husband or wife", "partner": "a partner, boyfriend or girlfriend", "child": "a son or daughter",
    "parent": "a mother or father", "sibling": "a brother or sister",
    "relative": "another relative: a grandparent, cousin, aunt, uncle, in-law", "pet": "a pet animal",
    "friend": "a friend", "colleague": "a colleague", "manager": "a boss or manager",
    "works_at": "where someone works", "job": "someone's job or occupation", "studies_at": "where someone studies",
    "lives_in": "where someone lives", "owns": "something someone has, bought, got, sold or gave away",
    "born_on": "someone's birthday or date of birth", "age": "someone's age", "skill": "something someone can do",
    "speaks": "a language someone speaks", "hobby": "a hobby or pastime",
    "health": "an allergy, illness, condition or diet", "likes": "something someone likes, loves or prefers",
    "dislikes": "something someone dislikes",
}
# The closing of a part is asked once, beside the groups.
ENDED = "something that no longer holds: sold, gave away, replaced, left a job, moved out, broke up"
# "The user is the parent of Lev" says Lev is the user's child.
INVERSE = {"child": "parent", "parent": "child", "spouse": "spouse", "partner": "partner", "sibling": "sibling",
           "friend": "friend", "colleague": "colleague", "relative": "relative"}
# The words a message speaks of a part of a person's world by, beside the names of what fills it.
SLOT_WORDS = {
    "born_on": {"birthday", "born"}, "age": {"age", "old"},
    "lives_in": {"live", "lives", "home", "flat", "apartment", "house", "city", "move", "moving"},
    "works_at": {"work", "works", "job", "office", "company", "employer"}, "job": {"job", "work", "career"},
    "studies_at": {"study", "studies", "school", "university", "course"}, "skill": {"skill", "skills", "learn"},
    "speaks": {"language", "languages", "speak"}, "hobby": {"hobby", "hobbies"},
    "health": {"allergy", "allergic", "diet", "health", "doctor"},
    "likes": {"gift", "present", "favourite", "favorite"}, "dislikes": {"gift", "present"},
}
# What the user says of themselves, in five classes: a question asks for one of them — what happened
# in a window, how many, how it stands now, what a suggestion should take into account. The relation
# stays the reader's own word ("planted"); the class is a closed question to the decision model.
CLASSES = {
    "did": "something the user did, got, bought, made or went to, or that happened to them",
    "has": "something the user has or owns",
    "likes": "what the user likes or prefers, can do, or how something went for them",
    "plans": "what the user plans, wants or means to do",
    "now": "how something stands for the user now and may change later: a habit, a time, an amount, a state",
}
# A topic's kind says what an answer takes from it: a choice — what was chosen and ruled out; a
# habit — how it stands now; an interest — what a suggestion should take into account.
TOPIC_KINDS = {
    "choice": "choosing something: a product, a place, an option",
    "problem": "a problem the user deals with: health, money, a conflict",
    "project": "a project or plan: a business, a trip, a move, an event",
    "habit": "a habit or routine: sleep, food, exercise, spending",
    "interest": "a hobby or interest the user keeps up",
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
 "links": [{{"from": "<entity>", "relation": "...", "to": "<entity>", "quote": "the entry's exact words that say it", "when": "YYYY-MM-DD, only when said", "ended": false}}],
 "topics": [{{"topic": <id, or "new">, "name": "a short name", "text": "the topic's whole new text"}}]}}

Entities: the people, places, things, organisations and events the entry names. "I", "me", "my" \
are "{user}"; so are "we" and "us", with whoever the entry says is with them as entities of their own. \
Give a known entity its known name. A person is named by their name when the entry or the \
conversation says it ("My wife Mila" is "Mila", with a link "Mila — spouse — {user}"); by their \
relation to the user ("the user's sister") only when no name is said. A particular product, model, \
brand, place or event is its own entity ("Sony TV", "Samsung S90D"), never folded into a general \
one ("TV"). Take a kind in use before \
making a new one; a kind is one or two plain words.
The parts of a person's world this entry speaks of, as a first reading found: {parts}. Give a link \
for each of them that the entry says, for whoever it says it of.
Links: what the entry says joins two entities. A person's people, read "<from> is the <relation> of \
<to>": {people}. What a person has and is, read "<from> <relation> <to>", where "to" may be a value \
in the entry's own words (a date, a place, a skill): {own}. Use these names when they fit, for the \
user and for anyone else. The relation is what <from> is to <to>: "our son Lev" is "Lev — child → \
{user}", "my mother" is "<her name> — parent → {user}", "our dog Rex" is "Rex — pet → {user}"; \
"Mila — born_on → 3 May", "{user} — owns → LG C4". Otherwise name the \
relation in a word or two ("landlord", "coach", "gave the gift to"). When the entry says a link no \
longer holds — sold, gave away, replaced, went with another instead, broke up, moved out, left the \
job — give that link with "ended": true. Also link "{user}" to what the entry says the user did, got, has, likes or can do, plans, or how a thing stands for them now — "{user} — planted → tomato saplings", "{user} — wakes up at → 8:30 am on Saturdays", "{user} — owns → utensil holder" — with "to" in the entry's own words, and "when": the day it happened, YYYY-MM-DD, when the entry says when (today, last Saturday, two weeks ago — counted from the day the entry was said). Only what the entry says.
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
              "and days; the newest says what holds now). A topic's text is the memory's summary: where "
              "it and a fact disagree, the fact holds:")


def _day(heading: str) -> str:
    parts = heading.split(" · ")
    return parts[1] if len(parts) > 1 else ""


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(text).lower()).split())


def _label(name: str) -> str:
    """"user's wife", "The user's wife" -> "the user's wife": one way to name someone not yet named."""
    got = re.fullmatch(r"(?:the\s+)?user'?s\s+(\w+)", name.strip(), re.I)
    return f"the user's {got.group(1).lower()}" if got else name


def unnamed(name: str) -> bool:
    """Someone the memory knows only by what they are to the user: "the user's wife"."""
    return name.startswith("the user's ")


def _named(name) -> str:
    """The name as kept: the user under one name, whatever the reader wrote for them."""
    name = str(name or "").strip()
    return USER if _words(name) in SELF else _label(name)


class Graph:
    """The mentions and topics of one memory, under `where`; `entries()` gives the journal as
    (number, heading, text). `wake()` after every kept entry; `wait()` before reading the graph."""

    def __init__(self, where: Path, entries, reader=None, embed=None, decide=None, goes_on=None, about=None):
        self.where = Path(where)
        self.where.mkdir(parents=True, exist_ok=True)
        self.entries = entries
        self.reader = reader or (lambda system, prompt: role("reader").json(system, prompt, room=8000))
        # A closed question over named options -> the option: the decision model, one token.
        self.decide = decide or (lambda state, question, options: role("judge").choice(state, question, options)["choice"])
        # How likely the entry speaks of this — a group or a part of a person's world: the decision
        # model, yes or no, the entry first so that every question about it shares its beginning.
        self.about = about or (lambda text, what: role("judge").noul(
            f'What the user said: "{text}"', f"Does what the user said mention {what}?",
            "yes, it mentions that", "no, it does not")["p"]["yes"])
        # How likely this message goes on with this topic: the decision model, yes or no.
        self.goes_on = goes_on or (lambda message, t: role("judge").noul(
            f'A topic the user talked about before, "{t["name"]}": {t["text"]}\n\nThe user now says: "{message}"',
            "Does the user's message go on with this topic, the same matter?", "yes, the same matter",
            "no, another matter")["p"]["yes"])
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
        # Who an unnamed one turned out to be: "the user's wife" is Mila, from the fact that named her.
        # A join, kept as its own row with its fact, so that it can be undone.
        self.aliases = {r["label"].lower(): r for r in self._lines("aliases.jsonl")}
        state = self.where / "state.json"
        self.read_upto = json.loads(state.read_text())["read_upto"] if state.exists() else 0
        # Indexes, so that finding by an entity, an entry or a topic never walks everything.
        self.by_entity, self.by_text, self.links_of, self.latest, self.kinds = {}, {}, {}, {}, {}
        self._index(self.mentions, self.links, self.topics)

    def canon(self, name: str) -> str:
        """The name the memory knows someone by now: an unnamed one, once named, by their name."""
        seen = set()
        while name.lower() in self.aliases and name.lower() not in seen:
            seen.add(name.lower())
            name = self.aliases[name.lower()]["to"]
        return name

    def _index(self, mentions, links, topics) -> None:
        # The indexes hold every mention and link under the names known now; what was kept on disk
        # stays as it was read, so a join undone is the indexes built again.
        for m in mentions:
            m = {**m, "entity": self.canon(m["entity"])}
            self.by_entity.setdefault(m["entity"].lower(), []).append(m)
            self.by_text.setdefault(m["text"], []).append(m)
            self.kinds.setdefault(m["entity"], m["kind"])
        for l in links:
            l = {**l, "from": self.canon(l["from"]), "to": self.canon(l["to"])}
            if l["from"] == l["to"]:
                continue
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
            for name in ("mentions.jsonl", "links.jsonl", "topics.jsonl", "aliases.jsonl", "world.json", "state.json"):
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
        parts = self.parts_of(text)
        got = self.reader("Answer with JSON only.", READ.format(
            entities="\n".join(f"- {name} — {kind}" for name, kind in entities) or "none yet",
            kinds=", ".join(sorted(set(self.kinds.values()))[:60]) or "none yet",
            topics="\n".join(f"{t['topic']}. {t['name']}: {t['text']}" for t in topics) or "none yet",
            dialogue="\n".join(f"{m}. {t}" for m, t in earlier) or "nothing yet", day=_day(heading)[:10], entry=text,
            user=USER, people="; ".join(f"{k} ({v})" for k, (_, v) in PEOPLE.items()),
            own="; ".join(f"{k} ({v})" for k, (_, v) in OWN.items()),
            parts=(", ".join(parts) if parts else "none of them") + "")) or {}
        with self.lock:
            links, versions = self._keep_reading(n, heading, text, dialogue[0], got)
        self._classify(text, links, versions)
        with self.lock:
            self.read_upto = n
            (self.where / "state.json").write_text(json.dumps({"read_upto": n}))
        return True

    def parts_of(self, text: str) -> list[str]:
        """The parts of a person's world the entry speaks of, down the tree: the groups, then the parts
        of those it says yes to; and whether something ended. Asked at once, each a closed question."""
        def ask(what):
            try:
                return float(self.about(text, what))
            except Exception:  # noqa: BLE001 - unasked is not a part
                log.exception("asking about a part failed")
                return 0.0
        with ThreadPoolExecutor(8) as pool:
            questions = [g for g, _ in GROUPS.values()] + [ENDED]
            said = dict(zip(list(GROUPS) + ["ended"], pool.map(ask, questions)))
            asked = [part for g, (_, ps) in GROUPS.items() if said[g] >= 0.5 for part in ps]
            if not asked:
                return ["ended"] if said["ended"] >= 0.5 else []
            got = dict(zip(asked, pool.map(ask, [PART_WORDS[p] for p in asked])))
        return [p for p in asked if got[p] >= 0.5] + (["something that ended"] if said["ended"] >= 0.5 else [])

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
            a, b = (named.get(self.canon(_named(l.get(end))).lower()) for end in ("from", "to"))
            to = re.sub(r"^(the|a|an|our|my|his|her|their)\s+", "", str(l.get("to") or "").strip(), flags=re.I)
            if a and relation in OWN:
                # "the Samsung" for the "Samsung TV" the person already has: the item it names.
                items = {x["to"] for x in self.links_of.get(a.lower(), []) + links if x["from"] == a and x["relation"] == relation}
                words = set(_words(b or to).split())
                same = next((x for x in items if words and words <= set(_words(x).split())), None)
                if same and b not in items:
                    b = same
            if a and not b and _words(to) and _words(to) in plain and (a == USER or relation in OWN):
                # What a person has or is, and what the user did or likes, is named in the entry's own
                # words: a thing is a mention of it; a date or an age is a value only.
                b = to
                if relation == "owns" or (a == USER and relation not in OWN):
                    mentions.append({"text": n, "dialogue": dialogue, "day": day, "entity": to, "kind": "thing", "as": to})
            if a and b and a != b and _words(l.get("quote")) and _words(l["quote"]) in plain:
                when = str(l.get("when") or "")
                links.append({"from": a, "relation": relation, "common": relation in RELATIONS, "to": b, "text": n, "day": day,
                              "quote": l["quote"], **({"when": when} if re.fullmatch(r"\d{4}-\d{2}-\d{2}", when) else {}),
                              **({"ended": True} if l.get("ended") is True else {})})
        # "My wife Mila", "our son Lev", "Mila, my wife": the user's people, by code, whatever the
        # reader gave — the plainest fact of a personal memory, never left to a model's attention.
        have = {(l["from"], l["relation"], l["to"]) for l in links}
        for m in mentions:
            if m["entity"] == USER or m["kind"] not in ("person", "animal", "dog", "cat", "pet"):
                continue
            name = re.escape(m["entity"])
            for relation, words in CALLED.items():
                called = "|".join(sorted(words))
                said = (re.search(rf"\b(?:my|our)\s+(?:\w+\s+)?(?:{called})\s*,?\s*(?:called\s+|named\s+)?{name}\b", text, re.I)
                        or re.search(rf"\b{name}\s*,?\s*(?:is\s+)?(?:my|our)\s+(?:\w+\s+)?(?:{called})\b", text, re.I))
                if said and (m["entity"], relation, USER) not in have:
                    links.append({"from": m["entity"], "relation": relation, "common": True, "to": USER, "text": n,
                                  "day": day, "quote": said.group(0)})
                    have.add((m["entity"], relation, USER))
        # "My wife…" with no name said: the user has a wife, whose name the memory does not know yet.
        # She is "the user's wife" until an entry names her; then the two are joined (_settle_people).
        for relation, words in CALLED.items():
            for word in sorted(words):
                for said in re.finditer(rf"\b(?i:my|our)\s+(?:\w+\s+)?(?i:{word})\b(?!\s*,?\s*(?:called\s+|named\s+)?[A-Z])", text):
                    label = f"the user's {word.lower()}"
                    # "Mila, my wife": the wife is named in this very entry.
                    if any(l["relation"] == relation and l["to"] == USER and (l["from"] == label or not unnamed(l["from"]))
                           for l in links):
                        continue
                    if not any(m["entity"] == label for m in mentions):
                        mentions.append({"text": n, "dialogue": dialogue, "day": day, "entity": label,
                                         "kind": "animal" if relation == "pet" else "person", "as": said.group(0)})
                    links.append({"from": label, "relation": relation, "common": True, "to": USER, "text": n,
                                  "day": day, "quote": said.group(0)})
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
                             "version": (before or {}).get("version", 0) + 1,
                             **({"kind": before["kind"]} if before and before.get("kind") else {})})
        self.mentions += mentions
        self._index(mentions, [], [])
        self._append("mentions.jsonl", mentions)
        return links, versions

    def _classify(self, text: str, links: list[dict], versions: list[dict]) -> None:
        """The closed questions, to the decision model and outside the lock: the class of each thing
        the user says of themselves, the kind of each new topic. Then the links and topics are kept."""
        def classify(l):
            try:
                l["class"] = self.decide(
                    f'What the user said: "{text}"\n\nRead from it: the user {l["relation"].replace("_", " ")} {l["to"]} '
                    f'("{l["quote"]}")', "Which is this, of what the user says of themselves?", list(CLASSES.items()))
            except Exception:  # noqa: BLE001 - a link without a class is still a link
                log.exception("classifying a link failed")
        own = [l for l in links if l["from"] == USER and not l["common"]]
        if own:
            # One entry's links at once: a long history told in one go is read in hours otherwise.
            with ThreadPoolExecutor(min(8, len(own))) as pool:
                list(pool.map(classify, own))
        for t in versions:
            if "kind" not in t:
                try:
                    t["kind"] = self.decide(f'A topic the user keeps coming back to: "{t["name"]}": {t["text"]}',
                                            "Which kind of topic is this?", list(TOPIC_KINDS.items()))
                except Exception:  # noqa: BLE001 - a topic without a kind is still a topic
                    log.exception("classifying a topic failed")
        with self.lock:
            self.links += links
            self.topics += versions
            self._index([], links, versions)
            self._append("links.jsonl", links)
            self._append("topics.jsonl", versions)
            if links:
                self._settle_people(links[0]["text"], links[0]["day"])
                self._write_world()

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
            if l["relation"] in PEOPLE:
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

    # The user's people a join may be made in: one of each is common ("my sister" and "my sister Ana"
    # are one when she is the only sister the memory knows); friends and colleagues are many.
    JOINABLE = {"spouse", "partner", "manager", "child", "parent", "sibling", "pet"}

    def _settle_people(self, n: int, day: str) -> None:
        """An unnamed one of the user's people and a named one in the same place of the user's world
        are one person, when the place holds one (a spouse) or the memory knows only one of each
        there: "the user's wife" is Mila. Joined by a row of its own, with the fact that made it."""
        joined = False
        for relation in self.JOINABLE:
            now = sorted({(l["from"] if l["to"] == USER else l["to"]) for l in self.links_of.get(USER, [])
                          if not l.get("ended") and ((l["relation"] == relation and l["to"] == USER)
                                                     or (l["relation"] == INVERSE.get(relation) and l["from"] == USER))})
            labels, names = [o for o in now if unnamed(o)], [o for o in now if not unnamed(o)]
            if len(names) == 1 and (PEOPLE[relation][0] == "one" or len(labels) == 1):
                for label in labels:
                    row = {"label": label, "to": names[0], "relation": relation, "fact": n, "day": day}
                    self.aliases[label.lower()] = row
                    self._append("aliases.jsonl", [row])
                    joined = True
        if joined:
            self.by_entity, self.by_text, self.links_of, self.kinds = {}, {}, {}, {}
            self._index(self.mentions, self.links, [])

    def world(self) -> dict:
        """The user's world as a structure: every person the memory knows of, each with every part a
        person has — filled or empty — and in each what holds now and what was, with facts and days."""
        people = [USER] + sorted({e for e, k in self.kinds.items() if e != USER and k in ("person", "animal", "dog", "cat", "pet")})
        out = {}
        for name in people:
            parts = self.world_of(name)
            entry = lambda o, l: {"value": o, **({"kind": self.kinds[o]} if o in self.kinds and o not in people else {}),  # noqa: E731
                                  "fact": l["text"], "day": l["day"][:10], "quote": l["quote"],
                                  **({"ended": True} if l.get("ended") else {})}
            out[name] = {"named": not unnamed(name), "kind": self.kinds.get(name, "person"),
                         "known_as": sorted(r["label"] for r in self.aliases.values() if r["to"] == name),
                         "parts": {r: {"size": size, "now": [entry(o, l) for o, l in parts.get(r, {}).get("now", [])],
                                       "was": [entry(o, l) for o, l in parts.get(r, {}).get("was", [])]}
                                   for r, (size, _) in (PEOPLE | OWN).items()}}
        return out

    def _write_world(self) -> None:
        (self.where / "world.json").write_text(json.dumps(self.world(), ensure_ascii=False, indent=1))

    def world_of(self, name: str) -> dict:
        """A person's world as the memory knows it now, by the fixed parts every person has: for each,
        what holds (the newest for a one-value part; every item not ended for a list) and what was,
        each with the fact and the day it stands on. Built when asked for, never stored."""
        key = name.lower()
        parts = {}
        for relation, (size, _) in (PEOPLE | OWN).items():
            said = []
            for l in self.links_of.get(key, []):
                if l["relation"] == relation and relation in PEOPLE and l["to"].lower() == key:
                    said.append((l["from"], l))
                elif relation in OWN and l["relation"] == relation and l["from"].lower() == key:
                    said.append((l["to"], l))
                elif relation in INVERSE and l["relation"] == INVERSE[relation] and l["from"].lower() == key:
                    said.append((l["to"], l))
            if not said:
                continue
            newest = {}
            for other, l in sorted(said, key=lambda x: x[1]["text"]):
                newest[other.lower()] = (other, l)
            ordered = sorted(newest.values(), key=lambda x: x[1]["text"], reverse=True)
            now = [x for x in ordered if not x[1].get("ended")]
            was = [x for x in ordered if x[1].get("ended")]
            if size == "one":
                now, was = now[:1], now[1:] + was
            parts[relation] = {"now": now, "was": was}
        # A pet or a person is not a thing owned, though "we have a beagle" says both.
        people = {o.lower() for r in PEOPLE if r in parts for o, _ in parts[r]["now"] + parts[r]["was"]}
        if "owns" in parts:
            parts["owns"] = {k: [x for x in v if x[0].lower() not in people] for k, v in parts["owns"].items()}
            if not parts["owns"]["now"] and not parts["owns"]["was"]:
                del parts["owns"]
        return parts

    def world_lines(self, name: str, only=None, gaps: bool = False) -> list[str]:
        """The person's world as lines for a reader; `only` some parts of it."""
        parts = self.world_of(name)

        def item(other, l):
            kind = self.kinds.get(other)
            return (f'{other}{" (name not known yet)" if unnamed(other) else ""}'
                    f'{f" [{kind}]" if kind and kind not in ("thing", "person") else ""} (fact {l["text"]}, {l["day"][:10]})')
        lines = []
        for relation, got in parts.items():
            if only is not None and relation not in only:
                continue
            line = f'  {relation.replace("_", " ")}: ' + ("; ".join(item(o, l) for o, l in got["now"][:8]) or "none now")
            if got["was"]:
                line += "; was: " + "; ".join(item(o, l) + (" — ended" if l.get("ended") else "") for o, l in got["was"][:4])
            lines.append(line)
        if gaps and only is None:
            missing = [r.replace("_", " ") for r in ("spouse", "child", "born_on", "lives_in", "works_at", "job") if r not in parts]
            missing += [f"the name of {o}" for got in parts.values() for o, _ in got["now"] if unnamed(o)]
            if missing:
                lines.append("  not known yet: " + ", ".join(missing))
        if not lines:
            return []
        return [f"{name}'s world as the memory knows it now (the newest holds; what ended or was replaced is under \"was\"):"] + lines

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
        if not names and not topics and not self.links_of.get(USER):
            return ""
        lines = []
        for t in topics:
            kind = f'{t["kind"]}, ' if t.get("kind") else ""
            lines.append(f'Topic "{t["name"]}" ({kind}as of {t["day"][:10]}, version {t["version"]}, from facts '
                         f'{", ".join(map(str, t["entries"][-30:]))}): {t["text"]}')
        lines += self._said_of_self(set(numbers) | {n for t in topics for n in t["entries"]})
        lines += self.world_lines(USER, gaps=True)
        for name in sorted(names):
            if self.kinds.get(name) == "person":
                lines += self.world_lines(name)
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

    def recall(self, message: str, numbers=(), limit: int = 2) -> str:
        """For the agent, beside the user's message: the topics it goes on with, said as a talk had
        before — where it stood and when it was last on — for the agent to bring up as it sees fit.
        Candidates are the topics of this dialogue's entries and of the entries found for the
        message, and the nearest by meaning, so a matter comes back in other words a month later;
        the decision model keeps those the message goes on with, since the nearest topic by meaning
        is always some topic. Never waits for the reading: what is read by now is what is given."""
        held = self.entries()
        recent = self.dialogue_of(held[-1][0], held) if held else []
        if held and _day(held[-1][1]):
            # The dialogue of the last entry only while it is going on.
            if datetime.now() - datetime.fromisoformat(_day(held[-1][1])) > PAUSE:
                recent = []
        touched = set(numbers) | set(recent)
        with self.lock:
            candidates = self.near_topics(message, len([t for t in self.latest.values() if touched & set(t["entries"])]) + 3,
                                          touched=touched)
        sure, possible = [], []
        for t in candidates:
            try:
                p = float(self.goes_on(message, t))
            except Exception:  # noqa: BLE001 - no decision model: the topics its entries are in
                log.exception("deciding a topic failed")
                p = 1.0 if touched & set(t["entries"]) else 0.0
            if p >= SURE and len(sure) < limit:
                sure.append(t)
            elif p >= POSSIBLE and len(possible) < 3:
                possible.append(t)
        lines = []
        for t in sure:
            lines.append(f'We discussed this before: "{t["name"]}", last on {t["day"][:10]} (facts '
                         f'{", ".join(map(str, t["entries"][-30:]))}). Where it stood: {t["text"]}')
        if sure:
            with self.lock:
                lines += self._said_of_self(set(n for t in sure for n in t["entries"]), limit=15)
        for t in possible:
            lines.append(f'Possibly related: "{t["name"]}", last on {t["day"][:10]} — ask the memory if it matters.')
        lines += self._world_spoken_of(message)
        lines += self._known_of(message, set(recent))
        if not lines:
            return ""
        lines.append("How and whether to bring this up with the user is yours to decide.")
        return "\n".join(lines)

    def _world_spoken_of(self, message: str) -> list[str]:
        """The parts of the user's world the message speaks of: "my car", "the TV", "my birthday",
        "work" — by the part's own words or by the kinds and names of what fills it."""
        plain = f" {_words(message)} "
        with self.lock:
            parts = self.world_of(USER)
            spoken = set()
            for relation, got in parts.items():
                words = SLOT_WORDS.get(relation, set()) | {w for r, ws in CALLED.items() if r == relation for w in ws}
                for other, _ in got["now"] + got["was"]:
                    words |= {_words(other)} | ({_words(self.kinds[other])} if other in self.kinds else set())
                if any(w and f" {w} " in plain for w in words):
                    spoken.add(relation)
            return self.world_lines(USER, only=spoken) if spoken else []

    def _known_of(self, message: str, now_said: set[int], limit: int = 4) -> list[str]:
        """The people and things the message names that the memory knows from before — by their name,
        or as the user calls them ("my wife" is the user's spouse) — each with its links and the last
        time it was spoken of, in the user's words. What this dialogue said, the agent has already."""
        plain = f" {_words(message)} "
        with self.lock:
            names = [ms[0]["entity"] for key, ms in self.by_entity.items()
                     if key != USER and _words(key) and f" {_words(key)} " in plain]
            for l in self.links_of.get(USER, []):
                other = l["from"] if l["to"] == USER else l["to"]
                if l["common"] and other != USER and any(f" {w} " in plain for w in CALLED.get(l["relation"], ())):
                    names.append(other)
        held = {n: (h, t) for n, h, t in self.entries()}
        out, seen = [], set()
        for name in names:
            if name in seen or len(seen) >= limit:
                continue
            seen.add(name)
            with self.lock:
                image = self.image(name)
            before = [(n, day, text) for n, day, text in image["entries"] if n not in now_said and n in held]
            if not before:
                continue
            if not out:
                out.append("Known from before:")
            n, day, text = before[0]
            links = [f'{l["from"]} is the {l["relation"].replace("_", " ")} of {l["to"]}' for l in image["links"][:4]]
            out.append(f'- {name} ({self.kinds.get(name, "thing")})' + (f': {"; ".join(links)}' if links else "")
                       + f'. Spoken of {len(before)} time{"s" if len(before) > 1 else ""}, last on {day}: "{text}" (fact {n})')
            if self.kinds.get(name) == "person":
                with self.lock:
                    out += ["  " + line for line in self.world_lines(name)[1:]]
        return out

    def _said_of_self(self, texts: set[int], limit: int = 80) -> list[str]:
        """What the user said of themselves in these facts, by class, the newest first: every one, not
        the few most alike to the question — so "how many" counts them all and "two weeks ago" finds
        the day. Each with the entry's own words; a topic's text cannot stand in for them."""
        own = [l for l in self.links_of.get(USER, []) if l["from"] == USER and l["text"] in texts and not l["common"]]
        if not own:
            return []
        out = ["What the user said of themselves in these facts (the entry's words; the newest first):"]
        for name, what in list(CLASSES.items()) + [("other", "not classed")]:
            these = sorted((l for l in own if l.get("class", "other") == name), key=lambda l: l["text"], reverse=True)
            if these:
                out.append(f"  {name} — {what}:")
            for l in these[:limit]:
                when = f', happened {l["when"]}' if l.get("when") else ""
                out.append(f'  - {l["relation"].replace("_", " ")} {l["to"]}: "{l["quote"]}" (fact {l["text"]}, '
                           f'said {l["day"][:10]}{when})')
        return out
