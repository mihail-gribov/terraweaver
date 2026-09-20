"""What was said, and what the world worked out. Append-only, and nothing in it is ever changed.

This is the lower of the two layers. Every statement the world receives lands here — from the
user, from the assistant's own conclusion, from a source on the internet — and stays. A
correction is not an edit: it is a later statement, and a retraction is a statement about a
statement. Nothing is overwritten, so nothing can be lost by being wrong.

One table per class per structure, named after both, so the database reads like the architecture:

    facts_Person        what was said about people
    reasoning_Person    what the world worked out about them, and what from
    Person              the images built out of those — the main data, loaded by the class

The first two have the same columns; a row in `reasoning_` is a conclusion and carries its
basis. So "forget everything you worked out about me" is one operation over one group of tables,
and "what was I actually told" needs no filter at all. `subjects` says which class a subject
belongs to, so a statement can be found without knowing where to look.

    subject      whom it is about        7db1463e…
    slot         what about them         full_name | email | kin:mother | same_as
    value        the value, or a reference to another subject
    valid_from   when it holds from      2026-08-01
    valid_until  when it stops holding   null
    stated_at    when we were first told this          2026-09-20 10:14
    restated_at when it was last said again, and `times` how often — the same thing said twice
                 is one statement that has been heard twice, not two statements
    source       where it came from      agent (through the assistant) | a named source |
                                         world (what this world worked out for itself)
    run_id       in which run — and, once work is organised into tickets, which ticket
    basis        what a conclusion was drawn from, with a digest: move the basis and the
                 conclusion is stale
    retracted_by what took it back

Conclusions are never drawn from conclusions: a world that reasons from its own guesses will
believe anything by the end of the month.

The upper layer (assembly.py) reads all of this and builds the entities — by rules that can
change without touching anything here. That is the point: change the rule, or learn one more
fact, and rebuild. Two people who looked like one come apart again, and what was said about each
of them is exactly where it was.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SAID, WORKED_OUT = "facts", "reasoning"

SUBJECTS = """
CREATE TABLE IF NOT EXISTS subjects (
    subject TEXT PRIMARY KEY,
    class_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_subjects_class ON subjects(class_name);
"""

TABLE = """
CREATE TABLE IF NOT EXISTS {table} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    slot TEXT NOT NULL,
    value TEXT,
    valid_from INTEGER,
    valid_until INTEGER,
    stated_at INTEGER NOT NULL,
    restated_at INTEGER,
    times INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    run_id TEXT,
    basis TEXT,
    basis_digest TEXT,
    retracted_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_{table}_subject ON {table}(subject, slot);
"""

COLUMNS = ("id, subject, slot, value, valid_from, valid_until, stated_at, restated_at, times, "
           "source, run_id, basis, basis_digest")

# Where a statement came from, and which wins when two cover the same slot at the same time.
#
# There are three, and only three. Everything that arrives through the assistant — the user's own
# words, and whatever the assistant concluded from them — is one source: `agent`. The world
# cannot tell those apart and does not try; what the assistant passes on is the assistant's
# responsibility. A named source is a file, a register, a site: checkable, and outranked by the
# person's own account of their life. `world` is what this world worked out for itself, the
# weakest thing here, and it lives in the `reasoning_` tables rather than the `facts_` ones.
TOLD, WORKED = "agent", "world"
TRUST = {TOLD: 3, WORKED: 1}
SOURCE_TRUST = 2  # anything else is a named source: a site, a register, a document


def trust(source: str) -> int:
    return TRUST.get(source, SOURCE_TRUST)


@dataclass(frozen=True)
class Statement:
    id: str              # "facts_Person:17" — which table it is in, and which row
    subject: str
    slot: str
    value: Any
    valid_from: datetime | None
    valid_until: datetime | None
    stated_at: datetime
    restated_at: datetime | None
    times: int
    source: str
    run_id: str | None
    basis: list | None = None
    basis_digest: str | None = None

    @property
    def last_said(self) -> datetime:
        """When this was last heard — what "the later one" means when two statements disagree."""
        return self.restated_at or self.stated_at

    @property
    def is_conclusion(self) -> bool:
        return self.basis is not None

    @property
    def is_reference(self) -> bool:
        return isinstance(self.value, dict) and "$subject" in self.value

    @property
    def refers_to(self) -> str | None:
        return self.value.get("$subject") if self.is_reference else None

    def holds_at(self, moment: datetime) -> bool:
        if self.valid_from is not None and self.valid_from > moment:
            return False
        return self.valid_until is None or self.valid_until > moment

    def __repr__(self):
        shown = self.value.get("$subject") if self.is_reference else self.value
        return f"<{self.subject} {self.slot}={shown!r} ({self.source})>"


def reference(subject: str) -> dict:
    return {"$subject": subject}


class Facts:
    def __init__(self, conn):
        self.conn = conn
        _run(conn, SUBJECTS)
        conn.commit()
        # A world written before time became a number is brought over on the way in, once. Two
        # spellings of a moment in one record is the bug this exists to make impossible.
        migrate_times(conn)

    # --- where a statement lives ---

    def table(self, class_name: str, structure: str = SAID) -> str:
        """`facts_Person`, `reasoning_Person`, made the first time something is written there."""
        name = f"{structure}_{class_name}"
        # Made every time, because both shortcuts are wrong. `executescript` would commit
        # whatever transaction is open — a table made mid-run would commit the run itself. And a
        # cache of "already made" outlives a rollback that unmade them. IF NOT EXISTS is cheap.
        _run(self.conn, TABLE.format(table=name))
        return name

    def tables(self, structure: str | None = None) -> list[str]:
        """Every statement table that exists, for reads that span classes."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND "
            "(name LIKE 'facts_%' OR name LIKE 'reasoning_%') ORDER BY name").fetchall()
        return [n for (n,) in rows if structure is None or n.startswith(f"{structure}_")]

    def _class(self, subject: str, class_name: str | None) -> str:
        known = self.class_of(subject)
        chosen = known or class_name or "Unknown"
        if not known:
            self.register(subject, chosen)  # so a statement can be found without a search
        return chosen

    def register(self, subject: str, class_name: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO subjects (subject, class_name) VALUES (?, ?)",
                          (subject, class_name))

    def class_of(self, subject: str) -> str | None:
        row = self.conn.execute("SELECT class_name FROM subjects WHERE subject = ?",
                                (subject,)).fetchone()
        return row[0] if row else None

    # --- writing ---

    def state(self, subject: str, slot: str, value, *, source: str = TOLD, valid_from=None,
              valid_until=None, run_id: str | None = None, stated_at=None,
              class_name: str | None = None) -> str:
        """Record that someone said this. Never replaces an earlier statement — it joins it.

        The same thing said again is not a second statement. A world is told the same fact over
        and over — a file re-read, an entity re-saved, a person repeating themselves — and if
        each telling were a row the record would be mostly its own echo. So a repetition moves
        the moment it was last heard and counts one more telling. `stated_at` still says when it
        was first said, which is the thing you actually want to know.
        """
        table = self.table(self._class(subject, class_name), SAID)
        when = _iso(stated_at) or _now()
        again = self.conn.execute(
            f"SELECT id, times FROM {table} WHERE subject = ? AND slot = ? AND value IS ? "
            f"AND source = ? AND valid_from IS ? AND valid_until IS ? AND retracted_by IS NULL",
            (subject, slot, json.dumps(value), source, _iso(valid_from), _iso(valid_until)),
        ).fetchone()
        if again:
            row_id, times = again
            self.conn.execute(f"UPDATE {table} SET restated_at = ?, times = ? WHERE id = ?",
                              (when, times + 1, row_id))
            return f"{table}:{row_id}"
        return self._insert(table, subject, slot, value, valid_from, valid_until, when, source,
                            run_id, None)

    def conclude(self, subject: str, slot: str, value, *, basis: list, run_id: str | None = None,
                 valid_from=None, valid_until=None, class_name: str | None = None) -> str:
        """What the world worked out for itself, and what from.

        Expensive by nature — many statements, a model, sometimes a search — so it is kept rather
        than recomputed on every read. When the basis moves, `stale()` says so and the work is
        due again."""
        guesses = [s for s in basis if getattr(s, "is_conclusion", False)]
        if guesses:
            raise ValueError("a conclusion is drawn from what was said, not from other conclusions "
                             f"({guesses[0].slot!r} is one) — otherwise the world ends up "
                             f"believing its own guesses")
        ids = sorted(s.id if isinstance(s, Statement) else str(s) for s in basis)
        return self._insert(self.table(self._class(subject, class_name), WORKED_OUT), subject,
                            slot, value, valid_from, valid_until, _now(), WORKED, run_id, ids)

    def end(self, statement_id: str, at=None) -> None:
        """Say when this stopped holding. Not a retraction: it was true, and then it wasn't.

        A tag that held from March to September, a job that ended, a rule that applied for a
        quarter — the difference between "this was never so" and "this stopped being so" is the
        whole of history, and only the second one can be asked about later."""
        table, row = _split(statement_id)
        self.conn.execute(f"UPDATE {table} SET valid_until = ? WHERE id = ? AND valid_until IS NULL",
                          (_iso(at) or _now(), row))

    def retract(self, statement_id: str, by: str | None = None) -> None:
        """Take a statement back — it was wrong, or the run that made it was undone. It stays in
        the table: what was said is part of the record even when it is no longer believed."""
        table, row = _split(statement_id)
        self.conn.execute(f"UPDATE {table} SET retracted_by = ? WHERE id = ?",
                          (by or "retracted", row))

    def retract_run(self, run_id: str) -> int:
        """Undo a whole run — later, a whole ticket. What makes the world's own work reversible
        without keeping a journal beside it."""
        undone = 0
        for table in self.tables():
            cursor = self.conn.execute(
                f"UPDATE {table} SET retracted_by = 'run undone' WHERE run_id = ? "
                f"AND retracted_by IS NULL", (run_id,))
            undone += cursor.rowcount
        return undone

    def forget_reasoning(self, subject: str | None = None) -> int:
        """Take back everything the world worked out, keeping every word it was told.

        The way out of a tangle: an agent that has reasoned itself somewhere strange drops its
        own conclusions and is back to exactly what it was given."""
        undone = 0
        for table in self.tables(WORKED_OUT):
            where = "retracted_by IS NULL" + (" AND subject = ?" if subject else "")
            cursor = self.conn.execute(
                f"UPDATE {table} SET retracted_by = 'forgotten' WHERE {where}",
                (subject,) if subject else ())
            undone += cursor.rowcount
        return undone

    # --- reading ---

    def about(self, subject: str, slot: str | None = None,
              include_retracted: bool = False) -> list[Statement]:
        where = "subject = ?" + ("" if slot is None else " AND slot = ?")
        args = [subject] + ([] if slot is None else [slot])
        class_name = self.class_of(subject)
        tables = ([f"{SAID}_{class_name}", f"{WORKED_OUT}_{class_name}"] if class_name
                  else self.tables())
        return self._query(where, args, tables, include_retracted)

    def with_slot(self, slot: str) -> list[Statement]:
        return self._query("slot = ?", [slot], self.tables(), False)

    def subjects(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT subject FROM subjects ORDER BY subject")]

    def all(self, include_retracted: bool = False) -> list[Statement]:
        return self._query("1 = 1", [], self.tables(), include_retracted)

    def stale(self, statement: Statement) -> bool:
        """Whether what this conclusion was drawn from still looks the way it did. Mechanical on
        purpose: a conclusion goes stale because its basis moved, not because anyone judged it
        wrong. What replaces it is work for the agenda."""
        if not statement.is_conclusion:
            return False
        live = {s.id for s in self.about(statement.subject)}
        return _digest(sorted(i for i in statement.basis if i in live)) != statement.basis_digest

    def basis_of(self, statement: Statement) -> list[Statement]:
        """The statements a conclusion was drawn from — "why do you think that", answerable."""
        if not statement.is_conclusion or not statement.basis:
            return []
        wanted = set(statement.basis)
        return [s for s in self.about(statement.subject, include_retracted=True) if s.id in wanted]

    def why(self, subject: str, slot: str) -> tuple[Statement, list[Statement]] | None:
        """The judgement standing on this slot and what it rests on, or None if nobody worked it
        out. The world hands this over; explaining it is the host's job, because an explanation
        is a sentence to a person and the world doesn't talk to people.

        Later, when work is organised into tickets, `run_id` names the ticket that ordered it,
        and the answer can include what the world was trying to work out."""
        judgements = [s for s in self.about(subject, slot) if s.is_conclusion]
        if not judgements:
            return None
        return judgements[-1], self.basis_of(judgements[-1])

    # --- internals ---

    def _insert(self, table: str, subject: str, slot: str, value, valid_from, valid_until,
                stated_at: str, source: str, run_id: str | None, basis: list | None) -> str:
        cursor = self.conn.execute(
            f"INSERT INTO {table} (subject, slot, value, valid_from, valid_until, stated_at, "
            f"source, run_id, basis, basis_digest) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (subject, slot, json.dumps(value), _iso(valid_from), _iso(valid_until), stated_at,
             source, run_id, json.dumps(basis) if basis is not None else None,
             _digest(basis) if basis is not None else None),
        )
        return f"{table}:{cursor.lastrowid}"

    def _query(self, where: str, args: list, tables: list[str],
               include_retracted: bool) -> list[Statement]:
        out = []
        existing = set(self.tables())
        for table in tables:
            if table not in existing:
                continue
            clause = where if include_retracted else f"({where}) AND retracted_by IS NULL"
            rows = self.conn.execute(
                f"SELECT {COLUMNS} FROM {table} WHERE {clause} ORDER BY id", args).fetchall()
            out += [_statement(table, row) for row in rows]
        return sorted(out, key=lambda s: (s.last_said, s.id))


def _run(conn, script: str) -> None:
    from terraweaver.store import run_script

    run_script(conn, script)


def _statement(table: str, row) -> Statement:
    (row_id, subject, slot, value, valid_from, valid_until, stated_at, restated_at, times,
     source, run_id, basis, digest) = row
    return Statement(f"{table}:{row_id}", subject, slot,
                     json.loads(value) if value is not None else None,
                     _parse(valid_from), _parse(valid_until), _parse(stated_at),
                     _parse(restated_at), times, source, run_id,
                     json.loads(basis) if basis else None, digest)


def _split(statement_id: str) -> tuple[str, int]:
    table, _, row = statement_id.rpartition(":")
    return table, int(row)


def _digest(ids: list) -> str:
    return hashlib.sha256(",".join(str(i) for i in ids).encode()).hexdigest()[:16]


def _now() -> int:
    from terraweaver import timeutil

    return timeutil.to_db(timeutil.now())


def _iso(value) -> int | None:
    """A moment as the record keeps it: microseconds since the epoch (timeutil.to_db)."""
    from terraweaver import timeutil

    return timeutil.to_db(value)


def _parse(raw) -> datetime | None:
    from terraweaver import timeutil

    return timeutil.from_db(raw)


def migrate_times(conn) -> list[str]:
    """Bring statement tables written in text over to numbers. Returns the tables it rewrote.

    A record is not something to rewrite lightly, and this rewrites nothing about it: the same
    moments, said in the one way the database can order. Done here, once, rather than by reading
    both forms forever — two spellings of a moment is exactly the thing that went wrong."""
    from terraweaver import timeutil

    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND "
                        "(name LIKE 'facts_%' OR name LIKE 'reasoning_%')").fetchall()
    moved = []
    for (table,) in rows:
        kinds = {r[1]: (r[2] or "").upper() for r in conn.execute(f"PRAGMA table_info({table})")}
        if kinds.get("stated_at") == "INTEGER":
            continue
        from terraweaver.store import run_script

        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_intext")
        run_script(conn, TABLE.format(table=table))
        columns = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        times = ("valid_from", "valid_until", "stated_at", "restated_at")
        old_rows = conn.execute(f"SELECT {', '.join(columns)} FROM {table}_intext").fetchall()
        for row in old_rows:
            values = dict(zip(columns, row))
            for column in times:
                values[column] = timeutil.to_db(timeutil.from_db(values.get(column)))
            conn.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES "
                         f"({', '.join('?' * len(columns))})", [values[c] for c in columns])
        conn.execute(f"DROP TABLE {table}_intext")
        moved.append(table)
    if moved:
        conn.commit()
    return moved
