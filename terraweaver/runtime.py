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

from terraweaver import onboarding, ontology, sandbox
from terraweaver.impls import IMPLS
from terraweaver.describe import (COMMON_MEMBERS, HOST_GUIDE, catalogue, describe_for_prompt,
                                  describe_methods)
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


class WorldView:
    """What host code sees as `world`: the operations, not the machinery.

    The real World holds the store, and the store holds the database connection — handing it
    over would let host code run raw SQL past every check.
    """

    def __init__(self, world: World, variables: WorldVariables, session_key: str, session=None):
        self._world = world
        self._variables = variables
        self._session_key = session_key
        self._session = session

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

    def all(self, cls, limit: int | None = World.DEFAULT_LIMIT, *, any_time: bool = False, history: bool = False):
        return self._world.all(cls, limit=limit, history=history or any_time)

    def find(self, cls, *, any_time: bool = False, history: bool = False, **attrs):
        return self._world.find(cls, history=history or any_time, **attrs)

    def get(self, cls, **attrs):
        return self._world.get(cls, **attrs)

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

    def pin(self, name: str, value, description: str) -> None:
        """Keep a named value for every session: an entity (by id), entities, or plain data."""
        self._variables.pin(name, value, description, set_by=self._session_key)
        print(f"[pinned] {name}")

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
            namespace["world"] = WorldView(self.world, self.variables, key, session)
            namespace["NeedsResolution"] = NeedsResolution
            namespace["NotInWorld"] = NotInWorld
            namespace["__builtins__"] = sandbox.BUILTINS
            namespace.update(sandbox.MODULES)
            session.preset |= set(sandbox.MODULES) | {"__builtins__", "NotInWorld"}
            self.sessions[key] = session
        session = self.sessions[key]
        session.last_used = time.time()
        return session

    def reset_session(self, key: str) -> str:
        """Drop a session's variables: the next call starts with a clean namespace.

        Returns what was left open about the entities that task worked with. A task ending is
        the one moment the world knows of when the host is free and the user is still there —
        exactly when a question can be put without interrupting anything.
        """
        session = self.sessions.pop(key, None)
        self.idle_reset.discard(key)
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
        load_world(self.fixture)(self.classes, self.store)
        self.sessions = {}

    # --- what hosts call ---

    def describe(self, key: str) -> str:
        session = self.session(key)
        return "\n".join([
            HOST_GUIDE,
            COMMON_MEMBERS,
            catalogue(self.specs),
            self.variables.describe(),
            self._questions_note(),
            session.describe_for_prompt(),
        ])

    def describe_classes(self, names: list[str]) -> str:
        """What the named classes are made of — attributes, methods, relations.

        The prompt carries the names; this carries the detail, for the few classes a task
        actually touches."""
        known = {n.lower(): n for n in self.specs}
        wanted = [known[n.strip().lower()] for n in names if n.strip().lower() in known]
        missing = [n for n in names if n.strip().lower() not in known]
        if not wanted:
            return ("No such class: " + ", ".join(missing) + ".\n\n" + catalogue(self.specs))
        text = describe_for_prompt(self.specs, only=wanted)
        text += ('\nWhat any of these does, in full and with examples: '
                 'describe_methods(["tag", "' + wanted[0] + '.' +
                 (self.specs[wanted[0]].get("methods") or [{"signature": "x"}])[0]["signature"].split("(")[0]
                 + '"])')
        if missing:
            text += "\nNot in this world: " + ", ".join(missing) + "."
        return text

    def describe_methods(self, names: list[str]) -> str:
        """What these methods do, in full, with examples where they help."""
        return describe_methods(self.specs, names)

    def _learn_name_choice(self, session, recording, before: dict) -> list[str]:
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
            tree = _variables_by_name(sandbox.check(code, protected=set(world_vars) | ALWAYS, always=ALWAYS))
            # Statement by statement, each in its own transaction. All-or-nothing was the rule
            # here for a long time, and the measurements turned against it: a fifth to a quarter
            # of every pool's runs ended discarded, most of them over a typo eight lines from
            # anything that mattered. What a completed statement wrote is a whole thought — the
            # subgraph a single call touches is saved together inside it — so keeping it costs
            # no consistency, and the host is told exactly where the block stopped.
            with contextlib.redirect_stdout(stdout), ontology.track_access() as counts, \
                    ontology.record_changes() as recording, sandbox.time_limit():
                _exec_by_statement(tree, namespace, self.store)
            with self.store.transaction():
                access = dict(counts)
                self._persist(recording, namespace)
                learned = self._learn_name_choice(session, recording, before)
                effects = _effects(recording, created={id(o) for o in self.store._tx_new_ids})
                effects["assumed"] += learned
                effects["questions"] += _waiting_on_answers(session)
                session.touched |= {e.id for e in _entities_of(recording)}
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
    """
    import ast

    for statement in tree.body:
        piece = ast.Module(body=[statement], type_ignores=[])
        with store.transaction():
            exec(compile(piece, "<run>", "exec"), namespace)


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
    if result.get("questions"):
        parts.append("[open questions] " + "; ".join(result["questions"])
                     + " — put them to the user if they're here; entity.questions() to answer or drop them")
    if result["new_variables"]:
        parts.append("[new variables] " + "; ".join(f"{k}: {v}" for k, v in result["new_variables"].items()))
    return "\n".join(parts)


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
