"""World variables: a small, explicit, described set of names every host gets.

Session variables are one task's working memory. World variables are the few things worth
naming for good — "anna: the Anna we're working with", "current_project" — so a host doesn't
look them up again or wonder which one is meant.

- Each has a description; a name without one is refused.
- There are few of them (MAX_VARIABLES): they're handed to every host in full, with meaning.
- An entity is kept by id, so the value is always the entity as it is now. Anything else is a
  snapshot, shown with the time it was taken.
- They change only through `world.pin(...)` / `world.unpin(...)`. Plain assignment to such a
  name in host code is refused (see sandbox.check), so nobody overwrites one by accident.

Stored in the world's database, so writes are part of the run's transaction.
"""
import json
import keyword
from datetime import datetime, timezone
from typing import Any

from terraweaver.ontology import Entity

MAX_VARIABLES = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_variables (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,          -- entity | entities | value
    value TEXT NOT NULL,         -- JSON: an id, a list of ids, or the value itself
    description TEXT NOT NULL,
    set_by TEXT,
    set_at TEXT NOT NULL,
    turns_left INTEGER,         -- left from when names had a term; nothing writes it now
    outlives_session INTEGER NOT NULL DEFAULT 0
);
"""

# A pinned name lives as long as the session and no shorter. Names used to be kept for three
# turns, which meant a host could pin something on purpose and get a NameError for it in the
# middle of the thought that needed it — the world quietly forgetting what it was told to hold.
# The session is the unit the host actually thinks in, so it is the unit the name lives in.
#
# Some names are worth more than a session: the person's own home, the project they are in the
# middle of, the calendar they keep. `keep=True` says so, and those stay until they are
# unpinned. The two are kept apart on purpose — a name that survives a conversation nobody
# remembers having is how a world fills with things nobody meant to keep.


class VariableError(Exception):
    """A world variable can't be set this way."""


class WorldVariables:
    def __init__(self, store, classes: dict[str, type], reserved: set[str]):
        self.store = store
        self.classes = classes
        # Names already taken in every namespace: classes, `world`, helpers, modules.
        self.reserved = reserved
        store.conn.executescript(SCHEMA)
        # Worlds written before names had a term keep their table; the column is added to it
        # rather than the table being rebuilt, because what is pinned in them is still pinned.
        held = {row[1] for row in store.conn.execute("PRAGMA table_info(world_variables)")}
        for column, declared in (("turns_left", "INTEGER"),
                                 ("outlives_session", "INTEGER NOT NULL DEFAULT 0")):
            if column not in held:
                store.conn.execute(f"ALTER TABLE world_variables ADD COLUMN {column} {declared}")
        store.conn.commit()

    def names(self) -> set[str]:
        return {row[0] for row in self.store.conn.execute("SELECT name FROM world_variables")}

    def load(self) -> dict[str, Any]:
        """name -> current value. An entity that no longer exists comes back as None."""
        return {name: self._value(kind, raw) for name, kind, raw in self.store.conn.execute(
            "SELECT name, kind, value FROM world_variables ORDER BY name")}

    def pin(self, name: str, value: Any, description: str, set_by: str | None = None,
            keep: bool = False) -> None:
        """Keep a name in the world — for this session, or past it with `keep=True`."""
        if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
            raise VariableError(f"{name!r} can't be a variable name")
        if name in self.reserved:
            raise VariableError(f"'{name}' is already taken in the namespace")
        if not isinstance(description, str) or len(description.strip()) < 3:
            raise VariableError("a world variable needs a description: what it is and why it's kept")
        existing = self.names()
        if name not in existing and len(existing) >= MAX_VARIABLES:
            raise VariableError(
                f"there are already {MAX_VARIABLES} world variables; unpin one that no longer matters first"
            )
        kind, raw = self._encode(value)
        self.store.conn.execute(
            "INSERT OR REPLACE INTO world_variables (name, kind, value, description, set_by, "
            "set_at, outlives_session) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, kind, raw, description.strip(), set_by,
             datetime.now(timezone.utc).isoformat(), int(keep)),
        )

    def session_ended(self, key: str | None) -> list[str]:
        """Let go of the names that belonged to that session. Returns what went."""
        rows = [row[0] for row in self.store.conn.execute(
            "SELECT name FROM world_variables WHERE outlives_session = 0 AND set_by IS ?", (key,))]
        if rows:
            self.store.conn.execute(
                "DELETE FROM world_variables WHERE outlives_session = 0 AND set_by IS ?", (key,))
            self.store.conn.commit()
        return rows

    def unpin(self, *names: str) -> None:
        """Remove world variables. All or nothing: an unknown name removes none of them."""
        missing = [name for name in names if name not in self.names()]
        if missing:
            raise VariableError(f"no world variable named {', '.join(repr(m) for m in missing)}; nothing was removed")
        for name in names:
            self.store.conn.execute("DELETE FROM world_variables WHERE name = ?", (name,))

    def describe(self) -> str:
        rows = list(self.store.conn.execute(
            "SELECT name, kind, value, description, set_at, outlives_session "
            "FROM world_variables "
            "ORDER BY name"))
        if not rows:
            return ""
        lines = [
            "\nWorld variables — yours for this whole session, however the conversation moves.",
            "Use them as they are; don't look these up again. Change one with",
            "world.pin(name, value, \"description\"), drop one with world.unpin(name). Add",
            "keep=True for something that should still be here in a week:",
        ]
        for name, kind, raw, description, set_at, outlives in rows:
            value = self._value(kind, raw)
            shown = _show(value)
            if kind == "value":
                shown += f" (snapshot taken {set_at[:16].replace('T', ' ')} UTC)"
            lines.append(f"- {name}: {shown} — {description}"
                         + (" — kept past this session" if outlives else ""))
        return "\n".join(lines) + "\n"

    # --- internals ---

    def _encode(self, value: Any) -> tuple[str, str]:
        if isinstance(value, Entity):
            if value.id is None:
                raise VariableError("that entity isn't in the world yet — record it with ensure(...) first")
            return "entity", json.dumps(value.id)
        if isinstance(value, (list, tuple)) and value and all(isinstance(v, Entity) for v in value):
            if any(v.id is None for v in value):
                raise VariableError("some of those entities aren't in the world yet")
            return "entities", json.dumps([v.id for v in value])
        try:
            return "value", json.dumps(value, ensure_ascii=False)
        except TypeError:
            raise VariableError(
                "a world variable holds an entity, a list of entities, or plain data (numbers, "
                f"strings, lists, dicts) — not {type(value).__name__}"
            ) from None

    def _value(self, kind: str, raw: str) -> Any:
        data = json.loads(raw)
        if kind == "entity":
            return self._entity(data)
        if kind == "entities":
            return [e for e in (self._entity(i) for i in data) if e is not None]
        return data

    def _entity(self, entity_id: str):
        try:
            return self.store.load(entity_id, self.classes)
        except KeyError:
            return None


def _show(value: Any) -> str:
    if isinstance(value, Entity):
        return f"{type(value).__name__} «{value.display_name()}»"
    if isinstance(value, list) and value and all(isinstance(v, Entity) for v in value):
        return f"[{', '.join(_show(v) for v in value[:5])}{', …' if len(value) > 5 else ''}]"
    if value is None:
        return "(the entity it pointed to is gone)"
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 80 else text[:77] + "..."
