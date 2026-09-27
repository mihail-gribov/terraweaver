"""SQLite-backed generic instance store (EAV).

Schema-as-data: an `instances` row per object (id, class_name) and, per class, a table of its
own named after it — `Person`, `Organization` — holding one row per attribute, JSON-encoded.
These are the images: the main data, built from what was said (`facts.py`, `assembly.py`) and
rebuildable from it at any time. This is deliberate — renaming/adding/removing an
attribute later is a data operation (update/insert/delete rows), not an ALTER TABLE,
which is what makes the class-refactoring operations from the spec tractable on top
of this store. References to other instances are encoded as {"$ref": id} /
{"$refs": [id, ...]} and resolved on load with a memo dict so reference cycles
(a link, its two ends, and the links those ends are in) don't recurse forever.
"""
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from terraweaver import ontology

SCHEMA = """
CREATE TABLE IF NOT EXISTS instances (
    id TEXT PRIMARY KEY,
    class_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_instances_class ON instances(class_name);
"""


def _is_instance(obj) -> bool:
    return isinstance(obj, ontology.Entity)


def _encode(value: Any) -> str:
    if isinstance(value, datetime):
        return json.dumps({"$dt": value.isoformat()})
    if _is_instance(value):
        return json.dumps({"$ref": value.id})
    if isinstance(value, list) and value and all(_is_instance(v) for v in value):
        return json.dumps({"$refs": [v.id for v in value]})
    return json.dumps(value)


def _decode(raw: str) -> tuple[str, Any]:
    data = json.loads(raw)
    if isinstance(data, dict) and set(data) == {"$dt"}:
        return "dt", data["$dt"]
    if isinstance(data, dict) and set(data) == {"$ref"}:
        return "ref", data["$ref"]
    if isinstance(data, dict) and set(data) == {"$refs"}:
        return "refs", data["$refs"]
    return "plain", data


VALUES = """
CREATE TABLE IF NOT EXISTS "{table}" (
    instance_id TEXT NOT NULL,
    attr TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (instance_id, attr)
)
"""


def run_script(conn, script: str) -> None:
    """Run a schema script one statement at a time, ignoring comments.

    Not `executescript`: that commits whatever transaction is open, and a table made in the
    middle of a run would commit the run with it. And not a plain split on ";" either — a
    semicolon inside a `--` comment cuts a statement in half, which is a bug you find once and
    then never want to find again."""
    lines = [line.split("--")[0] for line in script.splitlines()]
    for statement in "\n".join(lines).split(";"):
        if statement.strip():
            conn.execute(statement)


class Store:
    def __init__(self, path: str = "terraweaver.db"):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        # One row, one object. Without this the same entity can exist twice in memory, and
        # a stale copy saved later silently overwrites a fresh change made through the other
        # — which is how a settled contradiction quietly reverted itself.
        self._identity: dict[str, Any] = {}
        # State of the outermost open transaction: nesting depth and the instances that
        # received their id inside it.
        self._tx_depth = 0
        self._tx_new_ids: list = []
        # What got an id during this run, as against during one transaction. Statements are
        # committed one at a time on purpose, so a per-transaction list is empty by the time
        # anybody asks — and the run then reported everything the host had just made as
        # *updated*, in every slot it has, which reads as "you changed something that was
        # already here". Cleared by whoever is running, not by a transaction ending.
        self.made: list = []

    @contextmanager
    def transaction(self):
        """All writes inside land together or not at all.

        A subgraph is only consistent as a whole — a person saved without the company whose
        employees list now names them is a half-link. Nested calls join the outermost one.
        On failure the database and freshly assigned ids are rolled back, and the identity map
        is dropped: objects in it may carry changes that never reached the database, so the
        next load must come from storage. Objects the caller still holds are stale then.
        """
        if self._tx_depth:
            self._tx_depth += 1
            try:
                yield
            finally:
                self._tx_depth -= 1
            return
        self._tx_depth = 1
        self._tx_new_ids = []
        try:
            yield
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            self._identity = {}
            for obj in self._tx_new_ids:
                obj.id = None
            raise
        finally:
            self._tx_depth = 0
            self._tx_new_ids = []

    def _assign_id(self, instance) -> None:
        if instance.id is None:
            instance.id = uuid.uuid4().hex
            self._tx_new_ids.append(instance)
            self.made.append(instance)

    def save(self, instance) -> str:
        with self.transaction():
            self._assign_id(instance)
            self._identity[instance.id] = instance
            class_name = type(instance).__name__
            self.conn.execute(
                "INSERT OR REPLACE INTO instances (id, class_name) VALUES (?, ?)",
                (instance.id, class_name),
            )
            table = self.values_table(class_name)
            names = [a["name"] for a in instance._spec["attributes"] if "derived" not in a]
            names += [a for a in ontology.MANAGED_VALUE_ATTRS if a not in names]
            for name in names:
                self.conn.execute(
                    f'INSERT OR REPLACE INTO "{table}" (instance_id, attr, value) VALUES (?, ?, ?)',
                    (instance.id, name, _encode(getattr(instance, name, None))),
                )
        return instance.id

    def values_table(self, class_name: str) -> str:
        """The table holding this class's images, made the first time it is needed.

        Not executescript: that commits whatever transaction is open, and a table made in the
        middle of a run would commit the run with it."""
        self.conn.execute(VALUES.format(table=class_name))
        return class_name

    def save_all(self, instances) -> None:
        with self.transaction():
            for inst in instances:
                self.save(inst)

    def save_graph(self, instance, _seen: set[int] | None = None) -> None:
        """Save an instance plus everything it references, so no ref dangles."""
        _seen = _seen if _seen is not None else set()
        graph: list = []
        self._collect(instance, set(), graph)
        with self.transaction():
            # Ids must exist across the whole graph *before* anything is serialized, otherwise
            # a ref to a not-yet-saved instance would be written as {"$ref": null}.
            for obj in graph:
                self._assign_id(obj)
            for obj in graph:
                if id(obj) not in _seen:
                    _seen.add(id(obj))
                    self.save(obj)

    def _collect(self, instance, visited: set[int], out: list) -> None:
        if id(instance) in visited:
            return
        visited.add(id(instance))
        out.append(instance)
        for attr in instance._spec["attributes"]:
            if "derived" in attr:
                continue
            value = getattr(instance, attr["name"], None)
            if _is_instance(value):
                self._collect(value, visited, out)
            elif isinstance(value, list):
                for item in value:
                    if _is_instance(item):
                        self._collect(item, visited, out)

    def clear_all(self) -> None:
        with self.transaction():
            for (table,) in self.conn.execute(
                    "SELECT DISTINCT class_name FROM instances").fetchall():
                self.conn.execute(f'DELETE FROM "{self.values_table(table)}"')
            self.conn.execute("DELETE FROM instances")
            # Remarks hang off instances by id; a rebuilt world must not inherit old ones.
            for table in ("comments", "name_choices", "value_history", "questions"):
                if self.conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone():
                    self.conn.execute(f"DELETE FROM {table}")
            self._identity.clear()

    def clear(self, class_name: str) -> None:
        with self.transaction():
            ids = [r[0] for r in self.conn.execute("SELECT id FROM instances WHERE class_name = ?", (class_name,))]
            self.conn.execute(f'DELETE FROM "{self.values_table(class_name)}"')
            self.conn.execute("DELETE FROM instances WHERE class_name = ?", (class_name,))
            for instance_id in ids:
                self._identity.pop(instance_id, None)

    def forget(self, instance_id: str) -> None:
        """Remove one instance's image. For something the world concluded and no longer believes:
        the statements behind it are retracted separately, and what was *said* is never removed."""
        row = self.conn.execute("SELECT class_name FROM instances WHERE id = ?",
                                (instance_id,)).fetchone()
        if row is None:
            return
        with self.transaction():
            self.conn.execute(f'DELETE FROM "{self.values_table(row[0])}" WHERE instance_id = ?',
                              (instance_id,))
            self.conn.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
        self._identity.pop(instance_id, None)

    def is_live(self, instance) -> bool:
        """Whether this object is the one the identity map holds for its row (or nothing does)."""
        held = self._identity.get(instance.id)
        return held is None or held is instance

    def load(self, instance_id: str, classes: dict[str, type]):
        """One instance by id, through the identity map."""
        return self._load(instance_id, classes)

    def load_all(self, class_name: str, classes: dict[str, type]) -> list:
        ids = [r[0] for r in self.conn.execute("SELECT id FROM instances WHERE class_name = ?", (class_name,))]
        return [self._load(instance_id, classes, self._identity) for instance_id in ids]

    def _load(self, instance_id: str, classes: dict[str, type], memo: dict[str, Any] | None = None):
        memo = self._identity if memo is None else memo
        if instance_id in memo:
            return memo[instance_id]
        row = self.conn.execute("SELECT class_name FROM instances WHERE id = ?", (instance_id,)).fetchone()
        if row is None:
            raise KeyError(f"no instance with id {instance_id!r}")

        cls = classes[row[0]]
        obj = object.__new__(cls)  # bypass __init__: cyclic refs must register in memo before being filled in
        # Loading is machinery, not a user-driven change: no guard, and nothing to record.
        with ontology.trusted_writes(), ontology.not_recording():
            obj.id = instance_id
            memo[instance_id] = obj
            derived = ontology.derived_names(cls._spec)
            known = {a["name"] for a in cls._spec["attributes"]} | set(ontology.MANAGED_VALUE_ATTRS)
            # Read every row before setting anything. Filling an attribute can load a
            # referenced instance, which runs its own queries — including a CREATE TABLE for a
            # class whose table doesn't exist yet — and an open cursor does not reliably survive
            # that. It used to cut the loop short, silently dropping whatever came last in the
            # table: Event.title read back as None while the row said "Rent".
            rows = self.conn.execute(
                f'SELECT attr, value FROM "{self.values_table(cls.__name__)}" WHERE instance_id = ?',
                (instance_id,)
            ).fetchall()
            for attr_name, raw in rows:
                if attr_name in derived or attr_name not in known:
                    continue  # stored by an older version: now computed, or no longer part of the class
                kind, payload = _decode(raw)
                if kind == "dt":
                    # Rows written before the world settled on one form of time carry a zone;
                    # they come back in the same form as everything else.
                    when = datetime.fromisoformat(payload)
                    setattr(obj, attr_name,
                            when.astimezone(timezone.utc).replace(tzinfo=None)
                            if when.tzinfo is not None else when)
                elif kind == "ref":
                    try:
                        setattr(obj, attr_name, self._load(payload, classes, memo))
                    except KeyError:
                        # Pointing at something the image no longer holds. Reading it as nothing
                        # is the truth about the image; raising made one stale reference render
                        # every instance of its class unreadable.
                        setattr(obj, attr_name, None)
                elif kind == "refs":
                    kept = []
                    for one in payload:
                        try:
                            kept.append(self._load(one, classes, memo))
                        except KeyError:
                            continue
                    setattr(obj, attr_name, kept)
                else:
                    setattr(obj, attr_name, payload)
        return obj
