"""What the world solves a task with: a few tools that know about correctness and nothing about
any particular task.

The world's model writes a program from these (memory/solve.py) and decides which it needs — a
question about the user's colleagues is answered from the memory's links and never searches; a
purchase gathers candidates from the web first. What makes an answer right lives in the tools, so
no program can skip it:

- `parse` keeps a value or a link only on the text's own words, checked by code and by the
  decision model (memory/parse.py);
- `select` never reads "not known" as "no";
- `search` refuses a query that names anyone the user's memory holds;
- everything kept has its sentence and its source.

The user's memory is `memory`; a collection gathered for a task is a shelf — the same kind of
store under the memory's directory (collections/), so a thousand products don't crowd the user's
life. A collection outlives the task, so what was found can still be asked about, but a task
chooses only from what was found lately (FRESH) — what reuses is the program, not stale prices.
Not for good either: a thing found lives TTL (memory/ttl.py) from its last use — found or read by a
task — unless it has been with the user: named in an answer the agent got, or in the user's memory.
Those have no TTL. What is past its TTL is removed, its texts with it, by the cleaner
(memory/cleaner.py).
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

from memory import parse as parsing
from memory.models import role
from memory.model import Structure, Thing
from memory.ttl import TTL

ENGINE = "tavily"
# What holds for every thing of a class, whatever the task: its fields, and which must be known.
TAVILY = "https://api.tavily.com/search"


def tavily(query: str, pages: int) -> list[dict]:
    """Pages for a query straight from Tavily, with their text: what `ait-search` (the author's own
    search tool, which also keeps every page it found) does through Tavily, for a machine without it."""
    body = json.dumps({"query": query, "max_results": max(pages, 5), "include_raw_content": True}).encode()
    request = urllib.request.Request(TAVILY, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"})
    with urllib.request.urlopen(request, timeout=120) as answer:
        found = json.loads(answer.read()).get("results", [])
    return [{"url": r["url"], "title": r.get("title"), "published": r.get("published_date"),
             "text": r.get("raw_content") or r.get("content") or ""} for r in found if r.get("url")][:pages]


CLASSES = json.loads((Path(__file__).with_name("classes.json")).read_text())
# What a task chooses from: what was found within this long. A day old, a price or a date still
# holds for a few days; older, it may not.
FRESH = timedelta(days=3)
# Kinds that are places: a query may name them.
PLACES = {"place", "city", "town", "country", "region", "district", "neighbourhood", "neighborhood"}


class Journal:
    """A shelf's texts: numbered entries, kept in memory and appended to a file."""

    def __init__(self, path: Path):
        self.path, self.entries = path, {}
        if path.exists():
            for part in path.read_text().split("## #")[1:]:
                heading, _, text = part.partition("\n")
                number = heading.partition(" · ")[0]
                if number.isdigit():
                    self.entries[int(number)] = f"{heading.partition(' · ')[2]}: {' '.join(text.split())}"

    def keep(self, text: str, source: str, told: datetime | None = None) -> int:
        number = max(self.entries, default=0) + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as file:
            file.write(f"## #{number} · {told or datetime.now():%Y-%m-%d %H:%M:%S} · {source}\n{text}\n\n")
        self.entries[number] = f"{source}: {' '.join(text.split())}"
        return number

    def drop(self, numbers: set[int]) -> None:
        """Remove these entries from the file and from memory, for good."""
        if not numbers or not self.path.exists():
            return
        parts = self.path.read_text().split("## #")
        kept = [x for x in parts[1:] if not (x.partition(" · ")[0].isdigit() and int(x.partition(" · ")[0]) in numbers)]
        self.path.write_text(parts[0] + "".join("## #" + x for x in kept))
        for n in numbers:
            self.entries.pop(n, None)


class Shelf:
    """A collection gathered for a task: things, their values and links, each with its text."""

    def __init__(self, path: Path, session: str = "world", of: str | None = None):
        self.path, self.of = path, of if of in CLASSES else None
        self.journal = Journal(path / "facts.md")
        self.structure = Structure(path / "structure.jsonl", self.journal.keep, lambda: self.journal.entries)
        self.session = session

    def things(self, kind: str | None = None) -> list[Thing]:
        return self.structure.things(self.session, kind)

    # --- use: what keeps a thing alive -------------------------------------------------------

    def _uses(self) -> dict:
        if not hasattr(self, "_used"):
            file = self.path / "used.json"
            self._used = json.loads(file.read_text()) if file.exists() else {}
        return self._used

    def _save_uses(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "used.json").write_text(json.dumps(self._uses(), ensure_ascii=False, indent=0))

    def use(self, things, lasting: str | None = None) -> None:
        """Mark these things used now; `lasting` says why they have no TTL any more."""
        now, uses = f"{datetime.now():%Y-%m-%d %H:%M:%S}", self._uses()
        for t in things:
            mark = uses.setdefault(t.id, {})
            mark["used"] = now
            if lasting and not mark.get("lasting"):
                mark["lasting"] = lasting
        self._save_uses()

    def last_use(self, thing: Thing) -> str | None:
        """The last time it was found or read by a task."""
        return max(filter(None, (self.structure.dates(thing)["changed"], self._uses().get(thing.id, {}).get("used"))),
                   default=None)

    def lasting(self, thing: Thing) -> str | None:
        """Why it has no TTL — it has been with the user — or None."""
        return self._uses().get(thing.id, {}).get("lasting")

    def expire(self, spoken, now: datetime | None = None) -> list[str]:
        """Remove every thing not used for TTL that has not been with the user — no lasting mark,
        and `spoken(name)` doesn't hold — with the records and texts about it. Returns the names."""
        cut = f"{(now or datetime.now()) - TTL:%Y-%m-%d %H:%M:%S}"
        gone = {t.id: t.name for t in self.things()
                if t.name != "the user" and (self.last_use(t) or "") < cut and not self.lasting(t) and not spoken(t.name)}
        if not gone:
            return []
        for id_ in gone:
            self._uses().pop(id_, None)
        self._save_uses()
        records = self.structure.records
        out = [r for r in records if r.get("thing") in gone or set(r.get("about") or ()) & set(gone)]
        stay = [r for r in records if r not in out]
        self.journal.drop({r["entry"] for r in out if "entry" in r} - {r["entry"] for r in stay if "entry" in r})
        self.structure.records = stay
        self.structure.path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in stay))
        return sorted(gone.values())


def spoken(memory: Shelf, name: str) -> bool:
    """The user's memory names it: it was spoken of with the user."""
    said = re.compile(rf"\b{re.escape(name.lower())}\b")
    return any(t.name.lower() == name.lower() for t in memory.things()) or \
        any(said.search(e.lower()) for e in memory.journal.entries.values())


class Mistake(ValueError):
    """A tool used the wrong way: says what came, what is expected, and a call that works."""

    def __init__(self, came: str, expected: str, example: str):
        super().__init__(f"{came}. Expected {expected}. For example: {example}")


class Talking:
    """An object that, asked for what it doesn't have, says what it does have."""

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        own = sorted(m for m in dir(type(self)) if not m.startswith("_"))
        listed = " It is a list: len(x), x[0], for i in x work." if isinstance(self, list) else ""
        raise AttributeError(f"{type(self).__name__} has no {name!r}.{listed} What it has: {', '.join(own)}.")


# --- the objects a program works with; every name says what it does ---------------------------


class Item(Talking):
    """A thing the memory or a collection holds."""

    def __init__(self, thing: Thing, tools: "Tools"):
        self._thing, self._tools = thing, tools
        self.name, self.kind = thing.name, thing.kind

    def value_of(self, attribute: str):
        """item.value_of("price_eur") -> a number, a word, True/False, or None if not known
        Several numbers seen (prices from several shops) compare as a condition means:
        price <= 400 if some offer is, 200 <= price <= 500 if some offer is in the range."""
        return _plain(self._thing.get(attribute))

    def date_of(self, attribute: str = "date"):
        """item.date_of("date") -> a datetime.date, or None if not known — its weekday is
        .weekday() (Monday 0 … Sunday 6), and it compares with date.fromisoformat(today)"""
        return _date(self.value_of(attribute))

    def all_values(self) -> dict:
        """item.all_values() -> {attribute: value} for everything known about it"""
        return self._thing.values()

    def linked_items(self, as_word: str | None = None) -> list:
        """item.linked_items("works_at") -> [(Item, link word, the sentence)] for what it is linked to"""
        return [(Item(t, self._tools), w, text) for t, w, text in self._thing.links(as_word)]

    def texts_about(self) -> list[str]:
        """item.texts_about() -> [sentences, with their sources] — everything said about it"""
        return self._thing.about()

    def dates(self) -> dict:
        """item.dates() -> {"created", "changed", "told", "used", "lives_until"} as "YYYY-MM-DD HH:MM:SS";
        lives_until is None for what has been with the user: the user's own memory, what was named in
        an answer, what the user's memory names"""
        dates = self._thing.dates()
        shelf = self._tools._shelf_of(self._thing)
        dates["used"] = shelf.last_use(self._thing) if shelf else dates["changed"]
        lasting = shelf is None or shelf.lasting(self._thing) or self._tools._spoken(self.name)
        dates["lives_until"] = None if lasting or not dates["used"] else \
            f"{datetime.strptime(dates['used'], '%Y-%m-%d %H:%M:%S') + TTL:%Y-%m-%d %H:%M:%S}"
        return dates

    def chance_that(self, claim: str) -> float:
        """item.chance_that("it weighs under 1.5 kg") -> 0..1, read by the decision model from its texts"""
        if not isinstance(claim, str) or not claim.strip():
            raise Mistake(f"chance_that got {claim!r}", "a claim in words", 'item.chance_that("it has a backlit keyboard")')
        decider = role("judge")
        texts = "\n".join(f"- {e}" for e in self.texts_about()[:20])
        try:
            return decider.noul(f"{self.name}. What is known:\n{texts}", f"Does this show that {claim}?",
                                true="yes, what is known shows it", false="no, or nothing known shows it")["p"]["yes"]
        except Exception:  # noqa: BLE001 - what can't be read shows nothing
            return 0.0

    # The same thing is the same item, however it was reached: `org == brightwork` compared two
    # wrappers of one thing and was never true, so no colleague was found (2026-10-27).
    def __eq__(self, other) -> bool:
        return isinstance(other, (Item, _Seen)) and self._thing.id == other._thing.id and \
            self._thing._memory is other._thing._memory

    def __hash__(self) -> int:
        return hash(self._thing.id)

    def __repr__(self) -> str:
        return f"<{self.name} ({self.kind or 'thing'}): {self.all_values()}>"


class Items(Talking, list):
    """A list of items."""

    def __init__(self, items, tools: "Tools"):
        super().__init__(items)
        self._tools = tools

    def named(self, name: str):
        """items.named("Olga") -> the Item with that name, or None"""
        return next((i for i in self if i.name.lower() == str(name).lower()), None)

    def rank_by(self, conditions: dict, must_hold=(), keep_top: int = 10) -> "Ranking":
        """items.rank_by({"affordable": lambda i: i.value_of("price_eur") <= 800}, must_hold=["affordable"], keep_top=10) -> Ranking
        Each condition is met, not known, or not met. A condition that reads a value the item doesn't
        have is not known — never "not met". A must_hold condition has to be met AND known. An item
        missing its class's required values is left out. Filter with conditions, not beforehand: a
        plain list has no rank_by (Items(a_list) makes one)."""
        return self._tools._rank(self, conditions, must_hold, keep_top)

    def __repr__(self) -> str:
        return f"<{len(self)} items: " + ", ".join(i.name for i in self[:8]) + (" …>" if len(self) > 8 else ">")


class Ranked(Talking):
    """One item in a ranking, with how it stood on each condition."""

    def __init__(self, item: Item, conditions: dict, read: dict, score: float):
        self.item, self.conditions, self._read, self.score = item, conditions, read, score

    def report(self) -> str:
        """ranked.report() -> each condition met / not known / NOT met, with the value and the words it stands on"""
        t, lines = self.item._thing, []
        for name, held in self.conditions.items():
            mark = "met" if held else "not known" if held is None else "NOT met"
            seen = []
            for attr in dict.fromkeys(self._read.get(name, ())):
                said = t._memory.value(t, attr)["said"]
                day = _date(t.get(attr)) if isinstance(t.get(attr), str) else None
                seen.append(f"{attr} = {t.get(attr)!r}" + (f" ({day:%A})" if day else "") + (f' — {said[0][1].split(" — ", 1)[-1][:160]}' if said else ""))
            lines.append(f"- {name}: {mark}" + (f" ({'; '.join(seen)})" if seen else ""))
        return f"{self.item.name}\n" + "\n".join(lines)

    def __repr__(self) -> str:
        marks = " ".join(f"{k}={'yes' if v else '?' if v is None else 'no'}" for k, v in self.conditions.items())
        return f"<{self.item.name}: {marks}>"


class Ranking(Talking, list):
    """Ranked items, best first."""

    def __init__(self, ranked, tools: "Tools", closest=(), ruled_out=None):
        super().__init__(ranked)
        self._tools = tools
        # When nothing passed: the items that came nearest — most must_hold conditions met.
        self.closest = list(closest)
        # How many were left out by each condition that must hold: not met, or not known.
        self.ruled_out = dict(ruled_out or {})

    def best(self) -> Ranked | None:
        """ranking.best() -> the first Ranked, or None if nothing passed"""
        return self[0] if self else None

    def brief(self, among: int = 5) -> str:
        """ranking.brief() -> the first few for the agent to decide from: each condition met / not known / NOT met with the words it stands on, what is said about each, and what was ruled out by which limit"""
        # The world gives facts and the agent decides: a choice made here, by a model of the
        # world's, was a decision taken from the agent and the user (2026-10-27).
        if not self:
            return _nothing_passed(self.closest, self.ruled_out)
        listed = "\n\n".join(f"{n}. {r.report()}\nWhat is said about it:\n" +
                              "\n".join(f"  - {e}" for e in r.item.texts_about()[:8])
                              for n, r in enumerate(self[:among], 1))
        more = f" The first {among} of {len(self)} that passed, by how many conditions they meet." if len(self) > among else ""
        return (f"Candidates, in order of the conditions they meet — for you and the user to decide from.{more}"
                f"\n\n{listed}{_ruled_out(self.ruled_out)}")

    def __repr__(self) -> str:
        if not self:
            return f"<ranking of 0; closest: " + "; ".join(repr(r)[1:-1] for r in self.closest[:5]) + ">"
        return f"<ranking of {len(self)}: " + "; ".join(repr(r)[1:-1] for r in self[:5]) + (" …>" if len(self) > 5 else ">")


def _nothing_passed(closest, ruled_out=None) -> str:
    if not closest:
        return "Nothing known passed the conditions, and nothing came close." + _ruled_out(ruled_out)
    return ("Nothing passed every condition that must hold. What came closest, with each condition as judged:\n\n"
            + "\n\n".join(r.report() for r in closest) + _ruled_out(ruled_out))


def _ruled_out(ruled_out) -> str:
    if not ruled_out:
        return ""
    return "\n\nRuled out: " + "; ".join(f"{n} where {name} was not met or not known" for name, n in ruled_out.items())


class Collection(Talking):
    """Items gathered for this task, kept apart from the user's memory."""

    def __init__(self, shelf: Shelf, tools: "Tools"):
        self._shelf, self._tools, self.of_class = shelf, tools, shelf.of

    def add_from_texts(self, texts, fields: dict | None = None) -> dict:
        """collection.add_from_texts(pages, fields={"weight_kg": "weight in kg"}) -> {"items", "values", "links", "dropped"}
        Reads texts or pages and adds the items they name, their values (under exactly the names in
        fields, plus the class's) and links. Only what a text states is kept, each value checked
        against the text's own words. About 20 s per 8 pages."""
        return self._tools._parse(texts, self._shelf, fields)

    def describe(self) -> str:
        """collection.describe() -> its kinds, value names and link words, with counts"""
        return _describe(self._shelf.structure)

    def all_items(self, kind: str | None = None) -> Items:
        """collection.all_items() -> Items found in the last three days, by this task or one before"""
        # What earlier tasks found stays for its lifetime, to answer about, but a choice is made
        # from what was found in the last three days (FRESH): a price or a date seen days ago may be gone.
        found = [t for t in self._shelf.things(kind) if (self._shelf.structure.dates(t)["changed"] or "") >= self._tools.started]
        self._shelf.use(found)  # read by a task: a use, which its TTL counts from
        return Items([Item(t, self._tools) for t in found], self._tools)

    def __repr__(self) -> str:
        return f"<collection of {self.of_class or 'things'}: {len(self._shelf.things())} items>"


class UserMemory(Talking):
    """The user's own memory: their life, the people in it, their wishes and limits."""

    def __init__(self, tools: "Tools"):
        self._tools = tools

    def answer_question(self, question: str) -> str:
        """user_memory.answer_question("what limits a purchase for the flat?") -> an answer in words"""
        if not isinstance(question, str) or not question.strip():
            raise Mistake(f"answer_question got {question!r}", "a question in words",
                          'user_memory.answer_question("who are the user\'s colleagues?")')
        return self._tools._recall(question) if self._tools._recall else \
            "\n".join(self._tools.memory.journal.entries.values())

    def all_items(self, kind: str | None = None) -> Items:
        """user_memory.all_items("person") -> Items: the people, places, things the memory holds"""
        return Items([Item(t, self._tools) for t in self._tools._known().things("world", kind)], self._tools)

    def the_user(self) -> "Item":
        """user_memory.the_user() -> the user, as an Item: their links and values"""
        known = self._tools._known()
        return Item(next(t for t in known.things("world") if t.name == "the user"), self._tools)

    def describe(self) -> str:
        """user_memory.describe() -> what the memory holds: its kinds, value names and link words, with counts"""
        return _describe(self._tools._known()) + (
            "\nA link word starting former_ is a link that has ended (\"used to be\", \"left\"); the others hold."
            if self._tools._image_used else "")

    def add_from_texts(self, texts, fields: dict | None = None) -> dict:
        """user_memory.add_from_texts("Olga moved to Porto.") -> counts: keeps what the text states about the user's life"""
        return self._tools._parse(texts, self._tools.memory, fields)


class Web(Talking):
    """The outside."""

    def __init__(self, tools: "Tools"):
        self._tools = tools

    def search_pages(self, query: str, how_many: int = 5) -> list:
        """web.search_pages("student laptop test 2026 Germany", how_many=5) -> [{"url", "title", "text"}]
        A query names kinds of thing, the market and the date — never the user's people or places
        (refused)."""
        return self._tools._search(query, how_many)


class Tools:
    """What a program sees is the namespace: user_memory, web, new_collection, reply_to_agent,
    today. The docstrings of what it reaches are what the program's writer is told."""

    def __init__(self, memory: Shelf, root: Path, recall_with=None, engine: str = ENGINE, log=print):
        self.memory, self.root, self.engine, self.log = memory, root, engine, log
        self.shelves: dict[str, Shelf] = {}
        self._view, self._image_used = None, False
        # What a task chooses from: found within FRESH. Only what this run found hid eleven dated
        # concerts found four minutes before (2026-10-27); what is days old may be gone.
        self.started = f"{datetime.now() - FRESH:%Y-%m-%d %H:%M:%S}"
        self._closest: list = []
        self._ruled_out: dict = {}
        # Collections live with the memory and outlast the task; what is past its time is
        # removed by the cleaner (memory/cleaner.py), before a task starts.
        self.collections = memory.path / "collections"
        self._recall, self.answered = recall_with, None
        # Pages already read onto a shelf with the same fields: a program fixed and run again
        # gathers the same pages, and reading them is the slow part.
        self._read: set = set()

    # --- what the program calls ---------------------------------------------------------------

    def new_collection(self, name: str, of_class: str | None = None) -> Collection:
        """new_collection("laptops", of_class="product") -> Collection
        of_class names a class (see Classes): its fields are gathered on every add, and an item
        without its required values is never ranked."""
        if not isinstance(name, str) or not name.strip():
            raise Mistake(f"new_collection got name {name!r}", "a name in words", 'new_collection("laptops", of_class="product")')
        if of_class is not None and of_class not in CLASSES:
            raise Mistake(f"new_collection got of_class={of_class!r}", f"one of {sorted(CLASSES)}, or None",
                          f'new_collection("{name}", of_class="{next(iter(CLASSES))}")')
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        of_class = of_class or next((c for c in CLASSES if c in {w.rstrip("s") for w in slug.split("-")}), None)
        if slug not in self.shelves:
            self.shelves[slug] = Shelf(self.collections / slug, of=of_class)
            self.shelves[slug].structure.since = self.started
        return Collection(self.shelves[slug], self)

    def reply_to_agent(self, text) -> None:
        """reply_to_agent(text) — the answer the agent gets; the program ends with it. A Ranked is given as its report()."""
        self.answered = text.report() if isinstance(text, Ranked) else str(text)
        # A reply that says nothing passed gets what came closest, whatever the program wrote.
        if self._closest and not any(r.item.name in self.answered for r in self._closest):
            self.answered += "\n\n" + _nothing_passed(self._closest, self._ruled_out)
        # What the answer names has been with the user: it has no TTL from now on.
        for shelf in self.shelves.values():
            named = [t for t in shelf.things() if len(t.name) > 3 and t.name in self.answered]
            if named:
                shelf.use(named, lasting=f"named in an answer, {datetime.now():%Y-%m-%d}")

    def namespace(self) -> dict:
        return {"user_memory": UserMemory(self), "web": Web(self), "new_collection": self.new_collection,
                "reply_to_agent": self.reply_to_agent, "today": datetime.now().date().isoformat(),
                "Items": lambda items: Items(items, self)}

    def manual(self) -> str:
        """The object model as the program's writer is told it: names and docstrings only."""
        out = ["  " + _doc(self.new_collection), "  " + _doc(self.reply_to_agent), "  today -> 'YYYY-MM-DD'",
               "  Items(a_list) -> Items: a plain list of items made into Items again"]
        for cls, var in ((UserMemory, "user_memory"), (Web, "web"), (Collection, "Collection"), (Items, "Items"),
                         (Item, "Item"), (Ranking, "Ranking"), (Ranked, "Ranked")):
            out.append(f"\n  {var}: {cls.__doc__.strip()}")
            out += ["    " + _doc(getattr(cls, m)) for m in vars(cls) if not m.startswith("_") and callable(getattr(cls, m))]
            if cls is Item:
                out.append("    item.name, item.kind")
            if cls is Ranked:
                out.append("    ranked.item, ranked.conditions {name: True/None/False}, ranked.score")
        return "\n".join(out)

    # --- inside -------------------------------------------------------------------------------

    def _known(self) -> Structure:
        """What the program reads of the user's memory: the image the world read from the journal
        when there is one — things, values and links, typed, each standing on its entry — else
        what the host wrote. Read once per task."""
        if self._view is None:
            self._view, self._image_used = self.memory.structure, False
            try:
                from memory.world import image_of
                world = self.memory.path / "world"
                image = image_of(world) if (world / "image.json").exists() else None
            except Exception as wrong:  # noqa: BLE001 - without the image, the host's structure
                self.log(f"the image could not be read ({wrong!r}); reading what the host wrote")
                image = None
            if image and image.get("things"):
                self._view, self._image_used = _from_image(image, lambda: self.memory.journal.entries,
                                                           self.memory.structure), True
        return self._view

    def _spoken(self, name: str) -> bool:
        return spoken(self.memory, name)

    def _private(self) -> set[str]:
        # A place is the market a query names — "concerts in Belgrade" — and tells the web nothing
        # of the user; people and organisations would. Refusing every name refused the city an
        # events task can't search without (2026-10-27).
        return {t.name.lower() for t in self.memory.things() if len(t.name) > 2 and t.name.lower() != "the user"
                and not {w.rstrip("s") for w in re.findall(r"[a-z]+", (t.kind or "").lower())} & PLACES}

    def _search(self, query: str, pages: int) -> list:
        if not isinstance(query, str) or not query.strip():
            raise Mistake(f"search_pages got {query!r}", "a query in words", 'web.search_pages("Laptop Test 2026")')
        leaked = [n for n in self._private() if re.search(rf"\b{re.escape(n)}\b", query.lower())]
        if leaked:
            raise Mistake(f"the query {query!r} names {', '.join(sorted(leaked))} from the user's memory",
                          "kinds of thing, the market and the date only", 'web.search_pages("light student laptop under 800 euro")')
        if not shutil.which("ait-search"):
            return tavily(query, pages)
        run = subprocess.run(["ait-search", "--engine", self.engine, "search", query, "--limit", str(max(pages, 10)),
                              "--fetch", str(pages), "--tag", "terraweaver"], capture_output=True, text=True, timeout=600)
        try:
            found = json.loads(run.stdout).get("results", [])
        except ValueError:
            return []
        out = []
        for r in found:
            # The engine finds; a page's text may be fetched by another (Tavily finds, keenable reads).
            bodies = [b for b in r.get("bodies") or [] if b.get("path")]
            body = next((b for b in bodies if b.get("source") == self.engine), bodies[0] if bodies else None)
            if body:
                out.append({"url": r["url"], "title": r.get("title"), "published": r.get("published"),
                            "text": Path(body["path"]).read_text(errors="replace")})
        return out[:pages]

    def _parse(self, texts, into: Shelf, fields: dict | None) -> dict:
        if fields is not None and not (isinstance(fields, dict) and all(isinstance(k, str) and isinstance(v, str)
                                                                         for k, v in fields.items())):
            raise Mistake(f"add_from_texts got fields={fields!r}", "a dict of value name -> what it means, in words",
                          'fields={"weight_kg": "weight in kg", "battery_hours": "battery life in hours"}')
        items = texts if isinstance(texts, list) else [texts]
        if not all(isinstance(t, str) or (isinstance(t, dict) and "text" in t) for t in items):
            raise Mistake(f"add_from_texts got {sorted({type(t).__name__ for t in items})}",
                          "a text, a list of texts, or pages from web.search_pages(...)",
                          'collection.add_from_texts(web.search_pages("…"))')
        items = [t if isinstance(t, dict) else {"text": t, "url": ""} for t in items]
        if into.of:
            fields = {**CLASSES[into.of]["fields"], **(fields or {})}
        done = lambda i: (id(into), i.get("url") or hash(i["text"]), json.dumps(fields, sort_keys=True))
        items = [i for i in items if done(i) not in self._read]
        with ThreadPoolExecutor(8) as pool:
            read = list(pool.map(lambda i: parsing.read(i["text"], "", i.get("url", ""), fields), items))
        self._read |= {done(i) for i in items}
        total = {"items": 0, "values": 0, "links": 0, "dropped": 0}
        for item, got in zip(items, read):
            kept = parsing.keep(into.structure, into.session, got, item.get("url", ""))
            total["items"] += kept["things"]
            total["values"] += kept["values"]
            total["links"] += kept["links"]
            total["dropped"] += len(kept["dropped"])
        return total

    def _shelf_of(self, thing: Thing) -> Shelf | None:
        return next((s for s in self.shelves.values() if thing._memory is s.structure), None)

    def _class_of(self, thing: Thing) -> dict:
        for shelf in self.shelves.values():
            if thing._memory is shelf.structure and shelf.of:
                return CLASSES[shelf.of]
        return {}

    def _rank(self, items, conditions, must_hold, keep_top) -> Ranking:
        if not isinstance(conditions, dict) or not all(callable(c) for c in conditions.values()):
            raise Mistake(f"rank_by got conditions={conditions!r}", "a dict of name -> lambda item: ...",
                          '{"light": lambda i: i.value_of("weight_kg") <= 1.5}')
        must_hold = (must_hold,) if isinstance(must_hold, str) else tuple(must_hold)
        if set(must_hold) - set(conditions):
            raise Mistake(f"rank_by got must_hold={list(must_hold)}, naming {sorted(set(must_hold) - set(conditions))} "
                          f"that are not among the conditions {sorted(conditions)}", "names of conditions",
                          f"must_hold={[next(iter(conditions))] if conditions else []}")
        out, near, ruled_out = [], [], {}
        for item in items:
            t = item._thing
            values = t.values()
            if any(values.get(f) is None for f in self._class_of(t).get("required", ())):
                continue
            held, read = {}, {}
            for name, test in conditions.items():
                seen = _Seen(item, values)
                try:
                    held[name] = bool(test(seen))
                except _Unknown:
                    held[name] = None
                except Exception:  # noqa: BLE001 - a value of another shape is not known either
                    held[name] = None
                read[name] = seen.read
            score = sum(1 if v else 0.5 if v is None else 0 for v in held.values()) + 0.01 * len(t.about())
            if any(held.get(h) is not True for h in must_hold):
                for h in must_hold:
                    if held.get(h) is not True:
                        ruled_out[h] = ruled_out.get(h, 0) + 1
                near.append((sum(held.get(h) is True for h in must_hold), Ranked(item, held, read, score)))
                continue
            out.append(Ranked(item, held, read, score))
        # Nothing passed: the nearest go with the empty ranking, and into the reply. A program left
        # to say so itself answered "no candlelight concert avoids Sunday evenings", with eleven
        # of them, dated, in its collection (2026-10-27).
        closest = [r for _, r in sorted(near, key=lambda nr: (-nr[0], -nr[1].score))[:3]] if not out else []
        self._closest, self._ruled_out = closest, ruled_out
        return Ranking(sorted(out, key=lambda r: -r.score)[:keep_top], self, closest, ruled_out)


def _from_image(image: dict, entries, host: Structure | None = None) -> Structure:
    """The image as a store the object model reads: a thing per image thing (the user named "the
    user"), its values, and its links — those the world read from the journal over its own typed
    ones, which held "now" where they had ended (2026-10-27) — an ended link's word as former_<word>.
    Nothing is written: it lives for the task."""
    view = Structure(Path("/nonexistent/image.jsonl"), lambda text, source: 0, entries)
    at = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    records = view.records
    add = lambda r: records.append({**r, "session": "world", "n": len(records) + 1, "at": at})
    hosts = host._things() if host else {}
    for group, t in image.get("things", {}).items():
        # A class the world has not read yet is no kind; the host's word for it is.
        kind = _plain_word(t["class"]) if t.get("class") not in (None, "Thing") else (hosts.get(group) or {}).get("kind")
        add({"thing": group, "name": "the user" if t.get("user") else t.get("name") or group, "kind": kind})
    for group, r in hosts.items():  # what the host named and the world has not mirrored yet
        if group not in image.get("things", {}):
            add({"thing": group, "name": r["name"], "kind": r.get("kind")})
    for group, attrs in image.get("values", {}).items():
        for attr, said in attrs.items():
            for v in said:
                add({"entry": v["entry"], "about": [group], "as": attr, "value": v["value"], "when": None})
    links = image.get("links", [])
    read = [l for l in links if l.get("source") == "read"] or links
    for l in read:
        word = _plain_word(l["type"])
        if l.get("holds") == "ended" and not word.startswith("former"):
            word = f"former_{word}"
        if l.get("entry") is not None and l["subject"] in image["things"] and l["object"] in image["things"]:
            add({"entry": l["entry"], "about": [l["subject"], l["object"]], "as": word, "when": None})
    return view


def _plain_word(word: str) -> str:
    """ManagerOf, manager of, manager_of -> manager_of."""
    return "_".join(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(word)).lower().split())


def _describe(structure: Structure) -> str:
    """Kinds, value names and link words in a store, most used first: what a program can read."""
    kinds, values, links, example = {}, {}, {}, {}
    held = structure._entries()
    for r in structure.records:
        if "thing" in r:
            kinds[r.get("kind") or "?"] = kinds.get(r.get("kind") or "?", 0) + 1
        elif "value" in r:
            values[r["as"]] = values.get(r["as"], 0) + 1
        elif r.get("entry") and len(r.get("about") or ()) > 1:
            word = r.get("as") or "?"
            links[word] = links.get(word, 0) + 1
            example.setdefault(word, held.get(r["entry"], ""))
    show = lambda d: ", ".join(f"{k} ({n})" for k, n in sorted(d.items(), key=lambda kv: -kv[1])[:40]) or "none"
    # A link word alone says little — works_at, started_at, moved_to may all be "works there":
    # each comes with a sentence it was said in, so the program reads them by what they mean.
    said = "\n".join(f"  {w} ({n}): {example[w].split(': ', 1)[-1][:140]}"
                     for w, n in sorted(links.items(), key=lambda kv: -kv[1])[:40]) or "  none"
    return (f"kinds: {show(kinds)}\nvalues (item.value_of): {show(values)}\n"
            f"links (item.linked_items(word)), each with a sentence it was said in:\n{said}")


def _doc(method) -> str:
    first, _, rest = (method.__doc__ or "").strip().partition("\n")
    return first.strip() + "".join(f"\n      {l.strip()}" for l in rest.splitlines() if l.strip())


class _Unknown(Exception):
    pass


class Seen:
    """Numbers seen for one value — prices from several shops — compared as a condition means:
    `price <= 400` holds if some offer is at most 400, `climbs >= 20` if some source says 20 or
    more, `200 <= price <= 500` if some offer is in the range. The program writes the condition
    as it would for one number."""

    def __init__(self, lowest, highest):
        self.lowest, self.highest = lowest, highest

    def __le__(self, other): return self.lowest <= other
    def __lt__(self, other): return self.lowest < other
    def __ge__(self, other): return self.highest >= other
    def __gt__(self, other): return self.highest > other
    def __eq__(self, other): return self.lowest <= other <= self.highest
    def __float__(self): return float(self.lowest)
    def __repr__(self): return f"{self.lowest}–{self.highest}"


def _date(value):
    """A value read as a date: "2027-01-30" or "2027-01-30T19:00" -> date(2027, 1, 30); else None.
    A weekday worked out by a model came out wrong ("January 30, 2027 is a Thursday — but wait")."""
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str(value or ""))
    try:
        return date.fromisoformat(m.group(1)) if m else None
    except ValueError:
        return None


def _plain(value):
    return Seen(*value) if isinstance(value, list) and len(value) == 2 else value


class _Seen:
    """An item as a condition sees it: reading a value it doesn't have stops the condition, and
    which values it read are kept, so a report can show what each condition stood on."""

    def __init__(self, item: Item, values: dict):
        self._item, self._values, self.read = item, values, []
        self.name, self.kind = item.name, item.kind

    def value_of(self, attribute: str):
        attribute = "_".join(str(attribute).lower().split())
        self.read.append(attribute)
        value = self._values.get(attribute)
        if value is None:
            raise _Unknown(attribute)
        return _plain(value)

    def date_of(self, attribute: str = "date"):
        day = _date(self.value_of(attribute))
        if day is None:
            raise _Unknown(attribute)
        return day

    def __getattr__(self, name):
        return getattr(self._item, name)
