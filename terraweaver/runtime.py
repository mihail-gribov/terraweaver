"""The world as a service: sessions, code execution and the run log.

Hosts reach the world through two operations — `describe()` tells them what exists, `run()`
executes their Python against it. Everything a run does is recorded in the `runs` table, so
what a host wrote, what it saw and what it changed can be inspected afterwards. That log is
also the raw material for procedural memory (docs/procedural-memory.md).

Each run is one transaction: if the code raises, nothing it wrote stays in the world.
"""
import ast
import contextlib
import io
import json
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from terraweaver import initiative, matching, onboarding, ontology, sandbox
from terraweaver.impls import IMPLS
from terraweaver.describe import (COMMON_MEMBERS, HOST_GUIDE, catalogue, describe_for_prompt, short,
                                  describe_methods)
from terraweaver import timeutil
from terraweaver.ontology import Entity, build_classes, load_specs
from terraweaver.resolution import NeedsResolution
from terraweaver.session import Session
from terraweaver.store import Store
from terraweaver.variables import VariableError, WorldVariables
from terraweaver.world import NotInWorld, World

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
MAX_OUTPUT = 20_000
# A session idle this long is taken to be a finished task: the next call starts a fresh one.
IDLE_RESET_SECONDS = 20 * 60

RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    session TEXT NOT NULL,
    code TEXT NOT NULL,
    ok INTEGER NOT NULL,
    output TEXT,
    error TEXT,
    access TEXT,
    written TEXT,
    duration_ms INTEGER
);
"""



# Names that mean the same two entities in every session, and that host code may read but never
# rebind: losing "who you are" and "whose world this is" halfway through a task is not something
# a host should be able to do to itself.
ALWAYS = frozenset({"user", "agent", "owner", "me"})

# The session the world uses for code it wrote itself, kept apart from every host's so that
# what it binds cannot be mistaken for what a host is holding.
THE_WORLDS_OWN = "the world's own reading"


class WorldView:
    """What host code sees as `world`: the operations, not the machinery.

    The real World holds the store, and the store holds the database connection — handing it
    over would let host code run raw SQL past every check.
    """

    def __init__(self, world: World, variables: WorldVariables, session_key: str, session=None,
                 runtime=None):
        self._world = world
        self._variables = variables
        self._session_key = session_key
        self._session = session
        self._runtime = runtime

    def _touched(self) -> set:
        return set(getattr(self._session, "touched", set()))

    @property
    def owner(self):
        """The person this world belongs to."""
        return self._world.owner

    @property
    def me(self):
        """The assistant persona."""
        return self._world.me

    @property
    def pending(self):
        """The NeedsResolution that the last refused write left behind, if any."""
        return self._world.pending

    def all(self, cls=None, limit: int | None = World.DEFAULT_LIMIT, *,
            any_time: bool = False, history: bool = False):
        """Entities of a class, or of every class when none is named.

        `world.all()` used to be a TypeError about a missing argument, which says what the
        signature wants and not what the caller does. Asking a world for everything in it is a
        reasonable thing to ask.
        """
        if cls is None:
            got = []
            for name, klass in self._world.classes.items():
                if klass._spec.get("relation") or name == "Task":
                    continue
                got += self._world.all(name, limit=None, history=history or any_time)
            return got[:limit] if limit else got
        return self._world.all(cls, limit=limit, history=history or any_time)

    def find(self, cls, *, any_time: bool = False, history: bool = False, **attrs):
        return self._world.find(cls, history=history or any_time, **attrs)

    def get(self, cls, **attrs):
        return self._world.get(cls, **attrs)

    def identify(self, cls, **attrs) -> list:
        return self._world.identify(cls, **attrs)

    def new(self, cls, *, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        return self._world.new(cls, starts=starts, until=until, ttl=ttl, permanent=permanent, **attrs)

    def ensure(self, cls, *, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        return self._world.ensure(cls, starts=starts, until=until, ttl=ttl, permanent=permanent, **attrs)

    def settle(self, needs: NeedsResolution, choice=None, *, new: bool = False):
        return self._world.settle(needs, choice, new=new)

    def questions(self, limit: int = 20, here: bool = False):
        """Open questions, the ones worth asking first — ordered by how often the entity comes up.

        here=True narrows it to what this task actually worked with: call it when the task is
        done and the user is still there, and offer them in one go ("two things I'd like to
        check with you"). Never mid-task.
        """
        touched = self._touched() if here else None
        return self._world.questions.open_(limit, here=touched)

    def undecided(self, limit: int = 50) -> list:
        """The doubts this task raised that nobody has decided anything about yet.

        These are what `finish_task` refuses to close over, and they hang on the links and the
        entities the task made — not all on the one entity you started from, which is why
        reaching them through any single entity misses most of them. Settle each:

            for q in world.undecided():
                print(q.line())
            q.answer("...")           you know
            q.for_the_user("...")     you cannot; it goes to the user and stops blocking
            q.drop("...")             it was never a real doubt
        """
        return self._world.questions.unresolved(here=self._touched(), limit=limit)

    def classes_here(self, like: str | None = None, limit: int = 0) -> str:
        """Every class this world has now, with how much of it there is.

        The opening description is what the world contained when the task began; this is what
        it contains now, including whatever was defined five minutes ago. The primer told hosts
        to call `classes()` for it, twice, and no such name was ever bound — so the one call
        that would have shown a host its own new types raised NameError instead.
        """
        return self._runtime.classes_here(like, limit) if self._runtime else ""

    def where(self, cls=None, **conditions) -> list:
        """Attributes, links, tags and meaning in one ask; without a class, things of any kind."""
        return self._world.where(cls, **conditions)

    def texts(self, words: str | None = None, **kw) -> list[dict]:
        """Everything said in words about anything, searched by the words themselves."""
        return self._world.texts(words, **kw)

    def happening(self, since=None, until=None, limit: int = 200) -> list[tuple]:
        """What is on between two moments: (when, the thing, what it is), repeats counted out."""
        return self._world.happening(since, until, limit)

    def repeats(self) -> list[str]:
        """Everything in this world that happens again and again, in words."""
        return self._world.repeats()

    def wanted(self, least: int = 2) -> list[dict]:
        """The types this world keeps needing and hasn't got, counted from its own free links.

        Each one is a link written again and again with no type, always between the same two
        kinds of thing — a word that has become a habit. Define it and take them in."""
        return self._world.wanted(least)

    def verify(self, least: int = 3) -> list[dict]:
        """What the world notices about its own links: one running against its type, a type
        narrower than its facts, two types that are one idea. Nothing is refused — each finding
        says what was seen and what would settle it."""
        return self._world.verify(least)

    def relate(self, subject, obj, how: str, **attrs):
        """Relate two things — by the fact in words, or by a type this world already has.

            world.relate(paris, france, "Paris is the capital of France")   the fact, in words
            world.relate(paris, france, "capital_of")                       a type it has

        The same verb an entity carries (`paris.relate(france, ...)`), in the other place: the
        world joins two things, an entity attaches another to itself. One verb, two positions,
        and what it takes says which form it is.

        **Named for what is being said, not for the saying.** There are three things a host can
        tell this world and it does something different with each: what joins two things (here),
        what one thing is (`thing.describe`), and what a thing's value is (`thing.attr = ...`).
        Getting them mixed up is not a tidiness problem, it is the failure that was measured all
        day: fourteen capitals went into the *entity's* description — "the capital of Japan" on
        Tokyo, a fact about two things written about one, where nothing can supersede or find
        it — and encyclopaedia entries about cities went onto the *link* — "the capital and
        largest city of Germany, located in central Europe" on a CapitalOf. Each was a legal
        move and each put the fact where it cannot be used.

        So the host says which of the three it means, and the world can hold it to that: a
        sentence said as a link that mentions only one of the two things is probably about the
        thing, and the other way round.

        The type is not asked for. `a.relate(b, kind)` needs it chosen before the fact can be
        said, and a host that must choose before it has anything to choose with chooses badly —
        measured: two ideas under one word, three links written backwards, `over_time` answered
        by guess. Here the words are recorded at once, the two things are joined at once, and
        what the joining *is* gets read at the close of the task, where nothing waits on it.
        """
        from terraweaver import ontology as ont, sentences

        if not ont._is_a_sentence(how):
            return self._world.relate(subject, obj, how, **attrs)
        task = getattr(self._session, "task_id", None) if self._session else None
        sentences.say(self._world, subject, obj, how, task)
        ontology.note_world_call("world_writes")
        return f"said: {how.strip()}"

    def take_in(self, kind, idea: str | None = None) -> list:
        """Move the free links that were waiting for a type into the one just defined."""
        return self._world.take_in(kind, idea)

    def tags(self) -> dict:
        """Every tag in this world: how often it is used, on what, and how it has been written."""
        return self._world.tags()

    def tagged(self, tag: str, at=None, any_time: bool = False) -> list:
        """Everything carrying this tag now — or at a moment, or ever."""
        return self._world.tagged(tag, at, any_time)

    def untag(self, tag: str, among: list | None = None) -> int:
        """Take a tag off everything, or off the ones given — the other half of tagging."""
        return self._world.untag(tag, among)

    def tagged_all(self, *tags_wanted: str) -> list:
        """Everything carrying every one of these tags: one tag gathers, two pick out."""
        return self._world.tagged_all(*tags_wanted)

    def merge_tags(self, into: str, *others: str) -> int:
        """Make several tags one: everything carrying any of them ends up carrying the first."""
        return self._world.merge_tags(into, *others)

    def like(self, text: str, limit: int = 5, kind: str | None = None) -> list:
        """What in this world reads like that — by meaning, not by the words used."""
        return self._world.like(text, limit, kind)

    def rebuild(self) -> int:
        """Build every entity again from what was said. Safe, and states nothing."""
        return len(self._world.rebuild())

    def described(self, since=None, until=None, contains: str | None = None, limit: int = 50,
                 include_expired: bool = False, any_time: bool = False):
        """Dated remarks across every entity, newest first; include_expired=True adds history."""
        return self._world.comments.search(since=since, until=until, contains=contains, limit=limit,
                                           include_expired=include_expired or any_time)

    @property
    def now(self):
        """What time the world thinks it is. Set it and everything recorded is recorded then."""
        return timeutil.now()

    @now.setter
    def now(self, moment) -> None:
        was = timeutil.shifted()
        moved = timeutil.set_now(moment)
        if moved is None:
            ontology.note_hint("the world's now is the clock again.")
        else:
            ontology.note_hint(
                f"the world's now is {timeutil.show(moved)}"
                + (f" (it was {timeutil.show(was)})" if was else "")
                + ". Everything recorded from here is recorded as happening then, until it is "
                  "moved again or set to None."
            )

    def pin(self, name: str, value, description: str, keep: bool | None = None) -> None:
        """Keep a named value at hand: an entity (by id), entities, or plain data.

        Say which of the two it is, because the world cannot tell and will not guess:

            keep=False  for this task — it goes when the task does. Most things.
            keep=True   past this task, until you unpin it — where the person lives, the
                        project they are in the middle of, the calendar they keep.

        There is no default. A name that outlives the conversation that made it is how a world
        fills with things nobody meant to keep, and a name that quietly disappears is a
        NameError for something you pinned on purpose. Both are cheap to avoid and expensive to
        find, and you are the one who knows which this is.
        """
        if keep is None:
            raise TypeError(
                f"world.pin({name!r}, ...) — say how long: keep=False for this task, keep=True "
                f"for something that should still be here next week. I have no way to tell "
                f"which, and picking one for you is how the wrong one gets picked quietly."
            )
        self._variables.pin(name, value, description, set_by=self._session_key, keep=keep)
        print(f"[pinned] {name}" + (" — kept past this task" if keep else " — for this task"))

    def unpin(self, *names: str) -> None:
        """Remove world variables: world.unpin("anna", "stats")."""
        self._variables.unpin(*names)
        print(f"[unpinned] {', '.join(names)}")

    def __getattr__(self, name):
        """Calls a mode added (world.extras), and a useful refusal when there is no such call."""
        if name.startswith("_"):
            raise AttributeError(name)
        extra = self._world.extras.get(name)
        if extra is not None:
            return extra
        from terraweaver import ontology

        known = [n for n in dir(type(self)) if not n.startswith("_")] + list(self._world.extras)
        near = ontology.did_you_mean(name, known)
        raise AttributeError(
            f"the world has no {name!r}" + (f" — did you mean {near!r}? " if near else ". ")
            + f"It can: {', '.join(sorted(known))}.")

    def __repr__(self):
        core = ("all, find, where, get, new, ensure, settle, described, questions, happening, "
                "repeats, texts, tags, tagged, tagged_all, merge_tags, untag, like, rebuild, "
                "pin, unpin, owner, me, pending")
        extra = ", ".join(sorted(self._world.extras))
        return f"<world: {core}" + (f" | this world also: {extra}>" if extra else ">")


class WorldRuntime:
    def __init__(self, db_path: str, fixture: str | None = None, rebuild: bool = False, *,
                 specs: dict | None = None, selves: bool = True,
                 ontology_dir: Path | None = None, home: Path | None = None):
        self.db_path = db_path
        self.fixture = fixture
        # Where the two parties are described (selves.py). Next to the world by default, so a
        # world carried on a stick carries its configuration with it.
        self.home = Path(home) if home is not None else (
            Path(db_path).parent if db_path != ":memory:" else Path.cwd())
        # specs={} is a world with no vocabulary at all: whoever uses it defines its classes as
        # it goes (ontology.define_class). Everything else — statements, periods, history,
        # identity, tags, rebuild — works the same, because none of it knows what a Person is.
        self.specs = load_specs(ontology_dir or ONTOLOGY_DIR) if specs is None else dict(specs)
        self.classes = build_classes(self.specs, IMPLS)
        self.store = Store(db_path)
        self.store.conn.executescript(RUNS_SCHEMA)
        # Asked before the world opens: opening it puts the two parties in, and a world that
        # holds only those two is still an empty one waiting for its fixture.
        empty = self.store.conn.execute("SELECT COUNT(*) FROM instances").fetchone()[0] == 0
        self.world = World(self.store, self.classes, self.specs, selves=selves)
        # Methods the world wrote for itself hang on the classes like any other (procedures.py).
        self.world.procedures.bind(self.classes)
        onboarding.onboard(self.world, self.home)
        reserved = set(self.classes) | set(sandbox.MODULES) | {
            "world", "owner", "me", "NeedsResolution", "NotInWorld", "print", "report", "run_skill"}
        self.variables = WorldVariables(self.store, self.classes, reserved | set(sandbox.BUILTINS))
        if fixture and (rebuild or empty):
            self.reset()
            onboarding.onboard(self.world, self.home)  # the fixture's pair reads its files too
        self.sessions: dict[str, Session] = {}
        # Keys whose session was dropped for idleness; the next result says so once.
        self.idle_reset: set[str] = set()

    # --- sessions ---

    def session(self, key: str) -> Session:
        existing = self.sessions.get(key)
        if existing is not None and time.time() - existing.last_used > IDLE_RESET_SECONDS:
            del self.sessions[key]
            self.idle_reset.add(key)
        if key not in self.sessions:
            session = Session(self.classes, world=self.world)
            namespace = session.namespace
            namespace["world"] = WorldView(self.world, self.variables, key, session, self)
            namespace["NeedsResolution"] = NeedsResolution
            namespace["NotInWorld"] = NotInWorld
            namespace["__builtins__"] = sandbox.BUILTINS
            namespace.update(sandbox.MODULES)
            session.preset |= set(sandbox.MODULES) | {"__builtins__", "NotInWorld"}
            self.sessions[key] = session
        session = self.sessions[key]
        self._bind_classes(session)
        session.last_used = time.time()
        return session

    def _bind_classes(self, session) -> None:
        """Every class this world has, under its class name and under the word it is said with.

        Called when a session opens and after every run. Only after a run at first, which meant
        a session that opened onto a world full of grown types could not name one until it had
        written something — and the world was meanwhile asking it to amend a type by a name
        that raised NameError.
        """
        for name, cls in self.world.classes.items():
            if name not in session.namespace:
                session.namespace[name] = cls
                session.preset.add(name)
            kind = ((getattr(cls, "_spec", {}) or {}).get("relation") or {}).get("kind")
            if kind and kind not in session.namespace:
                session.namespace[kind] = cls
                session.preset.add(kind)

    def start_task(self, key: str, stated: str, mode: str) -> str:
        """Open a task: say what this piece of work is before doing it.

        The world has no other way to see where work starts and stops. Everything that hangs on
        that boundary — which names are still yours, what was left unanswered, what a fact was
        recorded for — hangs on this call.
        """
        stated = (stated or "").strip()
        if len(stated) < 12:
            raise ValueError(
                "say what the task is, as a sentence — 'record what the user said about their "
                "job history', not 'facts'. It is what the world holds the work against when "
                "you close it, and what the next task reads if you leave something open.")
        if mode not in ("recording", "answering"):
            raise ValueError("mode is 'recording' (putting something in) or 'answering' "
                             "(finding something out). A task is one or the other.")
        left = self.finish_task(key, closing="abandoned") if key in self.sessions else ""
        task = self.classes["Task"].new(stated=stated, mode=mode, runs=0)
        session = self.session(key)
        session.task_id = task.id
        lines = [f"Task {task.id} open: {stated} ({mode})."]
        if left:
            lines.append("The task before it was dropped. " + left)
        lines.append("Settle who this is about first: Person.identify(full_name=\"...\") "
                     "for each one the user named hands back who could be meant. Read them, "
                     "pick the one, hold it in a variable. A name nobody here has is recorded "
                     "as you ask, so that is one call, not two. Do it before anything else.")
        if mode == "recording":
            lines.append("Then write it against those variables. Writes don't ask about "
                         "identity: they take what they are given. Read what the world says "
                         "back, answer that, then finish_task. A fact recorded with the world's "
                         "reply unanswered is a guess filed under the user's name.")
        else:
            lines.append("Then read and report. Don't write facts: a question is not evidence.")
        return "\n".join(lines)

    def _links_against_their_type(self, session) -> list[str]:
        """Links this task made whose ends are the reverse of how the type otherwise runs.

        `relations.verify` has worked this out since it was written and nothing ever called it,
        so the world noticed and told nobody. Read by eye, one type in a three-batch world held
        `Le Guin -> A Wizard of Earthsea` beside `Starship Troopers -> Heinlein`; the world had
        found that one and a second I had missed.

        Only what this task touched, and only this finding of the several `verify` makes: a
        link running backwards is a wrong fact and cheap to turn round, while "these two types
        are one idea" has an innocent reading and is reported rather than held against.
        """
        from terraweaver import relations

        try:
            found = relations.verify(self.world, least=2)
        except Exception:  # noqa: BLE001 - a check must never be what stops a task closing
            return []
        against = []
        for one in found:
            if one.get("about") != "against the run of its type":
                continue
            for link_id in one.get("links", []):
                try:
                    link = self.store.load(link_id, self.classes)
                except Exception:  # noqa: BLE001
                    continue
                if link is None:
                    continue
                against.append((link.display_name(), one.get("said", ""), one.get("tied")))
                # Kept as a question on the link, not only reported here. A link written
                # backwards in the third batch is not in the seventh batch's session, so the
                # old test — only what this task touched — never saw it again; and inside its
                # own batch the type had too few links for a run to exist yet. So the world
                # worked it out, said nothing, and the wrong fact stayed. Six of them sat in a
                # hundred-fact world while every task closed clean. A question outlives the run
                # and is asked once: `raise_` will not repeat one, and will not re-ask one
                # somebody has answered.
                self.world.questions.raise_(
                    link, "against the run of its type", one.get("said", ""),
                    options=["it is backwards — record it the other way and retract this one",
                             "it is right; this type runs both ways"])
        return against

    def _words_taken_on_the_fly(self) -> list[tuple]:
        """Attributes the world took on the host's word, still waiting to be said what they are."""
        grow = (self.world.extras or {}).get("attribute")
        made = getattr(grow, "__self__", None)
        if made is None or not hasattr(made, "unsaid"):
            return []
        try:
            return made.unsaid()
        except Exception:  # noqa: BLE001 - a check must never be what stops a task closing
            return []

    def _facts_hiding_in_prose(self, session) -> list[tuple]:
        """Descriptions this task wrote that name another thing in the world and join nothing.

        "the capital of Japan", written on Tokyo, is not a description of Tokyo — it is a fact
        about Tokyo *and Japan*, and its place is the link between them. Written as prose it
        passes every check the world has: the thing is described, the task closes, and the fact
        is somewhere nothing can supersede, count or ask about it. Fourteen capitals went this
        way in one 455-fact run, each while no type for them existed yet — which is exactly when
        prose is the easiest thing to reach for, and exactly when reaching for it is worst,
        because nothing ever goes back over a description when the type finally arrives.

        The test is deliberately narrow: the text must name another entity *this world already
        holds*, and the two must have no link between them in either direction. "the city
        Thomas Kyd was born in" names Thomas Kyd and there is a link, so it is what it looks
        like — an account of why the thing is here. Same sentence with no link is a fact nobody
        recorded.
        """
        named: list[tuple] = []
        others = {}
        for cls in self.world.classes.values():
            if cls._spec.get("relation"):
                continue
            for other in self.world.all(cls, limit=None):
                said = (getattr(other, "name", None) or getattr(other, "full_name", None)
                        or getattr(other, "title", None))
                if said and len(str(said)) > 3:      # "USA" is a name; "the" is a coincidence
                    others[matching.normalize(str(said))] = other
        for entity_id in sorted(session.touched):
            try:
                entity = self.store.load(entity_id, self.classes)
            except Exception:  # noqa: BLE001 - a check must never be what stops a task closing
                continue
            if entity is None or type(entity)._spec.get("relation"):
                continue
            joined = set()
            try:
                for link in entity.relations(any_time=True):
                    joined |= {getattr(link.subject, "id", None), getattr(link.object, "id", None)}
            except Exception:  # noqa: BLE001
                pass
            for text in (getattr(entity, "descriptions", None) or []):
                words = matching.normalize(str(getattr(text, "text", text)))
                for name, other in others.items():
                    if other.id == entity.id or other.id in joined or name not in words:
                        continue
                    named.append((entity, other, str(getattr(text, "text", text))))
                    break
        return named

    def _undescribed(self, session) -> list[str]:
        """What this task put in the world and never said a word about.

        A name is a handle, not a description. Twenty facts went in correctly and left three
        universities filed as a place, an abstraction and an agent, and three football positions
        as objects and an abstraction — nothing in the world could have caught it, because
        nothing in the world said what any of them was. A line in the agent's own words is the
        one piece of evidence the world does not write itself, and so the only one it can
        honestly check its own structure against later.
        """
        if not session.touched:
            return []
        placed = ",".join("?" * len(session.touched))
        described = set()
        for (table,) in self.store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'facts_%'"):
            for subject, in self.store.conn.execute(
                    f"SELECT subject FROM '{table}' WHERE slot = 'descriptions' "
                    f"AND subject IN ({placed}) AND value NOT IN ('[]', 'null', '\"\"')",
                    tuple(session.touched)):
                described.add(subject)
        without = []
        for one in sorted(session.touched - described):
            try:
                entity = self.store.load(one, self.classes)
            except Exception:  # noqa: BLE001 - gone, or of a class this world no longer has
                continue
            if entity is None or not self._needs_describing(entity):
                continue
            without.append(entity.display_name())
        return without

    @staticmethod
    def _needs_describing(entity) -> bool:
        """Whether the class already accounts for the thing, or a line is owed.

        Asked of everything, the check produced the one thing this world forbids. Eleven of
        twenty-two descriptions came back as the fact written out in prose — "Amy Winehouse:
        died in the city of Camden Town", with the DiedIn link sitting right beside it. It was
        the honest answer to an unanswerable question: of a Person called Amy Winehouse, "what
        it is" is encyclopaedia the user never said, and "why it is here" is the fact.

        A Thing is different, because `Thing` says nothing. Camden Town, wide receiver and the
        BBC are all Things, and only the line tells them apart — which is exactly where the
        world found three organisations filed under three natures. So the line is owed by the
        catch-all class and by links, and by nothing that already has a class of its own.
        """
        from terraweaver.relations import Relation

        return isinstance(entity, Relation) or type(entity).__name__ == "Thing"

    def _anything_said(self, session) -> bool:
        """Whether this task put anything into the world beyond entities and their names.

        A name is how a thing is referred to, not something known about it. The record is the
        place to ask: a statement whose slot is not the class's own naming attribute is a fact.
        """
        if not session.touched:
            return False
        # `descriptions` is among these now, and that is the point: the world asks for one on
        # every Thing and every link, so every entity has one and "did this task say anything"
        # answered yes for a world holding nothing but names and the lines describing them. A
        # recorder created forty-three entities, defined four relation types, made **no links
        # at all**, and closed reporting "all ten facts are successfully recorded".
        marks = {"name", "full_name", "title", "aliases", "created_at", "accessed_at",
                 "valid_from", "valid_until", "from_is", "until_is", "tags", "descriptions"}
        placed = ",".join("?" * len(session.touched))
        for table in self.store.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'facts_%'"):
            rows = self.store.conn.execute(
                f"SELECT slot FROM '{table[0]}' WHERE subject IN ({placed})",
                tuple(session.touched)).fetchall()
            if any(slot not in marks for (slot,) in rows):
                return True
        return False

    def unresolved(self, key: str) -> list:
        """The doubts this task raised and nobody has decided anything about."""
        session = self.sessions.get(key)
        if session is None or not session.touched:
            return []
        return self.world.questions.unresolved(here=set(session.touched))

    def finish_task(self, key: str, closing: str | None = None, abandon: str = "") -> str:
        """Close the task — but only once nothing it touched is still undecided.

        How it closed is computed, not declared. A batch of facts raises a doubt per fact, and
        an agent working through the batch will pass some of them: not out of carelessness, but
        because each one arrives while it is busy with the next. So the check is here, where it
        cannot be walked past, and it is made every time rather than once at the end — the
        run-by-run count says how many are standing, and this refuses while any remain.

        Three ways past it, and all three are somebody's decision on the record: answer it,
        hand it to the user with `for_the_user` because you genuinely cannot know, or abandon
        the task and say why.
        """
        session = self.sessions.get(key)
        if session is None or session.task_id is None:
            # None, not "": nothing was closed because nothing was open, and a caller that
            # cannot tell those apart reports a clean finish over work nobody checked.
            return None
        task = self.store.load(session.task_id, self.classes)
        # Read what was said before weighing what is open, not after. The readings are what
        # settle half of it — a sentence is a bare link until it is read, a bare name is a
        # doubt until something is said about it — so checking first meant a task that said six
        # facts in words could never close, and therefore was never read, and therefore never
        # closed. Each reading is marked, so a second attempt pays for nothing.
        typed = self._read_what_was_said()
        placed, still = self._read_what_things_are()
        standing = self.unresolved(key)
        if standing and not abandon and closing is None:
            lines = "\n".join(f"    {q.line()}" for q in standing[:8])
            more = f"\n    … and {len(standing) - 8} more" if len(standing) > 8 else ""
            return (
                f"Not closed: {len(standing)} thing(s) this task raised are still nobody's "
                f"decision. They came up as you worked and each one is about a fact you "
                f"recorded, so they are the task, not leftovers from it:\n"
                f"{lines}{more}\n\n"
                f"Reach them all with `world.undecided()` — they hang on the links "
                f"this task made, not on one entity — and settle each:\n"
                f"    q.answer(\"she meant the London one\")        — you know\n"
                f"    q.for_the_user(\"two people share this name\") — you cannot know; it goes\n"
                f"                                                   to the user and stops\n"
                f"                                                   blocking\n"
                f"    q.drop(\"the link was a typo, now retracted\") — it was never a real doubt\n"
                f"Then finish_task again. If the task cannot be done at all, "
                f"finish_task(abandon=\"why\")."
            )
        if abandon:
            closing = "abandoned"
        elif task is not None and getattr(task, "mode", None) == "recording":
            # A recording task that recorded nothing is the failure that reports itself as a
            # success. One left a world holding eight bare names — no links, no attributes, no
            # remarks — and said "all ten facts have been recorded, the world kept everything".
            # The world knows what it was given, so it is the one thing it can say for certain.
            # Once per task, not once per type. Marking only what was shown meant a host that
            # recorded more between close attempts was asked again about the new ones, and a
            # batch that kept going kept being sent back: seven refusals to close in one, and
            # it ran out of turns having recorded nothing that scored.
            unread = session.readings if not session.read_back else {}
            if unread:
                shown = "\n".join(f"    {line}" for line in unread.values())
                session.read_back |= set(unread) | {"*"}
                return (
                    f"Not closed yet — read these back first. Each is the first link of a type "
                    f"this task made, as the world reads it:\n{shown}\n\n"
                    f"`a.relate(b, kind)` reads \"a is b's kind\", so the holder of the role "
                    f"comes first: the capital, the author, the chairperson. If any of them "
                    f"says the opposite of the fact, record it the other way round and retract "
                    f"the one that went in backwards. Then finish_task again — I will not ask "
                    f"a second time."
                )
            crossed = self._links_against_their_type(session)
            if crossed:
                shown = "\n".join(f"    {name}" for name, _, _ in crossed)
                why = crossed[0][1]
                return (
                    f"Not closed: {why}\n{shown}\n\n"
                    f"A link written from the wrong end is a different fact, not an untidy one: "
                    f"a.relate(b, kind) reads \"a is b's kind\", so the author is the subject "
                    f"of author_of and the book is the object. Record it the way the sentence "
                    f"reads and retract the one that went in backwards — or say it from the far "
                    f"end with the reverse name, which puts it round for you: "
                    f"book.relate(person, \"author_of_of\")."
                )
            unsaid = self._words_taken_on_the_fly()
            if unsaid:
                shown = "\n".join(
                    f"    world.attribute({cls}, {attr!r}, \"<what it is>\", "
                    f"type=\"{kind}\", changes=True)"
                    for cls, attr, kind in unsaid[:8])
                more = f"\n    … and {len(unsaid) - 8} more" if len(unsaid) > 8 else ""
                return (
                    f"Not closed: {len(unsaid)} attribute(s) you wrote to were taken on your "
                    f"word and nobody has said what they mean. The values are recorded and "
                    f"stay recorded; what is missing is the two things no value can tell me.\n"
                    f"{shown}{more}\n\n"
                    f"**What it is** — one sentence. It is what the next lookup searches, so a "
                    f"word without one cannot be found by anybody who did not invent it, and "
                    f"the world ends up with two words for one idea.\n"
                    f"**The type** — I guessed it from the first value. A phone typed as str "
                    f"stops matching \"+7 (900) 000-00-01\" against \"+79000000001\".\n"
                    f"**changes=** — True if a later telling replaces the value, False if they "
                    f"accumulate. Nothing in a value says which, and getting it wrong is how a "
                    f"correction never reaches anybody."
                )
            prose = self._facts_hiding_in_prose(session)
            if prose:
                shown = "\n".join(
                    f"    {_name_of(one)}: \"{text}\"   — names {_name_of(other)}, "
                    f"nothing joins them"
                    for one, other, text in prose[:8])
                more = f"\n    … and {len(prose) - 8} more" if len(prose) > 8 else ""
                first, other, _ = prose[0]
                return (
                    f"Not closed: {len(prose)} description(s) are facts about two things, "
                    f"written about one:\n{shown}{more}\n\n"
                    f"A sentence that names something else in this world is a link, and a link "
                    f"is the only place the world can do anything with it — supersede it when "
                    f"you are told otherwise, count it, answer a question with it. In a "
                    f"description it is text: nothing contradicts it and nothing finds it.\n"
                    f"Say it as the fact it is, with both things in hand:\n"
                    f"    a.relate(b, \"<the fact, in the words the user used>\")\n"
                    f"Nothing else is needed: which two things is yours to say, and only "
                    f"yours — the word for the link is found here, afterwards.\n"
                    f"Keep the description if it says why the thing is here; the fact goes in "
                    f"the link either way. If the sentence really is only about "
                    f"{_name_of(first)}, say it without naming {_name_of(other)}."
                )
            bare = self._undescribed(session)
            if bare and self._anything_said(session):
                shown = "\n".join(f"    {one}" for one in bare[:10])
                more = f"\n    … and {len(bare) - 10} more" if len(bare) > 10 else ""
                return (
                    f"Not closed: {len(bare)} thing(s) this task put in the world have a name "
                    f"and nothing else said about them:\n{shown}{more}\n\n"
                    f"Say what each one is here, in one line: "
                    f"`camden.describe(\"the London borough Amy Winehouse died in\")` — what "
                    f"it is in this world and why it turned up, not what you happen to know "
                    f"about it. \"the capital city of the United States\" is an encyclopaedia "
                    f"entry the user never said; \"the city Pedro Pierluisi worked in\" is the "
                    f"reason it is here.\n"
                    f"This line is the only account of the thing the world did not write "
                    f"itself, so it is the only thing it can check its own structure against "
                    f"later: three universities filed under three different natures is "
                    f"invisible to a world that knows nothing about any of them but a name."
                )
            if not self._anything_said(session):
                return (
                    "Not closed: this is a recording task and nothing about anything was "
                    "recorded. There are entities, and lines describing them, and no links "
                    "between them and nothing else said — a name and an account of it are not "
                    "a fact about anything. Either record them, or "
                    "finish_task(abandon=\"why\") if they could not be recorded, but do not "
                    "report work that is not in the world."
                )
        left = self.world.questions.open_(limit=5, here=set(session.touched)) if session.touched else []
        if task is not None:
            with ontology.trusted_writes():
                task.runs = session.runs
                touched = [self.store.load(i, self.classes) for i in sorted(session.touched)]
                task.touched = [e for e in touched if e is not None]
                # `closed_as` is what ends it. Giving it a valid_until as well would say the
                # task stopped being true, and a task that was done is still a task that was
                # done — it would drop out of every ordinary read, which is where anybody
                # looking for what a fact was recorded for would go.
                # "done" is not "nothing is open" — it is "nothing was left undecided". A
                # question handed to the user is not a loose end; it is the one honest outcome
                # for a doubt the agent could not settle, and calling that left_open would
                # punish the agent for saying so.
                task.closed_as = closing or ("for_the_user" if left else "done")
                if abandon:
                    task.describe(f"abandoned: {abandon.strip()}")
                self.world.save(task)
        unnamed = self._types_without_named_ends()
        turned = self._turn_the_odd_ones()
        offered = self._read_the_new_types()
        self.reset_session(key)
        if abandon:
            return f"Task abandoned: {abandon.strip()}. What it did record stays in the world."
        # Asked at the end, and the task closes either way. A type whose ends are not named
        # works; what it cannot do is be checked, and that is worth one line rather than a wall.
        asked = ""
        if typed:
            poor = typed.get("ill_typed") or []
            if poor:
                shown = "\n".join(
                    f"    «{words}» — that is {what} of {who}, not what joins two things"
                    for words, what, who in poor[:5])
                asked += (
                    f"\n\n{len(poor)} of them could not be typed as links, and stay as links "
                    f"with no type — joined, findable, and unable to supersede anything:\n"
                    f"{shown}\n"
                    f"A value belongs on the thing (thing.attribute = ...), what a thing IS "
                    f"belongs in its nature or its class. Said that way they land where they "
                    f"can be used; said this way they are kept and little else.")
            asked += (f"\n\nRead the {typed['read']} fact(s) you said in words: "
                      f"{typed['joined']} joined a relation already here, {typed['defined']} "
                      f"needed a new one"
                      + (f", {typed['astray']} had their ends given to somebody not in the fact "
                         f"and were taken in the order you wrote them" if typed["astray"] else "")
                      + (f", {typed['failed']} could not be read and are still waiting"
                         if typed["failed"] else "") + ".")
        if placed and placed.get("read"):
            asked += (f"\n\nRead what you said about {placed['read']} thing(s) that came in as "
                      f"bare names: {placed['placed']} were placed under a class"
                      + (f", {placed['defined']} of them a class made for them" if placed["defined"] else "")
                      + (f", {placed['failed']} could not be read and are still waiting"
                         if placed["failed"] else "") + ".")
        if still:
            asked += (f"\n\n{still} thing(s) here are still only a name — nothing has been said "
                      f"about them, so there was nothing to read. They keep the name and wait: "
                      f"say what they are next time you have the user in front of you.")
        if turned:
            # Said because it was changed, not because it was checked. A fact that turned round
            # while nobody was looking is one the agent can no longer account for.
            shown = "\n".join(f"    {line}" for line in turned[:8])
            asked += (f"\n\nI turned {len(turned)} link(s) round. Each was the only one of its "
                      f"type going that way against five or more going the other, which is not "
                      f"a second reading but a slip:\n{shown}\nThe record says the world did "
                      f"it and why. If any of them was right as you wrote it, turn it back — "
                      f"you have the sentence and I only have the count.")
        if offered:
            said = "\n".join(f"    {name}: {line}"
                              for name, lines in offered.items() for line in lines)
            asked += (f"\n\nRead from outside, now that the work is done — {len(offered)} "
                      f"type(s) this world holds:\n{said}\nNothing has been changed; this is "
                      f"what somebody outside the world makes of the words, and you have the "
                      f"sentences they came from.")
        if unnamed:
            shown = ", ".join(k for k, _ in unnamed[:6])
            more = f" and {len(unnamed) - 6} more" if len(unnamed) > 6 else ""
            asked = (f"\n\nOne thing to come back to when you can: {len(unnamed)} link type(s) "
                     f"here have no names for their two ends — {shown}{more}. Without them "
                     f"nothing can later tell a link written backwards from one written right, "
                     f"and a backwards link is a wrong fact, not an untidy one. Naming them is "
                     f"one argument each: world.define_relation(..., subject_is=\"…\", "
                     f"object_is=\"…\").")
        if not left:
            return (("Nothing was left open about what that task touched." + asked)
                    if task is not None else "")
        return ("Settled, and put to the user — these wait for them, not for you:\n"
                + "\n".join(f"    {q.line()}" for q in left) + asked)

    def _ask_about_bare_things(self, namespace: dict, recording, created: set,
                               mine: bool = True) -> list[str]:
        """The script has run; now the world looks at what it made and asks about the empty ones.

        A thing that came in as a bare name has nothing on it but that name — not a class worth
        the word, not a nature, nothing to find it by later. The host knows what it is: it has
        just heard about it from the user. So the world asks, in the list of questions the run
        hands back, and asks about `rome` and not about "Rome", because the host thinks in the
        variable it wrote.

        What it asks for is words, not a class — and what words, the class says itself
        (`ontology.what_to_say`). "Describe it" means different things about a person, an event
        and a link, and asking all of them the same thing gets all of them the same answer.

        A link written with nothing said about it is asked the same way and in the same breath.
        It is the same gap: a `Kin` between two people that nobody said anything about cannot be
        told from any other `Kin`, and the words are the only account of it the world did not
        write itself.
        """
        from terraweaver import ontology as ont, portraits

        try:
            # The things with nothing but a name — not the prose-facts waiting to be read.
            # `unread` holds accounts somebody has already given, which are the opposite of
            # what is being asked for here, and asking from it meant the one case this exists
            # for — a thing the world named itself and nobody has described — was never asked.
            waiting = set(portraits.still_only_a_name(self.world))
        except Exception:  # noqa: BLE001 - never what stops a run being reported
            return []
        if not waiting:
            return []
        asked = []
        for name, value in namespace.items():
            if name.startswith("_"):
                continue
            for entity, written in ((value, name),) if not isinstance(value, list) \
                    else [(v, f"{name}[{i}]") for i, v in enumerate(value)]:
                got = getattr(entity, "id", None)
                if got is None or got not in waiting:
                    continue
                waiting.discard(got)
                written = _reachable(entity, written, mine)
                why = ont.what_to_say(type(entity), self.classes)
                text = (
                    f"{written} is new here — recorded under the name you gave and nothing else. "
                    f"Tell me about it in your own words: {written}.describe(\"...\"). What sort "
                    f"of thing it is, where, when, whose — what the user told you and what you "
                    f"know yourself. I read it when the task closes and give it a class then, so "
                    f"you do not have to pick one. Describing it is the answer; nothing else to do.")
                self.world.questions.raise_(entity, "what_is_it", text, touches=["identity"])
                # Said again every run until something is said about the thing, the way a held
                # write is. `raise_` keeps one doubt per thing and answers None the second time,
                # so asking only on a new question meant a thing the world itself had named was
                # asked about in its own session and never mentioned to the agent again.
                asked.append(f'{written}.describe("...")   # {why}')
        for left in sorted(waiting):
            # Not in anybody's namespace: the world made it while reading somebody's account —
            # Italy turns up because "Rome is the capital of Italy" says Italy. The question is
            # still the agent's to answer, since it is the one who brought Italy up, so the line
            # looks the thing up by name rather than naming a variable nobody here has.
            try:
                stray = self.store.load(left, self.classes)
            except Exception:  # noqa: BLE001 - a thing that has gone is asked about by nobody
                continue
            if stray is None:
                continue
            handle = _reachable(stray, "", mine=False)
            why = ont.what_to_say(type(stray), self.classes)
            text = (f"{stray.display_name()} came up while I was reading what you told me, and "
                    f"is in the world as a bare name. Tell me about it in your own words: {why}. "
                    f"Describing it is the answer; nothing else to do.")
            self.world.questions.raise_(stray, "what_is_it", text, touches=["identity"])
            asked.append(f'{handle}.describe("...")   # {why}')
        return asked + self._ask_about_bare_links(namespace, recording, created)

    def _ask_about_bare_links(self, namespace: dict, recording, created: set) -> list[str]:
        """Links this run wrote with nothing said about them, and the line that would say it."""
        from terraweaver import ontology as ont

        bound = {getattr(v, "id", None): k for k, v in namespace.items() if not k.startswith("_")}
        asked = []
        for key, link in recording.changed.items():
            if key not in created or not hasattr(link, "subject") or not hasattr(link, "object"):
                continue
            if getattr(link, "descriptions", None) or getattr(link, "label", None):
                continue
            kind = (type(link)._spec.get("relation") or {}).get("kind")
            handle = bound.get(link.id)
            if handle is None:
                at_end = bound.get(getattr(getattr(link, "subject", None), "id", None))
                if at_end is None or not kind:
                    continue
                handle = f'{at_end}.relations("{kind}")[-1]'
            text = (f"{handle} was written with nothing said about it. Say what it is: "
                    f"{ont.what_to_say(type(link), self.classes)}. Those words are the only "
                    f"account of this link the world did not write itself.")
            if self.world.questions.raise_(link, "what_is_it", text) is not None:
                asked.append(f'{handle}.describe("...")   # '
                             f'{ont.what_to_say(type(link), self.classes)}')
        return asked

    def _read_what_things_are(self) -> tuple[dict, int]:
        """Read what was said about the things that came in as bare names. At the close.

        The twin of `_read_what_was_said`, and here for the same reason: a run is stopped after
        ten seconds and a reader takes four to twenty.
        """
        engineer = getattr(self.world, "engineer", None)
        if engineer is None:
            return {}, 0
        try:
            from terraweaver import portraits

            asked, waiting = portraits.count(self.world)
            silent = len(portraits.still_only_a_name(self.world))
            if not waiting:
                return {}, silent
            tally = portraits.read_them(self.world, engineer, run=self._the_world_writes)
            self._hand_back_what_moved(tally.pop("moved", []))
            return tally, silent
        except Exception:  # noqa: BLE001 - reading is never what stops a task closing
            return {}, 0

    def _the_world_writes(self, entity, code: str) -> dict:
        """Run code the world wrote itself, by exactly the door a host's code goes through.

        Not a second interpreter, and that is the point of asking for code at all. What the
        reader may say is what a host may say, the sandbox is the same sandbox, the statements
        are committed one at a time the same way, and every refusal the world makes of a host
        it makes of itself. A reading that can express only what a hand-written translator
        thought of is a reading that quietly drops the rest.

        `it` is the thing being filled in, bound before the code runs so the reader never has
        to name it — identity is handed over here as it is everywhere else in this world, never
        recovered from words. The writes are the world's own (`stating("world")`), which is the
        lowest standing there is and comes off in one move.
        """
        session = self.session(THE_WORLDS_OWN)
        session.namespace["it"] = entity
        with ontology.stating("world"):
            return self.run(code, THE_WORLDS_OWN)

    def _hand_back_what_moved(self, moved: list[str]) -> None:
        """A thing read under another class is a different instance; whoever holds it gets it.

        `retype` builds the thing afresh under its new class, so every variable still pointing at
        the old one points at a Thing that is no longer what the record says. Left alone the next
        line the agent writes saves that one back, and the whole reading is undone by an
        unrelated assignment, with nothing anywhere to say it happened.
        """
        if not moved:
            return
        for entity_id in moved:
            try:
                now = self.store.load(entity_id, self.classes)
            except Exception:  # noqa: BLE001 - a thing that has gone is nobody's to hand back
                continue
            if now is None:
                continue
            for session in self.sessions.values():
                for name, held in list(session.namespace.items()):
                    if getattr(held, "id", None) == entity_id and held is not now:
                        session.namespace[name] = now

    def _read_what_was_said(self) -> dict:
        """Turn the sentences this task said into links. At the close, where nothing waits.

        A run is stopped after ten seconds and a reader takes four to twenty, so this cannot
        happen where the fact is said. It does not need to: the words are in the record.
        """
        engineer = getattr(self.world, "engineer", None)
        if engineer is None:
            return {}
        try:
            from terraweaver import sentences

            said, waiting = sentences.count(self.world)
            if not waiting:
                return {}
            return sentences.read_them(self.world, engineer)
        except Exception:  # noqa: BLE001 - reading is never what stops a task closing
            return {}

    def _turn_the_odd_ones(self) -> list[str]:
        """The one correction the world makes by itself: see inspector.turn_the_odd_ones."""
        try:
            from terraweaver import inspector

            return inspector.turn_the_odd_ones(self.world)
        except Exception:  # noqa: BLE001 - a correction is never what stops a task closing
            return []

    def _read_the_new_types(self) -> dict:
        """Types nobody has read, read now — at the close, where no run is waiting on it.

        A host's run is stopped after ten seconds and a reader that thinks first takes longer,
        so this cannot happen where the type is defined. It happens here, once per type, and
        what it offers is said rather than applied.
        """
        try:
            from terraweaver import inspector

            return inspector.look_at_types(self.world)
        except Exception:  # noqa: BLE001 - reading is never what stops a task closing
            return {}

    def _types_without_named_ends(self) -> list[tuple]:
        """Link types this world grew that never said what each of their two ends is."""
        # Every type, whoever wrote it. A class is a class here, and a type whose ends are not
        # named cannot have its links checked whether it came with the world or was built in it.
        out = []
        for name, cls in sorted(self.classes.items()):
            rel = cls._spec.get("relation")
            if rel and not rel.get("roles"):
                out.append((rel.get("kind", name), name))
        return out

    def reset_session(self, key: str) -> str:
        """Drop a session's variables: the next call starts with a clean namespace.

        Returns what was left open about the entities that task worked with. A task ending is
        the one moment the world knows of when the host is free and the user is still there —
        exactly when a question can be put without interrupting anything.
        """
        session = self.sessions.pop(key, None)
        self.idle_reset.discard(key)
        # Names pinned in that session go with it. Nothing is promoted on its own: what should
        # outlive a conversation is a judgement the host makes at the time, with keep=True, not
        # something the world infers from a name having been useful once.
        self.variables.session_ended(key)
        if session is None or not session.touched:
            return ""
        left = self.world.questions.open_(limit=3, here=set(session.touched))
        if not left:
            return ""
        lines = [f"    {q.line()}" for q in left]
        return ("Left open about what that task worked with — if the user is still there, this is "
                "the moment to ask:\n" + "\n".join(lines))

    def reset(self) -> None:
        """Rebuild the world from its fixture and drop every session."""
        if not self.fixture:
            raise ValueError("this world has no fixture to rebuild from")
        from worlds import load_world

        self.store.clear_all()
        self.store.conn.execute("DELETE FROM world_variables")
        self.store.conn.commit()
        # One transaction for the whole build. Saving each entity on its own meant 366 commits
        # for 331 entities, and a commit is a write to the disk: a tenth of a second when there
        # is room and seventeen milliseconds apiece when there is not, which is six seconds of
        # fixture and, on a filesystem at ninety-nine per cent, a build that never finished.
        with self.store.transaction():
            load_world(self.fixture)(self.classes, self.store)
        self.sessions = {}

    # --- what hosts call ---

    def live_specs(self) -> dict:
        """The classes as they are now, not as they were when the world opened.

        A host that defines a class gets it at once — it is in `world.classes` and it works —
        and used to be told, every turn after, a list of what this world contains that did not
        have it in. A world that will not name what someone just built in it invites them to
        build it again under another name.
        """
        return {name: cls._spec for name, cls in self.classes.items()}

    def describe(self, key: str) -> str:
        session = self.session(key)
        return "\n".join([
            HOST_GUIDE,
            COMMON_MEMBERS,
            catalogue(self.live_specs()),
            self.variables.describe(),
            self._questions_note(),
            session.describe_for_prompt(),
        ])

    def classes_here(self, like: str | None = None, limit: int = 0) -> str:
        """Every class this world has now, with how much of it there is.

        The world's opening description carries the ones a task is most likely to touch; this is
        the whole list, including whatever the host defined five minutes ago. Without it a host
        that builds its own vocabulary is working from a list of what the world contained before
        it started — which is how the same idea gets defined twice under two names.
        """
        from terraweaver import authoring

        counts = {name: 0 for name in self.classes}
        for name, held in self.store.conn.execute(
                "SELECT class_name, COUNT(*) FROM instances GROUP BY class_name"):
            counts[name] = held
        specs = self.live_specs()
        if like:
            near = authoring.Authoring(self.world).classes_like(like, limit=limit or 5)
            wanted = [name for name, _ in near]
        else:
            wanted = sorted(counts, key=lambda n: (-counts[n], n))[:limit or len(counts)]
        lines = []
        for name in wanted:
            spec = specs.get(name, {})
            rel = spec.get("relation")
            shape = (f"  ('{rel['kind']}') {' / '.join(rel['from'])} → {' / '.join(rel['to'])}"
                     if rel else "")
            lines.append(f"  {name} ×{counts.get(name, 0)}{shape} — "
                         + short(spec.get("description", "")))
        return "\n".join([f"{len(wanted)} of {len(counts)} classes in this world, most used first."
                           if limit else f"{len(counts)} classes in this world, most used first.",
                           "Ask describe_classes([...]) for what any of them is made of.", ""]
                          + lines)

    def describe_classes(self, names: list[str]) -> str:
        """What the named classes are made of — attributes, methods, relations.

        The prompt carries the names; this carries the detail, for the few classes a task
        actually touches."""
        known = {n.lower(): n for n in self.live_specs()}
        wanted = [known[n.strip().lower()] for n in names if n.strip().lower() in known]
        missing = [n for n in names if n.strip().lower() not in known]
        if not wanted:
            return ("No such class: " + ", ".join(missing) + ".\n\n"
                    + catalogue(self.live_specs()))
        text = describe_for_prompt(self.live_specs(), only=wanted)
        text += ('\nWhat any of these does, in full and with examples: '
                 'describe_methods(["tag", "' + wanted[0] + '.' +
                 (self.live_specs()[wanted[0]].get("methods")
                  or [{"signature": "x"}])[0]["signature"].split("(")[0]
                 + '"])')
        if missing:
            text += "\nNot in this world: " + ", ".join(missing) + "."
        return text

    def describe_methods(self, names: list[str]) -> str:
        """What these methods do, in full, with examples where they help."""
        return describe_methods(self.live_specs(), names)

    def _learn_name_choice(self, session, recording, before: dict) -> list[str]:
        if not initiative.LEARNS_NAMES:
            return []
        return self._remember_name_choice(session, recording, before)

    def _remember_name_choice(self, session, recording, before: dict) -> list[str]:
        """Take the answer to "which Annie?" in the form a host actually gives it.

        The world only ever learned a name choice through `world.settle(...)`, and hosts rarely
        call it: the user says "Anna Sullivan", the host looks her up by her full name, answers,
        and moves on. Nothing was wrong with what it did — but the next conversation asked which
        Annie again, which is the one thing this world exists not to do.

        So a standing question about a name, plus this run working with exactly one of that
        question's own candidates, counts as the answer. It is a narrow signal: same session,
        same candidate list, one of them and no other. And it is said out loud rather than
        assumed in silence, so a wrong reading costs one sentence to correct.
        """
        said: list[str] = []
        told: set = set()
        fresh = [value for name, value in session.namespace.items()
                 if before.get(name) != id(value)]
        # A run that raised an ambiguity of its own is still asking, not answering — even when
        # the question it would settle was raised earlier. This is how the wrong Anna got
        # learned: the host listed the candidates for the user in a later run, and the loop
        # left the last of them bound.
        if any(isinstance(one, NeedsResolution) and one.candidates for one in fresh):
            return said
        # Only what the world itself handed over — get() settling on one, or a query returning
        # it. A binding in the namespace is not evidence: `for p in annie.similar` leaves the
        # last candidate bound, and twice now that has taught the world the wrong Anna.
        touched = {e.id for e in _entities_of(recording) if getattr(e, "id", None)}
        touched |= {e.id for e in recording.looked_up.values() if getattr(e, "id", None)}
        if not touched:
            return said
        for value in list(session.namespace.values()):
            if (not isinstance(value, NeedsResolution) or value.skill != "resolve_ambiguity"
                    or value.context.get("learned")):
                continue
            # Never in the run that raised it: the question and its answer are two moments, and
            # a candidate bound while the question is being asked is the asking, not the answer.
            if any(value is one for one in fresh):
                continue
            chosen = [c for c in value.candidates if getattr(c, "id", None) in touched]
            # More than one of them, ever, and the host was looking rather than choosing.
            seen = set(value.context.setdefault("seen", [])) | {c.id for c in chosen}
            value.context["seen"] = sorted(seen)
            if len(chosen) != 1 or len(seen) != 1:
                continue
            name = self.world.remember_choice(value, chosen[0])
            if name:
                value.context["learned"] = chosen[0].id
                line = f"{name!r} -> {chosen[0].id}"
                if line in told:      # two questions about one name is still one answer
                    continue
                told.add(line)
                # Straight onto this run's record rather than through note_assumed: by the time
                # a run's effects are gathered the recording context is closed, and a note made
                # then goes nowhere. Learning in silence is the one thing this must not do.
                said.append(
                    f"{name!r} taken as {chosen[0].display_name()} from here on, since that is "
                    f"the one you worked with — say so if it was someone else")
        return said

    def _questions_note(self) -> str:
        """A host starting a task should know there is something the user could settle."""
        open_ = self.world.questions.open_(limit=3)
        if not open_:
            return ""
        total = len(self.world.questions.open_(limit=1000))
        lines = [f"\nOpen questions about this world ({total}) — put them to the user when they're here, "
                 f"not in the middle of a task; world.questions() for all of them:"]
        lines += [f"    {q.about.display_name()}: {q.text}" for q in open_]
        return "\n".join(lines) + "\n"

    def list_variables(self, key: str) -> str:
        """World variables with their meaning, then this session's own variables with their age."""
        session = self.session(key)
        own = session.describe_for_prompt()
        parts = [self.variables.describe() or "\nNo world variables yet.\n", own or "\nThis session has no variables of its own.\n"]
        return "".join(parts).strip()

    def set_variable(self, key: str, name: str, expression: str, description: str) -> dict[str, Any]:
        """Pin a world variable to the value of a Python expression evaluated against the world.

        Goes through `run`, so it is sandboxed, atomic and logged like any other host code.
        """
        import ast

        try:
            ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            return {"ok": False, "output": "", "error": f"not a single Python expression: {exc.msg}",
                    "access": {}, "created": [], "updated": [], "found": [], "comments": [], "assumed": [],
                    "hints": [], "questions": [], "ask_now": [], "new_variables": {}, "duration_ms": 0}
        if not name.isidentifier():
            return {"ok": False, "output": "", "error": f"{name!r} can't be a variable name",
                    "access": {}, "created": [], "updated": [], "found": [], "comments": [], "assumed": [],
                    "hints": [], "questions": [], "ask_now": [], "new_variables": {}, "duration_ms": 0}
        return self.run(f"world.pin({name}, ({expression}), {description!r})", key)

    def unset_variables(self, key: str, names: str) -> dict[str, Any]:
        """Remove world variables named in one string: "anna, stats" or "anna stats"."""
        listed = [n for n in names.replace(",", " ").split() if n]
        bad = [n for n in listed if not n.isidentifier()]
        if bad:
            return {"ok": False, "output": "", "error": f"not variable names: {', '.join(bad)}",
                    "access": {}, "created": [], "updated": [], "found": [], "comments": [], "assumed": [],
                    "hints": [], "questions": [], "ask_now": [], "new_variables": {}, "duration_ms": 0}
        return self.run(f"world.unpin({', '.join(listed)})" if listed else "pass", key)

    def run(self, code: str, key: str) -> dict[str, Any]:
        session = self.session(key)
        namespace = session.namespace
        stdout = io.StringIO()
        error = None
        recording = None
        rolled_back: list[str] = []
        access: dict[str, int] = {}
        effects = {"created": [], "updated": [], "found": [], "comments": [], "assumed": [], "hints": [],
                   "questions": [], "ask_now": []}
        started = time.monotonic()
        standing: list[str] = []
        unrecorded: list[str] = []
        ran_before: dict = {}
        marked_block = ""
        # World variables are fresh in every run: entities come from the world as they are now,
        # and one pinned by another session shows up here too.
        world_vars = self.variables.load()
        for name in session.world_vars - set(world_vars):
            namespace.pop(name, None)
        namespace.update(world_vars)
        session.world_vars = set(world_vars)
        # What the namespace held before this run, so the learner below can tell what this run
        # bound from what was lying around. A loop variable outlives its loop in Python, and
        # `for p in annie.similar` left the last candidate bound — which once taught the world
        # the wrong Anna.
        before = {name: id(value) for name, value in namespace.items()}
        try:
            ontology.set_open_tokens(self.world.questions.tokens())
            skipped_imports: list[str] = []
            tree = _variables_by_name(sandbox.check(code, protected=set(world_vars) | ALWAYS,
                                                    always=ALWAYS, skipped=skipped_imports))
            # Statement by statement, each in its own transaction. All-or-nothing was the rule
            # here for a long time, and the measurements turned against it: a fifth to a quarter
            # of every pool's runs ended discarded, most of them over a typo eight lines from
            # anything that mattered. What a completed statement wrote is a whole thought — the
            # subgraph a single call touches is saved together inside it — so keeping it costs
            # no consistency, and the host is told exactly where the block stopped.
            with contextlib.redirect_stdout(stdout), ontology.track_access() as counts, \
                    ontology.record_changes() as recording, sandbox.time_limit():
                for said in _about_to_invent(self, tree):
                    ontology.note_hint(said)
                if skipped_imports:
                    ontology.note_hint(
                        f"skipped the import of {', '.join(skipped_imports)} — not available here, "
                        f"and the rest of the code ran without it. Those names are unbound, so "
                        f"anything that really needed them failed on its own line. "
                        + sandbox.AVAILABLE.split(". No files")[0] + "."
                    )
                _exec_by_statement(tree, namespace, self.store)
            with self.store.transaction():
                access = dict(counts)
                self._persist(recording, namespace)
                learned = self._learn_name_choice(session, recording, before)
                effects = _effects(recording, created={id(o) for o in self.store._tx_new_ids})
                effects["assumed"] += learned
                session.touched |= {e.id for e in _entities_of(recording)}
                # Said in this run's reply, not left for the next one: the question is about a
                # variable, and the variable is what the host has in front of it now. It is
                # raised outside the recorder — the run has already finished — so it is added
                # here by hand rather than arriving through it.
                effects["clarify"] = self._ask_about_bare_things(
                    namespace, recording, {id(o) for o in self.store._tx_new_ids},
                    mine=key != THE_WORLDS_OWN)
                effects["questions"] += _waiting_on_answers(session)
                # Only what this run raised. Repeating every doubt about every entity a run
                # happens to touch is noise: the literature's criterion is relevance to the
                # answer at hand (query-driven repair) and the task boundary, and both are
                # covered — [ask first] below, and the batch reset_session hands back.
                effects["ask_now"] = list(recording.ask_now)
                effects["questions"] = [q for q in effects["questions"]
                                        if not any(q.split(": ", 1)[-1][:50] in line for line in recording.ask_now)]
        except (Exception, sandbox.RunTimeout) as exc:  # noqa: BLE001 - reporting any failure to the host is the point
            error = _host_traceback(exc, code)
            # The statements that finished are in the world; only the one that raised was
            # rolled back, and whatever it had begun to make lost its id with it.
            rolled_back = [name for name in _discarded(recording) if name]
            # A failure before the code ever ran — a sandbox refusal, a syntax error — has no
            # recording to report from.
            if recording is not None:
                with self.store.transaction():
                    effects = _effects(recording, created={id(o) for o in self.store._tx_new_ids})
                    effects["assumed"] += self._learn_name_choice(session, recording, before)
                    # The statements that finished are in the world, so the task did touch
                    # things. Counting them only on a clean run left a close saying nothing
                    # was recorded while the world held the links the first ten lines made.
                    session.touched |= {e.id for e in _entities_of(recording) if getattr(e, "id", None)}
                # Whatever the failing statement had begun to make lost its id when that one
                # statement was undone; it is not among what was kept.
                effects["created"] = [line for line in effects["created"]
                                      if "id=None" not in line]
            self._refresh(namespace)
            standing, unrecorded = _what_survived(namespace, session)
            ran_before = _ran_before(code, exc, wrote=True)
            marked_block = _block_as_it_stands(code, exc, error)
            # A failed run is discarded, but an answer to the world's own question is not the
            # host's write and did not fail: the host really did work with one of the candidates
            # before its next line broke. Rolling that back meant the user answered "which
            # Annie?" and was asked again in the next conversation — the whole point of the
            # remembered choice, undone by an unrelated AttributeError eight lines later.
            if recording is not None:
                with self.store.transaction():
                    effects["assumed"] += self._learn_name_choice(session, recording, before)
        self._bind_classes(session)
        # A class the world made during the run has to be nameable in the next one. It was not:
        # the namespace is filled with the classes that existed when the session opened, so a
        # type the world invented from the host's own word could not be reached by any spelling
        # — and the world went on asking the host to amend a thing it had no name for. One
        # recorder spent ten runs trying `BornIn`, `born_in` and `Person.born_in` in turn, got
        # NameError twice and a silent no-op on the method the third time, and finally handed
        # every question to the user. It was right to give up; nothing it could have written
        # would have worked.
        new_names = session.sync()
        result = {
            "session_reset": key in self.idle_reset,
            "ok": error is None,
            "output": _truncate(stdout.getvalue()),
            "error": error,
            "rolled_back": rolled_back,
            "access": access,
            **effects,
            "standing": standing,
            "unrecorded": unrecorded,
            "ran_before": ran_before,
            "block": marked_block,
            "new_variables": {name: session.variables[name]["description"] for name in new_names},
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
        self.idle_reset.discard(key)
        session.runs += 1
        if recording is not None:
            session.readings.update(recording.readings)
        if (session.task_id is None and "Task" in self.classes
                and (result.get("created") or result.get("updated"))):
            # Work began without anybody saying what it was. The boundary is opened anyway,
            # because facts landing outside every task is the state this was built to end — the
            # benchmark ran 392 times that way and no check ever fired. It is opened unnamed and
            # said so: the world can hold work it was not told the name of, but it will not
            # pretend there was no work.
            with ontology.trusted_writes():
                opened = self.classes["Task"].new(
                    stated="(not said — work began before start_task)", mode="recording", runs=0)
            session.task_id = opened.id
            result["hints"] = list(result.get("hints") or []) + [
                "you began recording without start_task, so I opened a task without a name for "
                "it. Say what this work is with start_task(stated, mode) — what it is is what "
                "the world holds it against when you finish."]
        if session.task_id is not None and session.touched:
            # Counted every run, not once at the end. A doubt raised on the third fact of a
            # batch of forty is read while the host is already writing the fourth, and by the
            # fortieth nobody remembers it was raised. The running total is what makes it
            # impossible to lose track of rather than merely possible to notice.
            standing = self.world.questions.unresolved(here=set(session.touched))
            if standing:
                result["undecided"] = len(standing)
        self._log(key, code, result)
        return result

    # --- debugging ---

    def export(self) -> dict:
        """Everything the world holds, as plain JSON: for comparing against agents that keep
        the same data in files. References appear as {"id", "label"}."""
        def plain(value):
            if isinstance(value, Entity):
                return {"id": value.id, "label": value.display_name()}
            if isinstance(value, list):
                return [plain(v) for v in value]
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            return value

        out: dict[str, list] = {}
        for name, cls in self.classes.items():
            rows = []
            for entity in self.world.all(cls, limit=None, history=True):
                row = {"id": entity.id}
                for attr in cls._spec["attributes"]:
                    if "derived" not in attr:
                        row[attr["name"]] = plain(getattr(entity, attr["name"], None))
                # When a record holds is part of it. Leaving it out made an export that couldn't
                # answer "who changed jobs this year" — and made every comparison against it a
                # comparison against less than the world knows.
                for when in ("valid_from", "valid_until", "created_at"):
                    value = getattr(entity, when, None)
                    if value is not None:
                        row[when] = plain(value)
                rows.append(row)
            if rows:
                out[name] = rows
        out["comments"] = [
            {"about": plain(c.about), "text": c.text, "when": plain(c.when), "tentative": c.tentative}
            for c in self.world.comments.search(limit=10_000, include_expired=True)
        ]
        out["questions"] = [
            {"about": plain(q.about), "text": q.text, "kind": q.kind, "options": q.options,
             "raised_at": plain(q.raised_at)}
            for q in self.world.questions.open_(limit=10_000)
        ]
        return out

    def runs(self, limit: int = 20, session: str | None = None) -> list[dict]:
        query = "SELECT id, at, session, code, ok, output, error, access, written, duration_ms FROM runs"
        params: tuple = ()
        if session:
            query += " WHERE session = ?"
            params = (session,)
        rows = self.store.conn.execute(query + " ORDER BY id DESC LIMIT ?", params + (limit,)).fetchall()
        keys = ("id", "at", "session", "code", "ok", "output", "error", "access", "written", "duration_ms")
        out = []
        for row in rows:
            item = dict(zip(keys, row))
            item["ok"] = bool(item["ok"])
            item["access"] = json.loads(item["access"] or "{}")
            item["written"] = json.loads(item["written"] or "{}")
            out.append(item)
        return out

    def sessions_summary(self) -> dict[str, dict]:
        return {
            key: {"idle_seconds": int(time.time() - session.last_used), "variables": session.variables}
            for key, session in self.sessions.items()
        }

    # --- internals ---

    def _persist(self, recording, namespace: dict[str, Any]) -> None:
        """Store every entity the run changed, plus everything reachable from the namespace."""
        seen: set[int] = set()
        roots = list(recording.changed.values())
        for key, value in namespace.items():
            if key.startswith("__"):
                continue
            items = value.values() if isinstance(value, dict) else value if isinstance(value, (list, tuple, set)) else [value]
            # Only what the world already holds: an object that never got stored — left behind
            # by a run that failed and was rolled back — must not come back as a new entity.
            # And only the live object for each entity: a copy orphaned by a rollback is stale, and
            # saving it would overwrite what the world holds now.
            roots.extend(item for item in items if isinstance(item, Entity) and item.id is not None
                         and self.store.is_live(item))
        for root in roots:
            self.store.save_graph(root, seen)

    def _refresh(self, namespace: dict[str, Any]) -> None:
        """After a rollback, rebind entities the namespace holds to their stored state."""

        def fresh(value):
            if not isinstance(value, Entity) or value.id is None:
                return value
            try:
                return self.store.load(value.id, self.classes)
            except KeyError:
                return value

        for key, value in list(namespace.items()):
            if key.startswith("__"):
                continue
            if isinstance(value, Entity):
                namespace[key] = fresh(value)
            elif isinstance(value, list):
                namespace[key] = [fresh(item) for item in value]
            elif isinstance(value, dict):
                namespace[key] = {k: fresh(v) for k, v in value.items()}

    def _log(self, key: str, code: str, result: dict) -> None:
        self.store.conn.execute(
            "INSERT INTO runs (at, session, code, ok, output, error, access, written, duration_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                key,
                code,
                int(result["ok"]),
                result["output"],
                result["error"],
                json.dumps(result["access"]),
                json.dumps({k: result[k] for k in ("created", "updated", "found", "comments", "assumed", "hints",
                                                   "questions")}, ensure_ascii=False),
                result["duration_ms"],
            ),
        )
        self.store.conn.commit()


class _VariablesByName(ast.NodeTransformer):
    """`world.pin(anna, ...)` and `world.unpin(anna, stats)` name variables; they don't pass values.

    The host refers to a variable as a variable, never as a string holding its name: one level
    of abstraction, fewer tokens, less to get wrong. So bare names in those positions become the
    strings they spell — `world.unpin(zz)` for a missing `zz` then says "no world variable named
    'zz'" instead of raising NameError, and `world.pin(anna, ...)` works before `anna` exists.
    Quoted names keep working.
    """

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        func = node.func
        if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "world"):
            return node
        if func.attr == "unpin":
            node.args = [_name_as_string(arg) for arg in node.args]
        elif func.attr == "pin" and node.args:
            node.args[0] = _name_as_string(node.args[0])
        return node


def _name_as_string(arg: ast.expr) -> ast.expr:
    return ast.copy_location(ast.Constant(arg.id), arg) if isinstance(arg, ast.Name) else arg


def _variables_by_name(tree: ast.AST) -> ast.AST:
    return ast.fix_missing_locations(_VariablesByName().visit(tree))


def _name_of(entity) -> str:
    """What to call one entity in a message to the host — its own word for itself."""
    said = (getattr(entity, "name", None) or getattr(entity, "full_name", None)
            or getattr(entity, "title", None))
    return str(said) if said else entity.display_name()


# Attributes the machinery maintains; changing them isn't something the host did.
_BOOKKEEPING = {"created_at", "accessed_at"}


def _effects(recording, created: set[int]) -> dict[str, list[str]]:
    """What a run did, as the host should read it: made, changed (and what), picked out."""
    def name(entity) -> str:
        return f"{type(entity).__name__} «{entity.display_name()}»"

    def written(entity) -> str:
        """A relation is read back from both ends the one time it is written — see both_ways."""
        reading = entity.both_ways() if hasattr(entity, "both_ways") else entity.display_name()
        return f"{type(entity).__name__} «{reading}»"

    made, changed = [], []
    for key, entity in recording.changed.items():
        if key in created:
            made.append(written(entity))
            continue
        attrs = sorted(recording.attrs.get(key, set()) - _BOOKKEEPING)
        if attrs:
            changed.append(f"{name(entity)}: {', '.join(attrs)}")
    found = [name(e) for key, e in recording.found.items()
             if key not in created and not recording.attrs.get(key, set()) - _BOOKKEEPING]
    return {"created": made, "updated": changed, "found": found, "comments": list(recording.remarks),
            "assumed": list(recording.assumed), "hints": list(recording.hints),
            "questions": list(recording.questions), "ask_now": list(recording.ask_now)}


def _reachable(entity, written: str, mine: bool) -> str:
    """A handle for this thing that whoever is being asked can actually run.

    A host is asked about the variable it wrote — that is the whole reason the asking happens
    after the run. But the world writes code too, while reading somebody's account, and it
    names things the account named: Italy turns up because "Rome is the capital of Italy" says
    Italy. That question is still the agent's to answer — it is the one who brought Italy up —
    and the agent has no `italy`. So the line looks the thing up by name, which anybody can run.
    """
    if mine:
        return written
    cls = type(entity)
    key = cls._spec.get("identified_by") or matching.NAME_KEYS.get(cls.__name__) or "name"
    return f'{cls.__name__}.identify({key}="{entity.display_name()}")[0]'


def _waiting_on_answers(session) -> list[str]:
    """Questions this session is holding writes for, said again every run until they are settled.

    A held write is quiet by design — nothing is guessed — and quiet is how things get lost: a
    host that never settles the question leaves the membership it wrote unmade and never hears
    about it again. The doubt outlives the run that raised it, so the reminder does too.
    """
    out = []
    for value in session.namespace.values():
        held = isinstance(value, NeedsResolution) and value.context.get("held")
        if held:
            what = ", ".join(sorted({name for name, _, _ in held}))
            out.append(f"{value.reason} — {len(held)} thing(s) waiting on the answer ({what}). "
                       f"world.settle(<it>, <the one they meant>) applies them; new=True records "
                       f"it as new and applies them to that.")
    return out


def _entity_ids(values) -> set:
    """The entities a host is holding — in a variable, in a list, in a result it kept.

    Working with one of the candidates is not always a call the world sees: `Person.find(...)`
    hands back a result and the host keeps the one it wanted in a variable. That is the choice,
    made as plainly as `get()` makes it, and it is visible right here in the namespace.
    """
    found = set()
    for value in values:
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if isinstance(item, Entity) and getattr(item, "id", None):
                found.add(item.id)
            else:
                main = getattr(item, "matches", None)
                if isinstance(main, (list, tuple)):
                    found |= {e.id for e in main if isinstance(e, Entity) and getattr(e, "id", None)}
    return found


def _entities_of(recording) -> list:
    """Everything a run actually worked with — including both ends of a relation it wrote. A
    relation is about two people; recording one is working with them, and a doubt about either
    belongs in that run's result."""
    out = []
    for entity in list(recording.changed.values()) + list(recording.found.values()):
        if getattr(entity, "id", None) is None:
            continue
        out.append(entity)
        for end in ("subject", "object"):
            other = getattr(entity, end, None)
            if isinstance(other, Entity) and other.id is not None:
                out.append(other)
    return out


def _merge_questions(raised: list[str], standing: list[str]) -> list[str]:
    """One line per open question: what this run raised, plus what was already open about the
    entities it worked with."""
    out, seen = [], set()
    for line in list(raised) + list(standing):
        key = line.split(": ", 1)[-1][:60]
        if key not in seen:
            seen.add(key)
            out.append(line)
    return out[:5]


MAX_ECHO = 18    # lines of a failed block worth handing back; beyond that, say how many
MAX_BLOCK = 60   # past this, handing the whole block back costs more than it saves


def _block_as_it_stands(code: str, exc: BaseException, reason: str) -> str:
    """The block handed back the way it now stands: done, stopped, not run.

    Describing the cut in words still leaves the host to reconstruct its own code. This gives
    it back in the shape it was written in — the lines that are done as plain code (to read,
    not to re-run), the one that raised commented with why, and everything after it commented
    out because it never happened. What comes next is written under it, in the next message.
    """
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<run>"]
    lines = code.splitlines()
    if not frames or not lines:
        return ""
    where = frames[-1].lineno or 0
    if not 0 < where <= len(lines) or len(lines) > MAX_BLOCK:
        return ""
    why = reason.strip().splitlines()[-1][:160]
    out = ["# --- done and kept, do not send again ---"] + lines[:where - 1]
    out.append(f"# !! stopped here — {why}")
    out += [("# " + line) if line.strip() else line for line in lines[where - 1:]]
    out.append("# --- from here on, nothing ran: fix and carry on below ---")
    return "\n".join(out)


def _ran_before(code: str, exc: BaseException, wrote: bool) -> dict:
    """The part of the block that got as far as running, handed back as text.

    A host that fails on line 5 of 9 rewrites all nine from memory. It doesn't have to: the
    world has the code and knows where it stopped. What it hands back depends on one thing —
    whether those lines wrote anything. If they only looked things up, their variables are
    still bound and the work is done; if they wrote, the writing was rolled back with the rest
    and has to be sent again. Saying "it ran" without saying which of the two would be a lie
    the host pays for.
    """
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<run>"]
    if not frames or not code:
        return {}
    where = frames[-1].lineno or 0
    lines = code.splitlines()
    if not 0 < where <= len(lines):
        return {}
    before = lines[:where - 1]
    kept = [line for line in before if line.strip()]
    if not kept:
        return {}
    return {"wrote": wrote, "lines": len(kept),
            "code": "\n".join(before) if len(kept) <= MAX_ECHO else ""}


def _exec_by_statement(tree, namespace: dict, store) -> None:
    """Run the block one top-level statement at a time, each one committed on its own.

    A statement is the unit that either happened or didn't: `anna.relate(acme, ...)` writes a
    relation and both ends together, inside one call, and either all of that lands or none of
    it does. What the unit is *not* is the whole block a host happened to send — and treating
    it that way threw away everything before the line that broke.

    A statement that raises no longer ends the block either. Counted on one run: 26 blocks of
    relations failed partway, holding 109 links between them, and 65 of those links were on lines
    after the break — written by the host, never run, never retried. Keeping what came before was
    half the job; the other half is that one bad line must not cost the forty behind it.

    The first failure is the one reported, because it is the one that explains the rest. The
    others are counted and named briefly: a block where everything fails is usually one mistake
    seen forty times, and forty tracebacks bury it.
    """
    import ast

    broke: list[BaseException] = []
    ran_after = 0
    for statement in tree.body:
        piece = ast.Module(body=[statement], type_ignores=[])
        try:
            with store.transaction():
                exec(compile(piece, "<run>", "exec"), namespace)
            if broke:
                ran_after += 1
        except (Exception, sandbox.RunTimeout) as failed:  # noqa: BLE001 - carrying on is the point
            if isinstance(failed, sandbox.RunTimeout):
                raise                      # out of time is out of time; the rest would not run
            broke.append(failed)
            if len(broke) >= _GIVE_UP_AFTER:
                break
    if broke:
        if len(broke) > 1 or ran_after:
            # A statement that fails leaves its name unbound, and everything downstream that
            # was going to use it fails too — on the name, not on anything of its own. Listed
            # as peers, one broken line reads as three broken lines: across 455 facts the
            # world reported 110 NameErrors and 22 KeyErrors, and most of them were the wreck
            # of a line already reported above them.
            after = [one for one in broke[1:] if isinstance(one, (NameError, KeyError))]
            own = [one for one in broke[1:] if not isinstance(one, (NameError, KeyError))]
            others = "; ".join(f"{type(one).__name__}: {str(one)[:60]}" for one in own)
            fallout = (f" {len(after)} more failed on a name the first one never bound "
                       f"({'; '.join(str(one)[:40] for one in after)}) — those are the same "
                       f"failure, not others." if after else "")
            ontology.note_hint(
                f"{len(broke)} statement(s) in this block failed; the rest of the block ran, "
                f"{ran_after} of them after the first failure — everything that did not raise is "
                f"in the world. The first failure is reported below"
                + (f"; the others: {others}." if others else ".") + fallout
            )
        raise broke[0]


def _what_survived(namespace: dict, session) -> tuple[list[str], list[str]]:
    """After a failure: which variables are still worth something, and which only look it.

    A run is rolled back, but the namespace is not — the lookups, the dates, the strings a host
    computed before the failure are all still bound, and telling it to "send the whole block
    again" throws away work it does not have to redo. The one trap is an entity created in the
    rolled-back run: the variable still holds the object, and the object is no longer in the
    world (its id was taken back), so saying which names those are matters more than the rest.
    """
    standing, unrecorded = [], []
    for name, value in namespace.items():
        if name.startswith("_") or name in getattr(session, "preset", set()) or callable(value):
            continue
        if isinstance(value, Entity):
            (unrecorded if getattr(value, "id", None) is None else standing).append(name)
        elif isinstance(value, (str, int, float, bool, list, tuple, dict, set)) or hasattr(value, "matches"):
            standing.append(name)
    return standing[:12], unrecorded[:12]


def _discarded(recording) -> list[str]:
    """What a failed run had written before it failed — rolled back with the rest of it. Named
    here because a host that saw those lines print tends to assume they stuck and move on."""
    if recording is None:
        return []
    names = []
    for key, entity in recording.changed.items():
        if not recording.attrs.get(key, set()) - _BOOKKEEPING:
            continue  # only touched, nothing of its own was written
        try:
            names.append(f"{type(entity).__name__} «{entity.display_name()}»")
        except Exception:  # noqa: BLE001 - a half-built entity is exactly what this is about
            names.append(type(entity).__name__)
    return names


def format_result(result: dict) -> str:
    """A run's result as the text a host reads."""
    parts = []
    if result.get("session_reset"):
        parts.append("[session was reset after a long pause — earlier variables are gone]")
    parts.append(result["output"] or "(no output)")
    if result["error"]:
        ran = result.get("ran_before") or {}
        done = ran.get("lines", 0)
        told = [f"[stopped here — the {done} line(s) before this one are done and kept; "
                f"only this one was undone]" if done else "[stopped on the first line]"]
        if result.get("unrecorded"):
            told.append("[not in the world] " + ", ".join(result["unrecorded"])
                        + " — this one was being made when the line failed, so it was undone:"
                        " make it again if you still want it")
        told.append("Your block as it now stands — the done part is there to read, not to send "
                    "again; write the continuation under it:")
        parts.append("\n".join(told) + "\n" + (result.get("block") or result["error"]))
        if result.get("block"):
            parts.append(result["error"])
    for kind in ("created", "updated", "found", "comments", "assumed", "hints"):
        if result.get(kind):
            parts.append(f"[{kind}] " + "; ".join(result[kind]))
    if result.get("ask_now"):
        parts.append("[ask first] " + "; ".join(result["ask_now"])
                     + " — this run's answer depends on it: put it to the user before answering, "
                       "or answer by the standing reading above and say so")
    if result.get("clarify"):
        # Not a doubt and not a failure: the block ran and the world wants a line more. The
        # answer is code, so it is given as code, with the variable the host itself wrote —
        # a host told "describe the thing" writes about the wrong one often enough that the
        # variable is the whole point of asking here rather than at the close.
        parts.append("[to fill in] the block ran. Run these next, with real words in place of "
                     "the dots — each answers a question the world would otherwise have to "
                     "guess:\n" + "\n".join(f"    {line}" for line in result["clarify"]))
    if result.get("questions"):
        parts.append("[open questions] " + "; ".join(result["questions"])
                     + " — put them to the user if they're here; entity.questions() to answer or drop them")
    if result.get("undecided"):
        count = result["undecided"]
        parts.append(f"[undecided] {count} thing(s) this task raised are still nobody's decision. "
                     f"finish_task will not close until each is answered, handed to the user with "
                     f"q.for_the_user(why), or dropped. Settling them as you go is cheaper than "
                     f"finding {count} of them at the end.")
    if result["new_variables"]:
        parts.append("[new variables] " + "; ".join(f"{k}: {v}" for k, v in result["new_variables"].items()))
    return "\n".join(parts)


# How many failing statements before a block is called hopeless. Three is a mistake repeated;
# beyond that the host is writing against a world it has misunderstood, and running on wastes a
# turn producing forty copies of one error.
_GIVE_UP_AFTER = 3


# What a host writes when it is adding to the vocabulary rather than using it.
# Attributes are not in here, and not for want of trying. "given names / other names they go by"
# reads 0.701 like `aliases` and 0.684 like `full_name` — seventeen thousandths between the right
# answer and an unrelated field of the same class. Attribute names are short and their
# descriptions formulaic, so everything on one class reads alike, and a reminder that names the
# wrong twin half the time is worse than none.
_DECLARING = {"define": "class", "define_relation": "relation type"}


def _about_to_invent(runtime, tree) -> list[str]:
    """Before the code runs: is it naming something this world already has under another word?

    The host does not study the world — 46 relation types defined in one run against two calls
    to `describe_classes` and none at all to `classes_like`. So the looking happens here, on the
    way in, attached to the very line that would make the second word. Said afterwards it would
    be a post-mortem; said in the prompt it would be an instruction, and instructions are what
    this world stopped relying on.
    """
    proposed = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if called not in _DECLARING:
            continue
        words = [a.value for a in node.args if isinstance(a, ast.Constant)
                 and isinstance(a.value, str)]
        if words:
            proposed.append((_DECLARING[called], words[0], " ".join(words[:2])))
    if not proposed:
        return []
    return _reads_like(runtime, proposed)


def _reads_like(runtime, proposed: list) -> list[str]:
    """For each name about to be declared, the nearest thing the world already holds."""
    known: dict[str, tuple[str, str]] = {}
    for name, cls in runtime.classes.items():
        spec = cls._spec
        rel = spec.get("relation")
        if rel and rel.get("free"):
            continue
        what = "relation type" if rel else "class"
        known[f"{what}:{name}"] = (name, f"{name.replace('_', ' ')}. {spec.get('description', '')}")
        for attr in spec.get("attributes", []):
            if attr["name"] in ("subject", "object") or "derived" in attr:
                continue
            known[f"attribute:{name}.{attr['name']}"] = (
                f"{name}.{attr['name']}",
                f"{attr['name'].replace('_', ' ')}. {attr.get('description', '')}")
    said = []
    for what, name, text in proposed:
        theirs = [key for key in known if key.startswith(f"{what}:")]
        if not theirs:
            continue
        from terraweaver import authoring

        vectors = runtime.world.meanings.model.embed([text] + [known[k][1] for k in theirs])
        best, score = None, 0.0
        for key, vector in zip(theirs, vectors[1:]):
            close = sum(a * b for a, b in zip(vectors[0], vector))
            if close > score:
                best, score = known[key][0], close
        if best and score >= authoring.SAME_IDEA - 0.08 and best.lower() != name.lower():
            said.append(
                f"about to define the {what} '{name}', and this world already has '{best}', "
                f"which reads much the same. describe_classes([\"{best.split('.')[0]}\"]) says "
                f"what it is made of. One idea under two words makes every later question ask "
                f"both."
            )
    return said


def _host_traceback(exc: BaseException, code: str = "") -> str:
    """The error as the host needs it: frames of its own code only, plus the message.

    With the code in hand it also draws the boundary — what ran before the failure, the line
    that broke, and what was never reached. A host that can see the cut fixes one line and
    sends the rest; without it, the usual answer is to send everything again.
    """
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<run>"]
    lines = []
    if frames and code:
        where = frames[-1].lineno or 0
        source = code.splitlines()
        if 0 < where <= len(source):
            ran = len([l for l in source[:where - 1] if l.strip()])
            left = len([l for l in source[where:] if l.strip()])
            lines.append(f"line {where}: {source[where - 1].strip()}")
            lines.append(f"({ran} line(s) before it are done; {left} after it never ran)")
        else:
            lines.append(f"line {where}")
    elif frames:
        lines.append(f"line {frames[-1].lineno}")
    lines.append("".join(traceback.format_exception_only(type(exc), exc)).strip())
    return "\n".join(lines)


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n... [output truncated: {len(text)} chars in total]"
