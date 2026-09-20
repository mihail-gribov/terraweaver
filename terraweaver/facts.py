"""What was said. One table, append-only, and nothing in it is ever changed.

This is the lower of the two layers. Every statement the world ever receives lands here — from
the user, from the assistant's own conclusion, from a source on the internet — and stays. A
correction is not an edit: it is a later statement, and a retraction is a statement about a
statement. Nothing is overwritten, so nothing can be lost by being wrong.

    subject      whom it is about        p:0d1f…            (a subject, not yet a person: who is
                                                             who is decided when images are built)
    slot         what about them         full_name | email | kin:mother | same_as
    value        the value, or a subject
    valid_from   when it holds from      2026-08-01
    valid_until  when it stops holding   null
    stated_at    when we were told       2026-09-20 10:14
    source       whose word it is        user | agent | companies-house.gov.uk
    run_id       in which run
    basis        what it was drawn from  [12, 48, 51]  — only for what the world concluded
    basis_digest the shape of that basis, so a conclusion knows when it has gone stale
    retracted_by the statement that took it back

Most statements are *said*: someone told us. A few are *concluded*: the world read a hundred
remarks about someone and formed a judgement about their character. Those are statements too —
lowest in standing, so anything anyone actually says outranks them — but they carry what they
were drawn from, because a conclusion nobody can check is a rumour, and because when the basis
changes the conclusion has to be made again. Conclusions are never drawn from conclusions: a
world that reasons from its own guesses will believe anything by the end of the month.

The upper layer (assembly.py) reads this and builds the entities — by rules that can change
without touching anything here. That is the whole point: change the rule, or learn one more
fact, and rebuild. Two people who looked like one come apart again, and the facts about each of
them are exactly where they were.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    slot TEXT NOT NULL,
    value TEXT,                  -- JSON; a reference is {"$subject": "..."}
    valid_from TEXT,
    valid_until TEXT,
    stated_at TEXT NOT NULL,
    source TEXT NOT NULL,
    run_id TEXT,
    basis TEXT,                  -- JSON list of statement ids a conclusion was drawn from
    basis_digest TEXT,           -- what that basis looked like; it changed, the conclusion is stale
    retracted_by INTEGER
);
CREATE INDEX IF NOT EXISTS idx_statements_subject ON statements(subject, slot);
CREATE INDEX IF NOT EXISTS idx_statements_slot ON statements(slot);
"""

# Whose word outranks whose, when two statements cover the same slot at the same time. The user
# is the authority on their own life; a checkable source outranks the assistant's inference on
# matters of form; the assistant's own conclusion is the weakest thing in the world.
TRUST = {"user": 3, "agent": 1}
SOURCE_TRUST = 2  # anything else is a named source: a site, a register, a document


def trust(source: str) -> int:
    return TRUST.get(source, SOURCE_TRUST)


@dataclass(frozen=True)
class Statement:
    id: int
    subject: str
    slot: str
    value: Any
    valid_from: datetime | None
    valid_until: datetime | None
    stated_at: datetime
    source: str
    run_id: str | None
    basis: list | None = None
    basis_digest: str | None = None

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
        conn.executescript(SCHEMA)
        conn.commit()

    # --- writing ---

    def state(self, subject: str, slot: str, value, *, source: str = "user", valid_from=None,
              valid_until=None, run_id: str | None = None, stated_at=None) -> int:
        """Record that someone said this. Never replaces an earlier statement — it joins it."""
        cursor = self.conn.execute(
            "INSERT INTO statements (subject, slot, value, valid_from, valid_until, stated_at, "
            "source, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (subject, slot, json.dumps(value), _iso(valid_from), _iso(valid_until),
             _iso(stated_at) or _now(), source, run_id),
        )
        return cursor.lastrowid

    def conclude(self, subject: str, slot: str, value, *, basis: list, run_id: str | None = None,
                 valid_from=None, valid_until=None) -> int:
        """What the world worked out for itself, and what from.

        Expensive by nature — many statements, a model, sometimes a search — so it is kept rather
        than recomputed on every read. `basis` is the statements it was drawn from; when they
        change, `stale()` says so and the work is due again.
        """
        conclusions = [s for s in basis if getattr(s, "is_conclusion", False)]
        if conclusions:
            raise ValueError("a conclusion is drawn from what was said, not from other conclusions "
                             f"({conclusions[0].slot!r} is one) — otherwise the world ends up "
                             f"believing its own guesses")
        ids = sorted(s.id if isinstance(s, Statement) else int(s) for s in basis)
        cursor = self.conn.execute(
            "INSERT INTO statements (subject, slot, value, valid_from, valid_until, stated_at, "
            "source, run_id, basis, basis_digest) VALUES (?, ?, ?, ?, ?, ?, 'agent', ?, ?, ?)",
            (subject, slot, json.dumps(value), _iso(valid_from), _iso(valid_until), _now(),
             run_id, json.dumps(ids), _digest(ids)),
        )
        return cursor.lastrowid

    def stale(self, statement: Statement) -> bool:
        """Whether what this conclusion was drawn from still looks the way it did.

        Mechanical on purpose: a conclusion goes stale because its basis moved, not because
        anyone judged it wrong. What replaces it is work for the agenda."""
        if not statement.is_conclusion:
            return False
        live = [s.id for s in self.about(statement.subject)]
        kept = sorted(i for i in statement.basis if i in live)
        return _digest(kept) != statement.basis_digest

    def basis_of(self, statement: Statement) -> list[Statement]:
        """The statements a conclusion was drawn from — "why do you think that", answerable."""
        if not statement.is_conclusion or not statement.basis:
            return []
        marks = ",".join("?" * len(statement.basis))
        return self._query(f"id IN ({marks})", list(statement.basis))

    def retract(self, statement_id: int, by: int | None = None) -> None:
        """Take a statement back — it was wrong, or the run that made it was undone. It stays in
        the table: what was said is part of the record even when it is no longer believed."""
        self.conn.execute("UPDATE statements SET retracted_by = ? WHERE id = ?",
                          (by if by is not None else -1, statement_id))

    def retract_run(self, run_id: str) -> int:
        """Undo a whole run. This is what makes a run reversible without a separate journal."""
        cursor = self.conn.execute(
            "UPDATE statements SET retracted_by = -1 WHERE run_id = ? AND retracted_by IS NULL",
            (run_id,))
        return cursor.rowcount

    # --- reading ---

    def about(self, subject: str, slot: str | None = None, include_retracted: bool = False) -> list[Statement]:
        where = "subject = ?"
        args: list = [subject]
        if slot is not None:
            where += " AND slot = ?"
            args.append(slot)
        if not include_retracted:
            where += " AND retracted_by IS NULL"
        return self._query(where, args)

    def with_slot(self, slot: str) -> list[Statement]:
        return self._query("slot = ? AND retracted_by IS NULL", [slot])

    def subjects(self) -> list[str]:
        return [row[0] for row in self.conn.execute(
            "SELECT DISTINCT subject FROM statements WHERE retracted_by IS NULL ORDER BY subject")]

    def all(self) -> list[Statement]:
        return self._query("retracted_by IS NULL", [])

    def _query(self, where: str, args: list) -> list[Statement]:
        rows = self.conn.execute(
            f"SELECT id, subject, slot, value, valid_from, valid_until, stated_at, source, run_id, "
            f"basis, basis_digest FROM statements WHERE {where} ORDER BY id", args).fetchall()
        return [Statement(i, subject, slot, json.loads(value) if value is not None else None,
                          _parse(vf), _parse(vu), _parse(at), source, run,
                          json.loads(basis) if basis else None, digest)
                for i, subject, slot, value, vf, vu, at, source, run, basis, digest in rows]


def _digest(ids: list) -> str:
    return hashlib.sha256(",".join(str(i) for i in ids).encode()).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return datetime(value.year, value.month, value.day).isoformat()


def _parse(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None
