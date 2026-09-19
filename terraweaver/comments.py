"""Dated free-form comments attached to any entity.

The object model can't foresee everything worth knowing: a friend's allergy, that a company
froze hiring in March, that the user *might* move in spring. Rather than lose such facts or
invent attributes on the spot, they are attached to the entity they're about as comments:
free text, with the date the thing happened (when known), the date it was recorded, and
whether it's confirmed or only tentative.

Kept in a table of their own, not as an attribute: they're append-mostly, queryable across
entities, can be forgotten one by one, and don't weigh on loading an entity.

Remarks go stale. Each has an end (`until`): the host gives it — until=, ttl=, or
permanent=True for what holds for good — or it gets a default, DEFAULT_TTL from when it was
recorded, TENTATIVE_TTL for an unconfirmed one. An expired remark isn't false, it's history
("lived in Moscow until 2025"): it drops out of ordinary reads but stays retrievable with
include_expired=True, so a default that turns out too short loses nothing. Deleting is what
forget() is for.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from terraweaver import ontology, timeutil

SCHEMA = """
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    text TEXT NOT NULL,
    happened_at TEXT,            -- when the thing itself happened or holds; NULL if unknown
    recorded_at TEXT NOT NULL,   -- when it was written down
    tentative INTEGER NOT NULL DEFAULT 0,
    valid_until TEXT,            -- after this it's history, not current; NULL = no end
    default_ttl INTEGER NOT NULL DEFAULT 0   -- the end came from TENTATIVE_TTL, not the host
);
CREATE INDEX IF NOT EXISTS idx_comments_entity ON comments(entity_id);
"""

# How long a remark counts as current when the host didn't say.
DEFAULT_TTL = timedelta(days=180)
TENTATIVE_TTL = timedelta(days=30)


@dataclass
class Comment:
    """One dated remark about an entity."""

    id: int
    about: Any  # the entity it's attached to
    text: str
    when: date | datetime | None
    recorded_at: datetime
    tentative: bool
    until: date | datetime | None = None
    _book: "Comments" = field(repr=False, compare=False, default=None)

    @property
    def expired(self) -> bool:
        return self.until is not None and _as_datetime(self.until) < _now()

    def forget(self) -> None:
        """Remove this comment for good — the user asked for it to be forgotten, or it was wrong."""
        self._book.forget(self)

    def confirm(self) -> None:
        """Mark a tentative comment as confirmed. A default end restarts as the ordinary default."""
        self.until = self._book.confirm(self)
        self.tentative = False

    def keep(self, until=None, ttl=None, permanent: bool = False) -> None:
        """Set how long this remark holds: until=date, ttl=timedelta (from now), or permanent=True."""
        self.until = self._book.set_end(self, until=until, ttl=ttl, permanent=permanent)

    def __repr__(self):
        when = f"{_show_date(self.when)}: " if self.when else ""
        flag = " (tentative)" if self.tentative else ""
        if self.until is not None:
            flag += f" (expired {_show_date(self.until)})" if self.expired else f" (until {_show_date(self.until)})"
        return f"<Comment on {self.about.label()} — {when}{self.text}{flag}>"


class Comments:
    def __init__(self, store, classes: dict[str, type]):
        self.store = store
        self.classes = classes
        store.conn.executescript(SCHEMA)
        # Tables created before remarks could expire lack these columns.
        columns = {row[1] for row in store.conn.execute("PRAGMA table_info(comments)")}
        if "valid_until" not in columns:
            store.conn.execute("ALTER TABLE comments ADD COLUMN valid_until TEXT")
        if "default_ttl" not in columns:
            store.conn.execute("ALTER TABLE comments ADD COLUMN default_ttl INTEGER NOT NULL DEFAULT 0")
        store.conn.commit()

    def add(self, entity, text: str, when=None, tentative: bool = False, until=None, ttl=None,
            permanent: bool = False) -> Comment:
        if entity.id is None:
            raise ValueError("record the entity in the world first (ensure), then comment on it")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("a comment needs text")
        if when is not None and not isinstance(when, (date, datetime)):
            raise TypeError("when must be a date or datetime — the day the thing happened or holds")
        explicit = timeutil.period_end(until, ttl, permanent, base=_as_datetime(when) if when is not None else _now())
        default = explicit is timeutil.NO_END_GIVEN
        ends = (_now() + (TENTATIVE_TTL if tentative else DEFAULT_TTL)) if default else explicit
        recorded = datetime.now(timezone.utc)
        ontology.note_world_call("world_writes")
        with self.store.transaction():
            cursor = self.store.conn.execute(
                "INSERT INTO comments (entity_id, text, happened_at, recorded_at, tentative, valid_until, default_ttl) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entity.id, text.strip(), _encode_date(when), recorded.isoformat(), int(bool(tentative)),
                 _encode_date(ends), int(default)),
            )
        ontology.note_remark(f"added on {entity.label()}: {text.strip()}")
        return Comment(cursor.lastrowid, entity, text.strip(), when, recorded, bool(tentative), ends, self)

    def set_end(self, comment: Comment, until=None, ttl=None, permanent: bool = False):
        explicit = timeutil.period_end(until, ttl, permanent, base=_now())
        if explicit is timeutil.NO_END_GIVEN:
            raise ValueError("say how long it holds: until=date(...), ttl=timedelta(...), or permanent=True")
        ontology.note_world_call("world_writes")
        with self.store.transaction():
            self.store.conn.execute("UPDATE comments SET valid_until = ?, default_ttl = 0 WHERE id = ?",
                                    (_encode_date(explicit), comment.id))
        return explicit

    def of(self, entity, since=None, until=None, contains: str | None = None,
           include_expired: bool = False) -> list[Comment]:
        """An entity's comments, newest first (by when it happened, else when recorded)."""
        if entity.id is None:
            return []
        return self._query("entity_id = ?", (entity.id,), since, until, contains, include_expired)

    def search(self, since=None, until=None, contains: str | None = None, limit: int = 50,
               include_expired: bool = False) -> list[Comment]:
        """Comments across the whole world."""
        return self._query("1 = 1", (), since, until, contains, include_expired)[:limit]

    def forget(self, comment: Comment) -> None:
        ontology.note_world_call("world_writes")
        with self.store.transaction():
            self.store.conn.execute("DELETE FROM comments WHERE id = ?", (comment.id,))
        ontology.note_remark(f"forgotten on {comment.about.label()}: {comment.text}")

    def confirm(self, comment: Comment):
        """Confirm a remark. Returns its end: kept if the host set it, the ordinary default if not."""
        ontology.note_world_call("world_writes")
        with self.store.transaction():
            self.store.conn.execute(
                "UPDATE comments SET tentative = 0, "
                "valid_until = CASE WHEN default_ttl = 1 THEN ? ELSE valid_until END WHERE id = ?",
                (_encode_date(_now() + DEFAULT_TTL), comment.id))
            row = self.store.conn.execute("SELECT valid_until FROM comments WHERE id = ?", (comment.id,)).fetchone()
        return _decode_date(row[0]) if row else None

    def clear(self) -> None:
        self.store.conn.execute("DELETE FROM comments")

    # --- internals ---

    def _query(self, where: str, params: tuple, since, until, contains, include_expired: bool = False) -> list[Comment]:
        ontology.note_world_call("world_queries")
        sql = f"SELECT id, entity_id, text, happened_at, recorded_at, tentative, valid_until FROM comments WHERE {where}"
        args = list(params)
        if contains:
            sql += " AND text LIKE ?"
            args.append(f"%{contains}%")
        rows = self.store.conn.execute(sql, args).fetchall()
        out = []
        for cid, entity_id, text, happened, recorded, tentative, valid_until in rows:
            ends = _decode_date(valid_until)
            if not include_expired and ends is not None and _as_datetime(ends) < _now():
                continue
            when = _decode_date(happened)
            key = _as_datetime(when if when else datetime.fromisoformat(recorded))
            if since is not None and key < _as_datetime(since):
                continue
            if until is not None and key > _as_datetime(until):
                continue
            try:
                entity = self.store.load(entity_id, self.classes)
            except KeyError:
                continue
            out.append((key, Comment(cid, entity, text, when, datetime.fromisoformat(recorded), bool(tentative), ends, self)))
        out.sort(key=lambda pair: pair[0], reverse=True)
        return [comment for _, comment in out]


def _encode_date(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return "dt:" + value.isoformat()
    return "d:" + value.isoformat()


def _decode_date(raw: str | None):
    if not raw:
        return None
    kind, text = raw.split(":", 1)
    return datetime.fromisoformat(text) if kind == "dt" else date.fromisoformat(text)


def _as_datetime(value) -> datetime:
    """Comparable across dates, naive and aware datetimes."""
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)


def _now() -> datetime:
    """Now, in the same naive-UTC terms _as_datetime compares in."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _show_date(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime) else value.isoformat()
