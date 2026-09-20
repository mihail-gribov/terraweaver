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

from terraweaver import ontology, sandbox
from terraweaver.impls import IMPLS
from terraweaver.ontology import COMMON_MEMBERS, Entity, build_classes, describe_for_prompt, load_specs
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

HOST_GUIDE = """\
This is the user's personal world: a Python object model backed by storage. You work with it
by sending Python code to the `run` tool. Print what you need to see — stdout is what you get
back. Variables persist between `run` calls in this session, so build on earlier results.

In the namespace: every class below, `world`, `owner` (the person this world belongs to), `me`
(the assistant persona), and `NeedsResolution`.

World variables (listed below, if any) are the few named things every session shares: use
them as they are instead of looking them up again. Set or change one with
`world.pin(anna, value, "description")`, remove with `world.unpin(anna, stats)` — name them as
variables, no quotes needed. Pin only what will
matter beyond this task, and describe what it is.

Variables are working memory for one task. Starting a new task, call `reset_session` first, so
nothing from an earlier task — an entity settled for another conversation, a stale query
result — carries over. After a long pause the session is reset for you. Anything that must
outlive the task belongs in the world, not in a variable.

Rules the world enforces:
- Each `run` is atomic: if your code raises, nothing it wrote is kept — including the lines
  that printed before it failed. The error names what was discarded; send the whole block
  again, not only the line that failed.
- What isn't in the world isn't known. An empty result means the information isn't there — say
  so rather than filling the gap.
- Before recording what the user tells you, decide from the conversation whether it is about
  something already in the world or something new, and say so by the call: `Class.get(...)`
  for an existing one (never creates; NotInWorld if absent), `Class.new(...)` for a new one
  (asks the user if its twin exists), `Class.ensure(...)` only when you genuinely can't tell.
  Never construct `Class(...)` directly. Check the [created] / [updated] / [found] lines of
  each result against what you meant. What has no attribute to go into is attached as a dated
  remark: `anna.comment("allergic to nuts", when=date(...))`.
- Which entity the user means is never yours to guess. Look it up with everything the user
  already told you — `Person.find(full_name="Annie", organization=cloudnine)`, not just the name.
  If it is still open, you get a NeedsResolution; printing it shows the question and the
  candidates (`needs.candidates`). Ask the user, then `entity = world.settle(needs, <the entity
  they meant>)`, or `world.settle(needs, new=True)` if it's someone new. Never answer it
  yourself — not even with new=True. If the user won't choose, leave it unresolved.
- Assigning an attribute is your statement and goes through: `anna.email = "..."` when the user
  says it changed, or when you concluded it. The old value is kept — `anna.history("email")`.
  A disagreement shows up as a question only when identifying: `Person.ensure(full_name="Ada",
  organization=dataworks)` with Ada recorded at TechCorp asks whether it changed, the record is
  right, or it's a different person — `world.settle(needs, <the value that is right>)`, or
  `new=True` for a different one.
- Your code can reach the world and plain computation only. """ + sandbox.AVAILABLE + "\n"


class WorldView:
    """What host code sees as `world`: the operations, not the machinery.

    The real World holds the store, and the store holds the database connection — handing it
    over would let host code run raw SQL past every check.
    """

    def __init__(self, world: World, variables: WorldVariables, session_key: str):
        self._world = world
        self._variables = variables
        self._session_key = session_key

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

    def questions(self, limit: int = 20):
        """Everything open across the world — what could be cleared up while the user is here."""
        return self._world.questions.open_(limit)

    def comments(self, since=None, until=None, contains: str | None = None, limit: int = 50,
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

    def __repr__(self):
        return "<world: all, find, get, new, ensure, settle, comments, pin, unpin, owner, me, pending>"


class WorldRuntime:
    def __init__(self, db_path: str, fixture: str | None = None, rebuild: bool = False):
        self.db_path = db_path
        self.fixture = fixture
        self.specs = load_specs(ONTOLOGY_DIR)
        self.classes = build_classes(self.specs, IMPLS)
        self.store = Store(db_path)
        self.store.conn.executescript(RUNS_SCHEMA)
        self.world = World(self.store, self.classes)
        reserved = set(self.classes) | set(sandbox.MODULES) | {
            "world", "owner", "me", "NeedsResolution", "NotInWorld", "print", "report", "run_skill"}
        self.variables = WorldVariables(self.store, self.classes, reserved | set(sandbox.BUILTINS))
        empty = self.store.conn.execute("SELECT COUNT(*) FROM instances").fetchone()[0] == 0
        if fixture and (rebuild or empty):
            self.reset()
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
            namespace["world"] = WorldView(self.world, self.variables, key)
            namespace["NeedsResolution"] = NeedsResolution
            namespace["NotInWorld"] = NotInWorld
            namespace["__builtins__"] = sandbox.BUILTINS
            namespace.update(sandbox.MODULES)
            session.preset |= set(sandbox.MODULES) | {"__builtins__", "NotInWorld"}
            self.sessions[key] = session
        session = self.sessions[key]
        session.last_used = time.time()
        return session

    def reset_session(self, key: str) -> None:
        """Drop a session's variables: the next call starts with a clean namespace."""
        self.sessions.pop(key, None)
        self.idle_reset.discard(key)

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
            describe_for_prompt(self.specs),
            self.variables.describe(),
            self._questions_note(),
            session.describe_for_prompt(),
        ])

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
                    "hints": [], "questions": [], "new_variables": {}, "duration_ms": 0}
        if not name.isidentifier():
            return {"ok": False, "output": "", "error": f"{name!r} can't be a variable name",
                    "access": {}, "created": [], "updated": [], "found": [], "comments": [], "assumed": [],
                    "hints": [], "questions": [], "new_variables": {}, "duration_ms": 0}
        return self.run(f"world.pin({name}, ({expression}), {description!r})", key)

    def unset_variables(self, key: str, names: str) -> dict[str, Any]:
        """Remove world variables named in one string: "anna, stats" or "anna stats"."""
        listed = [n for n in names.replace(",", " ").split() if n]
        bad = [n for n in listed if not n.isidentifier()]
        if bad:
            return {"ok": False, "output": "", "error": f"not variable names: {', '.join(bad)}",
                    "access": {}, "created": [], "updated": [], "found": [], "comments": [], "assumed": [],
                    "hints": [], "questions": [], "new_variables": {}, "duration_ms": 0}
        return self.run(f"world.unpin({', '.join(listed)})" if listed else "pass", key)

    def _open_questions(self, recording) -> list[str]:
        """What is open about the entities this run worked with. A host that touches Michael
        should be told his two dentists are still unresolved — the hint that raised it was read
        once, in some earlier run, and the doubt outlived it."""
        seen, out = set(), []
        for entity in list(recording.changed.values()) + list(recording.found.values()):
            key = getattr(entity, "id", None)
            if key is None or key in seen:
                continue
            seen.add(key)
            for question in self.world.questions.of(entity):
                options = f" [{' / '.join(question.options)}]" if question.options else ""
                out.append(f"{entity.display_name()}: {question.text}{options}")
        return out[:5]

    def run(self, code: str, key: str) -> dict[str, Any]:
        session = self.session(key)
        namespace = session.namespace
        stdout = io.StringIO()
        error = None
        recording = None
        rolled_back: list[str] = []
        access: dict[str, int] = {}
        effects = {"created": [], "updated": [], "found": [], "comments": [], "assumed": [], "hints": [],
                   "questions": []}
        started = time.monotonic()
        # World variables are fresh in every run: entities come from the world as they are now,
        # and one pinned by another session shows up here too.
        world_vars = self.variables.load()
        for name in session.world_vars - set(world_vars):
            namespace.pop(name, None)
        namespace.update(world_vars)
        session.world_vars = set(world_vars)
        try:
            tree = _variables_by_name(sandbox.check(code, protected=set(world_vars)))
            with self.store.transaction():
                with contextlib.redirect_stdout(stdout), ontology.track_access() as counts, \
                        ontology.record_changes() as recording, sandbox.time_limit():
                    exec(compile(tree, "<run>", "exec"), namespace)
                access = dict(counts)
                self._persist(recording, namespace)
                effects = _effects(recording, created={id(o) for o in self.store._tx_new_ids})
                effects["questions"] = _merge_questions(effects["questions"], self._open_questions(recording))
        except (Exception, sandbox.RunTimeout) as exc:  # noqa: BLE001 - reporting any failure to the host is the point
            error = _host_traceback(exc)
            rolled_back = _discarded(recording)
            self._refresh(namespace)
        new_names = session.sync()
        result = {
            "session_reset": key in self.idle_reset,
            "ok": error is None,
            "output": _truncate(stdout.getvalue()),
            "error": error,
            "rolled_back": rolled_back,
            "access": access,
            **effects,
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

    made, changed = [], []
    for key, entity in recording.changed.items():
        if key in created:
            made.append(name(entity))
            continue
        attrs = sorted(recording.attrs.get(key, set()) - _BOOKKEEPING)
        if attrs:
            changed.append(f"{name(entity)}: {', '.join(attrs)}")
    found = [name(e) for key, e in recording.found.items()
             if key not in created and not recording.attrs.get(key, set()) - _BOOKKEEPING]
    return {"created": made, "updated": changed, "found": found, "comments": list(recording.remarks),
            "assumed": list(recording.assumed), "hints": list(recording.hints),
            "questions": list(recording.questions)}


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
        undone = result.get("rolled_back") or []
        lost = f" — {', '.join(undone[:5])} " + ("were" if len(undone) > 1 else "was") + " discarded" if undone else ""
        parts.append(f"[error — nothing from this run was kept{lost}. A run is all or nothing: "
                     f"send the whole block again, not only the line that failed]\n{result['error']}")
    for kind in ("created", "updated", "found", "comments", "assumed", "hints"):
        if result.get(kind):
            parts.append(f"[{kind}] " + "; ".join(result[kind]))
    if result.get("questions"):
        parts.append("[open questions] " + "; ".join(result["questions"])
                     + " — put them to the user if they're here; entity.questions() to answer or drop them")
    if result["new_variables"]:
        parts.append("[new variables] " + "; ".join(f"{k}: {v}" for k, v in result["new_variables"].items()))
    return "\n".join(parts)


def _host_traceback(exc: BaseException) -> str:
    """The error as the host needs it: frames of its own code only, plus the message."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<run>"]
    lines = [f"line {f.lineno}" for f in frames[-1:]]
    lines.append("".join(traceback.format_exception_only(type(exc), exc)).strip())
    return "\n".join(lines)


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n... [output truncated: {len(text)} chars in total]"
