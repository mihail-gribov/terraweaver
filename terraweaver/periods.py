"""When things held: one table, built from the statements, normalised.

Everything in this world that holds for a time — an entity's validity, a relation, a tag — says
so on the statement that claimed it. That is the record, and the record is append-only: "on in
March, off in June" and "on again in June" are two rows and stay two rows, because nothing in
the record is ever rewritten.

Which is right for a record and wrong for working with. Two stretches that touch are one stretch;
a stretch inside another is not news; a question like "what held in June" should not have to walk
every statement ever made. So the periods are also kept here, as a derivation: one row per
stretch, coalesced — the same relation to the statements that images have, and as disposable.

    subject   whom it is about
    nature    what kind of thing held: "tags", "valid", "kin", "membership"
    value     which one — the tag, the other end of the relation, or nothing for plain validity
    starts    from                   (null: since it was said)
    until     to                     (null: still holding)

What the normalising does, and it is deterministic, so a script does it and nobody argues:
stretches that overlap or touch become one; a stretch wholly inside another disappears into it.
Rebuild it whenever: `periods.rebuild(world)` throws the table away and derives it again, and
nothing about the world changes.
"""
from datetime import datetime

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS periods (
    subject TEXT NOT NULL,
    nature TEXT NOT NULL,
    value TEXT,
    starts TEXT,
    until TEXT
);
CREATE INDEX IF NOT EXISTS idx_periods_subject ON periods(subject, nature);
CREATE INDEX IF NOT EXISTS idx_periods_value ON periods(nature, value);
"""

# Slots whose statements describe a stretch of time rather than a value that simply is.
OVER_TIME = ("tags",)


def rebuild(world) -> int:
    """Derive the table again from every statement. Returns how many stretches it holds."""
    run_script(world.store.conn, SCHEMA)
    world.store.conn.execute("DELETE FROM periods")
    rows = 0
    for subject, nature, value, stretches in _from_statements(world):
        for starts, until in coalesce(stretches):
            world.store.conn.execute(
                "INSERT INTO periods (subject, nature, value, starts, until) VALUES (?, ?, ?, ?, ?)",
                (subject, nature, value, starts.isoformat() if starts else None,
                 until.isoformat() if until else None))
            rows += 1
    world.store.conn.commit()
    return rows


def coalesce(stretches: list) -> list:
    """Overlapping or touching stretches become one; a stretch inside another disappears into it.

    The whole reason this table exists. It is arithmetic over intervals, so it is the same every
    time and nobody has to decide anything.
    """
    ordered = sorted(stretches, key=lambda pair: (pair[0] or datetime.min, pair[1] or datetime.max))
    out: list = []
    for starts, until in ordered:
        if not out:
            out.append([starts, until])
            continue
        last_starts, last_until = out[-1]
        if last_until is None:  # the one before never ends: everything after is inside it
            continue
        if starts is None or starts <= last_until:
            if until is None or last_until is None or until > last_until:
                out[-1][1] = until
        else:
            out.append([starts, until])
    return [(starts, until) for starts, until in out]


def holding(world, subject: str, nature: str, at: datetime | None = None) -> list[str]:
    """What held for this subject at a moment — the values, without walking the statements."""
    run_script(world.store.conn, SCHEMA)
    moment = (at or datetime.utcnow()).isoformat()
    rows = world.store.conn.execute(
        "SELECT value FROM periods WHERE subject = ? AND nature = ? "
        "AND (starts IS NULL OR starts <= ?) AND (until IS NULL OR until > ?)",
        (subject, nature, moment, moment)).fetchall()
    return [value for (value,) in rows if value is not None]


def carrying(world, nature: str, value: str, at: datetime | None = None) -> list[str]:
    """Which subjects held this value at a moment — the question asked from the other end."""
    run_script(world.store.conn, SCHEMA)
    moment = (at or datetime.utcnow()).isoformat()
    rows = world.store.conn.execute(
        "SELECT DISTINCT subject FROM periods WHERE nature = ? AND value = ? "
        "AND (starts IS NULL OR starts <= ?) AND (until IS NULL OR until > ?)",
        (nature, value, moment, moment)).fetchall()
    return [subject for (subject,) in rows]


def stretches(world, subject: str, nature: str, value: str | None = None) -> list[tuple]:
    """Every stretch, coalesced, in order — (value, from, to)."""
    run_script(world.store.conn, SCHEMA)
    where = "subject = ? AND nature = ?" + (" AND value = ?" if value is not None else "")
    args = [subject, nature] + ([value] if value is not None else [])
    rows = world.store.conn.execute(
        f"SELECT value, starts, until FROM periods WHERE {where} ORDER BY starts", args).fetchall()
    return [(value, _parse(starts), _parse(until)) for value, starts, until in rows]


def _from_statements(world):
    """(subject, nature, value, stretches) for everything the statements say held for a time."""
    gathered: dict = {}
    for slot in OVER_TIME:
        for statement in world.facts.with_slot(slot):
            values = statement.value if isinstance(statement.value, list) else [statement.value]
            for one in values:
                if not isinstance(one, str):
                    continue
                from terraweaver import tags as tagging

                key = (statement.subject, slot, tagging.canonical(one) if slot == "tags" else one)
                gathered.setdefault(key, []).append(
                    (statement.valid_from or statement.stated_at, statement.valid_until))
    for (subject, nature, value), found in gathered.items():
        yield subject, nature, value, found


def _parse(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None
