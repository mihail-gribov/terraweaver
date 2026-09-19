"""What an attribute used to be.

Assigning a value is the host's statement — the user said so, or the host concluded it — and
the world doesn't second-guess it. What the world does is keep what was there before: every
overwrite leaves the old value here, with the moment it stopped holding. Nothing a host writes
can erase a fact for good, and "where did Ada work before?" stays answerable.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from terraweaver import timeutil
from terraweaver.store import _decode, _encode

SCHEMA = """
CREATE TABLE IF NOT EXISTS value_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL,
    attr TEXT NOT NULL,
    value TEXT,                  -- encoded like values_: plain JSON, $dt, $ref, $refs
    until TEXT NOT NULL          -- when it stopped being the value
);
CREATE INDEX IF NOT EXISTS idx_value_history ON value_history(instance_id, attr);
"""


@dataclass
class Past:
    """One value an attribute held, and until when (None: it's the current one)."""

    value: Any
    until: datetime | None

    def __repr__(self):
        shown = self.value.display_name() if hasattr(self.value, "display_name") else repr(self.value)
        return f"<{shown} until {timeutil.show(self.until)}>" if self.until else f"<{shown} now>"


class ValueHistory:
    def __init__(self, store, classes: dict[str, type]):
        self.store = store
        self.classes = classes
        store.conn.executescript(SCHEMA)

    def record(self, instance, attr: str, old_value) -> None:
        self.store.conn.execute(
            "INSERT INTO value_history (instance_id, attr, value, until) VALUES (?, ?, ?, ?)",
            (instance.id, attr, _encode(old_value), timeutil.now().isoformat()),
        )

    def of(self, instance, attr: str) -> list[Past]:
        """Past values oldest first, then the current one."""
        rows = self.store.conn.execute(
            "SELECT value, until FROM value_history WHERE instance_id = ? AND attr = ? ORDER BY id",
            (instance.id, attr),
        ).fetchall()
        past = [Past(self._value(raw), datetime.fromisoformat(until)) for raw, until in rows]
        return past + [Past(getattr(instance, attr, None), None)]

    def clear(self) -> None:
        self.store.conn.execute("DELETE FROM value_history")

    def _value(self, raw: str):
        kind, payload = _decode(raw)
        if kind == "dt":
            return datetime.fromisoformat(payload)
        if kind == "ref":
            return self._entity(payload)
        if kind == "refs":
            return [e for e in (self._entity(i) for i in payload) if e is not None]
        return payload

    def _entity(self, entity_id: str):
        try:
            return self.store.load(entity_id, self.classes)
        except KeyError:
            return None
