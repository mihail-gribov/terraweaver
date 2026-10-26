"""What the world solves a task with: a few tools that know about correctness and nothing about
any particular task.

The world's model writes a program from these (proto/solve.py) and decides which it needs — a
question about the user's colleagues is answered from the memory's links and never searches; a
purchase gathers candidates from the web first. What makes an answer right lives in the tools, so
no program can skip it:

- `parse` keeps a value or a link only on the text's own words, checked by code and by the
  decision model (proto/parse.py);
- `select` never reads "not known" as "no";
- `search` refuses a query that names anyone the user's memory holds;
- everything kept has its sentence and its source.

The user's memory is `memory`; a collection gathered for a task is a shelf — the same kind of
store under the memory's directory (collections/), so a thousand products don't crowd the user's
life. A collection outlives the task, so what was found can still be asked about, but a task
chooses only from what it found itself — what reuses is the program, not stale prices. Not for
good either: an item lives LIFETIME from the last time it was found, unless the user's memory names
it — what was spoken of with the user has no lifetime. An item past its time is removed, its texts
with it.
"""
import asyncio
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from proto import parse as parsing
from proto.models import role
from proto.model import Structure, Thing

ENGINE = "tavily"
# What holds for every thing of a class, whatever the task: its fields, and which must be known.
CLASSES = json.loads((Path(__file__).with_name("classes.json")).read_text())
# How long an item found for a task and never spoken of with the user is kept, from the last time
# it was found: prices and stock a week old are no longer a shop's word.
LIFETIME = timedelta(days=7)


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

    def expire(self, spoken, now: datetime | None = None) -> list[str]:
        """Remove every thing last found more than LIFETIME ago that `spoken(name)` doesn't hold
        for, with the records and texts about it. Returns the names removed."""
        cut = f"{(now or datetime.now()) - LIFETIME:%Y-%m-%d %H:%M:%S}"
        gone = {t.id: t.name for t in self.things()
                if t.name != "the user" and (self.structure.dates(t)["changed"] or "") < cut and not spoken(t.name)}
        if not gone:
            return []
        records = self.structure.records
        out = [r for r in records if r.get("thing") in gone or set(r.get("about") or ()) & set(gone)]
        stay = [r for r in records if r not in out]
        self.journal.drop({r["entry"] for r in out if "entry" in r} - {r["entry"] for r in stay if "entry" in r})
        self.structure.records = stay
        self.structure.path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in stay))
        return sorted(gone.values())


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
        """item.dates() -> {"created", "changed", "told", "lives_until"} as "YYYY-MM-DD HH:MM:SS";
        lives_until is None for what has no lifetime: the user's own memory, and what was spoken of with the user"""
        dates = self._thing.dates()
        lasting = self._thing._memory is self._tools.memory.structure or self._tools._spoken(self.name)
        dates["lives_until"] = None if lasting or not dates["changed"] else \
            f"{datetime.strptime(dates['changed'], '%Y-%m-%d %H:%M:%S') + LIFETIME:%Y-%m-%d %H:%M:%S}"
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
                seen.append(f"{attr} = {t.get(attr)!r}" + (f' — {said[0][1].split(" — ", 1)[-1][:160]}' if said else ""))
            lines.append(f"- {name}: {mark}" + (f" ({'; '.join(seen)})" if seen else ""))
        return f"{self.item.name}\n" + "\n".join(lines)

    def __repr__(self) -> str:
        marks = " ".join(f"{k}={'yes' if v else '?' if v is None else 'no'}" for k, v in self.conditions.items())
        return f"<{self.item.name}: {marks}>"


class Ranking(Talking, list):
    """Ranked items, best first."""

    def __init__(self, ranked, tools: "Tools"):
        super().__init__(ranked)
        self._tools = tools

    def best(self) -> Ranked | None:
        """ranking.best() -> the first Ranked, or None if nothing passed"""
        return self[0] if self else None

    def choose_one_for(self, task: str, among: int = 5) -> str:
        """ranking.choose_one_for("a light laptop for a student") -> the choice among the first few, why, and its report"""
        if not self:
            return "Nothing passed the conditions, so there is nothing to choose from."
        writer = role("chooser")
        top = self[:among]
        listed = "\n\n".join(f"{r.report()}\nWhat is said about it:\n" +
                             "\n".join(f"- {e}" for e in r.item.texts_about()[:12]) for r in top)
        said = writer.say(
            "You choose for the user among the candidates given, and only among them.",
            f"Task: {task}\n\nCandidates, each with its conditions already judged — met, not known, "
            f"NOT met. Those marks are final: do not judge a condition again or call a NOT met one "
            f"acceptable.\n\n{listed}\n\nFirst line: \"Choice: <the candidate's name exactly as "
            f"written>\". Then a few lines why, quoting the marks, and what to check before acting. "
            f"Name no product, shop or model that is not among the candidates.",
            room=3000, thinking=False)
        first, _, why = said.strip().partition("\n")
        named = first.split(":", 1)[-1].strip().strip("*\" ")
        # The choice must be one of the candidates: a model named from the writer's own knowledge
        # is no candidate at all (seen 2026-10-26: "consider the Eufy G30").
        chosen = next((r for r in top if r.item.name.lower() == named.lower()), None)
        if chosen is None:
            chosen, why = top[0], (f"(The model named {named!r}, which is not among the candidates; "
                                   f"the first by the conditions is given instead.)\n" + why)
        return f"Choice: {chosen.item.name}\n{why.strip()}\n\n{chosen.report()}"

    def __repr__(self) -> str:
        return f"<ranking of {len(self)}: " + "; ".join(repr(r)[1:-1] for r in self[:5]) + (" …>" if len(self) > 5 else ">")


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
        """collection.all_items() -> Items found for this task"""
        # What earlier tasks found stays for its lifetime, to answer about, but a choice is made
        # from what this task found: a price or stock seen days ago may be gone.
        return Items([Item(t, self._tools) for t in self._shelf.things(kind)
                      if (self._shelf.structure.dates(t)["changed"] or "") >= self._tools.started], self._tools)

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
        return Items([Item(t, self._tools) for t in self._tools.memory.things(kind)], self._tools)

    def describe(self) -> str:
        """user_memory.describe() -> what the memory holds: its kinds, value names and link words, with counts"""
        return _describe(self._tools.memory.structure)

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
        self.started = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        # Collections live with the memory and outlast the task; what is past its time goes now.
        self.collections = memory.path / "collections"
        for path in sorted(self.collections.glob("*/")) if self.collections.exists() else []:
            gone = Shelf(path).expire(self._spoken)
            if gone:
                self.log(f"collection {path.name}: {len(gone)} items past their lifetime, removed")
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

    def _spoken(self, name: str) -> bool:
        """The user's memory names it: it was spoken of with the user."""
        said = re.compile(rf"\b{re.escape(name.lower())}\b")
        return any(t.name.lower() == name.lower() for t in self.memory.things()) or \
            any(said.search(e.lower()) for e in self.memory.journal.entries.values())

    def _private(self) -> set[str]:
        return {t.name.lower() for t in self.memory.things() if len(t.name) > 2 and t.name.lower() != "the user"}

    def _search(self, query: str, pages: int) -> list:
        if not isinstance(query, str) or not query.strip():
            raise Mistake(f"search_pages got {query!r}", "a query in words", 'web.search_pages("Laptop Test 2026")')
        leaked = [n for n in self._private() if re.search(rf"\b{re.escape(n)}\b", query.lower())]
        if leaked:
            raise Mistake(f"the query {query!r} names {', '.join(sorted(leaked))} from the user's memory",
                          "kinds of thing, the market and the date only", 'web.search_pages("light student laptop under 800 euro")')
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
        out = []
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
            if any(held.get(h) is not True for h in must_hold):
                continue
            score = sum(1 if v else 0.5 if v is None else 0 for v in held.values()) + 0.01 * len(t.about())
            out.append(Ranked(item, held, read, score))
        return Ranking(sorted(out, key=lambda r: -r.score)[:keep_top], self)


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

    def __getattr__(self, name):
        return getattr(self._item, name)
