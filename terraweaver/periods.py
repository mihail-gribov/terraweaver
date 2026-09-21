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
    every     how often it repeats   (null: once — "week", "2 weeks", "month", "quarter", "year")
    lasting   how long each one is    (null: a moment rather than a stretch), in days

A repeating row is the whole series in one row, not a thousand rows: `starts` and `until` are
the window the series runs in, `every` is the step, `lasting` is how much of each step it holds
for. Nothing is expanded into the table, because a rule with no end would fill it forever and a
table cut off at a horizon answers "no" past that horizon — wrong, and quiet about it. The
arithmetic is in recurrence.py, and a question that asks about a window gets the occurrences in
that window (`stretches`), while a question about a moment gets an answer without expanding
anything at all (`holding`, `carrying`).

What the normalising does, and it is deterministic, so a script does it and nobody argues:
stretches that overlap or touch become one; a stretch wholly inside another disappears into it.
Rebuild it whenever: `periods.rebuild(world)` throws the table away and derives it again, and
nothing about the world changes.
"""
from datetime import datetime, timedelta

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS periods (
    subject TEXT NOT NULL,
    nature TEXT NOT NULL,
    value TEXT,
    starts INTEGER,
    until INTEGER,
    every TEXT,
    lasting REAL
);
CREATE INDEX IF NOT EXISTS idx_periods_subject ON periods(subject, nature);
CREATE INDEX IF NOT EXISTS idx_periods_value ON periods(nature, value);
"""

# Slots whose statements describe a stretch of time rather than a value that simply is: the
# dated lists of texts a class declares (`list[text]`), tags among them.
OVER_TIME = ("tags",)


def over_time(world) -> list[str]:
    """Which slots hold texts that come and go — read from the classes, not written down twice."""
    from terraweaver import ontology

    slots = set(OVER_TIME)
    for cls in getattr(world, "classes", {}).values():
        slots |= ontology.dated_lists(getattr(cls, "_spec", {}))
    return sorted(slots)

# Where a repeat rule is kept in the record: one statement saying what repeats, and how.
REPEATS = "repeats"


def rebuild(world) -> int:
    """Derive the table again from every statement. Returns how many stretches it holds."""
    run_script(world.store.conn, SCHEMA)
    _add_missing_columns(world.store.conn)
    world.store.conn.execute("DELETE FROM periods")
    rows = 0
    for subject, nature, value, stretches in _from_statements(world):
        for starts, until in coalesce(stretches):
            _insert(world, subject, nature, value, starts, until)
            rows += 1
    for rule in _repeat_rules(world):
        _insert(world, rule["subject"], rule["nature"], rule.get("value"),
                rule["anchor"], rule.get("ends"), rule["every"], rule.get("lasting"))
        rows += 1
    world.store.conn.commit()
    return rows


def _insert(world, subject, nature, value, starts, until, every=None, lasting=None) -> None:
    from terraweaver import timeutil

    world.store.conn.execute(
        "INSERT INTO periods (subject, nature, value, starts, until, every, lasting) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (subject, nature, value, timeutil.to_db(starts), timeutil.to_db(until), every, lasting))


def _add_missing_columns(conn) -> None:
    """A world written before repeats existed has the table without them: add, never migrate."""
    have = {row[1] for row in conn.execute("PRAGMA table_info(periods)")}
    for column, kind in (("every", "TEXT"), ("lasting", "REAL")):
        if column not in have:
            conn.execute(f"ALTER TABLE periods ADD COLUMN {column} {kind}")


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
    _ready(world)
    when = _moment(at, datetime.utcnow())
    moment = _stamp(when)
    rows = world.store.conn.execute(
        "SELECT value FROM periods WHERE subject = ? AND nature = ? AND every IS NULL "
        "AND (starts IS NULL OR starts <= ?) AND (until IS NULL OR until > ?)",
        (subject, nature, moment, moment)).fetchall()
    found = [value for (value,) in rows if value is not None]
    for row in _repeating(world, "subject = ? AND nature = ?", [subject, nature]):
        if row["value"] is not None and _covers(row, when) and row["value"] not in found:
            found.append(row["value"])
    return found


def carrying(world, nature: str, value: str, at: datetime | None = None) -> list[str]:
    """Which subjects held this value at a moment — the question asked from the other end."""
    _ready(world)
    when = _moment(at, datetime.utcnow())
    moment = _stamp(when)
    rows = world.store.conn.execute(
        "SELECT DISTINCT subject FROM periods WHERE nature = ? AND value = ? AND every IS NULL "
        "AND (starts IS NULL OR starts <= ?) AND (until IS NULL OR until > ?)",
        (nature, value, moment, moment)).fetchall()
    found = [subject for (subject,) in rows]
    for row in _repeating(world, "nature = ? AND value = ?", [nature, value]):
        if _covers(row, when) and row["subject"] not in found:
            found.append(row["subject"])
    return found


def stretches(world, subject: str, nature: str, value: str | None = None,
              since: datetime | None = None, until: datetime | None = None) -> list[tuple]:
    """Every stretch, coalesced, in order — (value, from, to).

    A cyclic row is the one thing here that has to be asked about within a window: `since`/`until`
    say how far to count its occurrences out. Without a window it stays one row, as it is stored —
    the rule itself, not its instances.
    """
    _ready(world)
    where = "subject = ? AND nature = ?" + (" AND value = ?" if value is not None else "")
    args = [subject, nature] + ([value] if value is not None else [])
    rows = world.store.conn.execute(
        f"SELECT value, starts, until, every, lasting FROM periods WHERE {where} "
        f"ORDER BY starts", args).fetchall()
    out = []
    for held, starts, ends, every, lasting in rows:
        if not every:
            out.append((held, _parse(starts), _parse(ends)))
        elif since is None or until is None:  # no window asked about: the rule itself, one row
            out.append((held, _parse(starts), _parse(ends)))
        else:
            from terraweaver import recurrence

            for one_start, one_end in recurrence.occurrences(
                    _parse(starts), every, _moment(since), _moment(until), lasting, _parse(ends)):
                out.append((held, one_start, one_end))
    return sorted(out, key=lambda row: (row[1] or datetime.min, row[2] or datetime.max))


def next_time(world, subject: str, nature: str, value: str | None = None,
              after: datetime | None = None) -> datetime | None:
    """When the next occurrence of a cyclic row is — the question a repeat exists to answer."""
    from terraweaver import recurrence

    _ready(world)
    where = "subject = ? AND nature = ?" + (" AND value = ?" if value is not None else "")
    args = [subject, nature] + ([value] if value is not None else [])
    moment = _moment(after, datetime.utcnow())
    coming = []
    for row in _repeating(world, where, args):
        when = recurrence.next_after(row["starts"], row["every"], moment, row["until"])
        if when is not None:
            coming.append(when)
    return min(coming) if coming else None


def happening(world, since=None, until=None, limit: int = 200) -> list[tuple]:
    """What falls in a window, one-offs and repeats together — (when, entity, what it is).

    The question a diary is for, and the one thing a date query on an attribute cannot answer:
    a weekly standup has one `start_time`, the day it started, so "what is on after New Year"
    finds nothing however many times it will happen by then. Here the rules are counted out
    into the window asked about and sorted in with everything else.
    """
    from terraweaver import recurrence, timeutil

    start = _moment(since, timeutil.now())
    stop = _moment(until, start + timedelta(days=90))
    out = []
    named = {}
    for class_name, cls in getattr(world, "classes", {}).items():
        dated = [a["name"] for a in cls._spec["attributes"]
                 if a.get("type") == "datetime" and "derived" not in a
                 and a["name"] not in ("created_at", "accessed_at", "valid_from", "valid_until")]
        if not dated:
            continue
        for entity in world.all(class_name, limit=None, any_time=True):
            named[getattr(entity, "subject_id", None) or entity.id] = entity
            for slot in dated[:1]:  # the first dated attribute is the thing's own time
                when = getattr(entity, slot, None)
                if isinstance(when, datetime) and start <= when <= stop:
                    out.append((when, entity, entity.display_name()))
    for rule in cycles(world):
        entity = named.get(rule["subject"])
        if entity is None:
            continue
        for begins, _ in recurrence.occurrences(rule["starts"], rule["every"], start, stop,
                                                rule["lasting"], rule["until"]):
            what = f"{entity.display_name()} — {rule['value']}" if rule["value"] else entity.display_name()
            if not any(when == begins and other is entity for when, other, _ in out):
                out.append((begins, entity, what))
    return sorted(out, key=lambda row: row[0])[:limit]


def cycles(world, subject: str | None = None) -> list[dict]:
    """The cyclic rows: what repeats, how often, and for how long each time."""
    where, args = ("subject = ?", [subject]) if subject else ("1 = 1", [])
    return _repeating(world, where, args)


def _moment(value, default=None) -> datetime | None:
    """A date and a datetime are the same question asked twice; the table answers in one."""
    from terraweaver import timeutil

    if value is None:
        return default
    return timeutil.as_datetime(value)


def _ready(world) -> None:
    conn = world.store.conn
    kinds = {r[1]: (r[2] or "").upper() for r in conn.execute("PRAGMA table_info(periods)")}
    if kinds and kinds.get("starts") != "INTEGER":
        # Derived, so there is nothing to migrate: throw it away and let it be built again in
        # the shape that orders correctly.
        conn.execute("DROP TABLE periods")
        conn.commit()
        rebuild(world)
        return
    run_script(conn, SCHEMA)
    _add_missing_columns(conn)


def _repeating(world, where: str, args: list) -> list[dict]:
    """The cyclic rows matching a condition, read as dicts rather than as five positions."""
    rows = world.store.conn.execute(
        f"SELECT subject, nature, value, starts, until, every, lasting FROM periods "
        f"WHERE {where} AND every IS NOT NULL", args).fetchall()
    return [{"subject": subject, "nature": nature, "value": value, "starts": _parse(starts),
             "until": _parse(ends), "every": every, "lasting": lasting}
            for subject, nature, value, starts, ends, every, lasting in rows]


def _covers(row: dict, when: datetime) -> bool:
    from terraweaver import recurrence

    return recurrence.covers(row["starts"], row["every"], row["lasting"], when, row["until"])


def _repeat_rules(world) -> list[dict]:
    """The repeat statements, as rules. One statement, one cyclic row."""
    from terraweaver import tags as tagging

    out = []
    for statement in world.facts.with_slot(REPEATS):
        rule = statement.value
        if not isinstance(rule, dict) or not rule.get("every"):
            continue
        value = rule.get("value")
        nature = rule.get("nature") or "valid"
        out.append({"subject": statement.subject, "nature": nature,
                    "value": tagging.canonical(value) if value and nature == "tags" else value,
                    "anchor": _parse(rule.get("anchor")) or statement.valid_from or statement.stated_at,
                    "ends": _parse(rule.get("ends")) or statement.valid_until,
                    "every": rule["every"], "lasting": rule.get("lasting")})
    return out


def _from_statements(world):
    """(subject, nature, value, stretches) for everything the statements say held for a time."""
    gathered: dict = {}
    for slot in over_time(world):
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


def _parse(raw) -> datetime | None:
    from terraweaver import timeutil

    return timeutil.from_db(raw)


def _stamp(value) -> int | None:
    from terraweaver import timeutil

    return timeutil.to_db(value)
