"""How often each entity is actually worked with.

A personal world accumulates more open questions than anyone will sit through. Which ones are
worth the user's attention is not a matter of how interesting they look — it's how often the
entity comes up. A doubt about the person the user asks about every week is worth a minute; the
same doubt about someone met once at a conference can wait, possibly forever.

So every `get` / `find` / `ensure` that lands on an entity counts, and the count is what orders
the questions (questions.py). It is bookkeeping, not part of the entity: it lives in its own
table, doesn't weigh on loading, and nothing in the object model can see it.
"""
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_access (
    instance_id TEXT PRIMARY KEY,
    times INTEGER NOT NULL DEFAULT 0,
    last_at TEXT NOT NULL
);
"""


class Usage:
    def __init__(self, store):
        self.store = store
        store.conn.executescript(SCHEMA)

    def record(self, entity) -> None:
        if getattr(entity, "id", None) is None:
            return
        self.store.conn.execute(
            "INSERT INTO entity_access (instance_id, times, last_at) VALUES (?, 1, ?) "
            "ON CONFLICT(instance_id) DO UPDATE SET times = times + 1, last_at = excluded.last_at",
            (entity.id, datetime.now(timezone.utc).isoformat()),
        )

    def times(self, entity_id: str) -> int:
        row = self.store.conn.execute(
            "SELECT times FROM entity_access WHERE instance_id = ?", (entity_id,)).fetchone()
        return row[0] if row else 0

    def counts(self) -> dict[str, int]:
        return {row[0]: row[1] for row in self.store.conn.execute("SELECT instance_id, times FROM entity_access")}

    def clear(self) -> None:
        self.store.conn.execute("DELETE FROM entity_access")
