"""Open questions: what doesn't add up, kept until someone can answer it.

A personal world is written from conversation, and conversation leaves loose ends: two current
dentists when the user meant a replacement, a second Olga recorded as new though one was already
there, a job that starts before the one it replaces ends. Refusing the write is wrong — the user
said it, and the world is not the authority on their life. Guessing is worse. So the world takes
the write, and remembers what doesn't add up.

A question is attached to the entity it's about. The next time a host works with that entity, the
result carries it: *this is open, ask the user if they're here*. The host asks, `q.answer("…")`
closes it, and the host records what the user said in the ordinary way.

Nothing here decides anything. Two things keep the list honest rather than growing forever:

- a question that has become moot closes itself. Each kind knows how to re-check its own reason
  (are those two relations still both current?), and one that no longer holds is closed as
  `settled_itself` when the list is read.
- a question the user answered stays, with the answer, so the same doubt isn't raised twice.

The host can raise one too: `entity.question("Is this still their number?")` for a contradiction
it noticed but can't resolve right now.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from terraweaver import ontology

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,     -- what the question is about
    kind TEXT NOT NULL,          -- what sort of doubt it is; the checker is chosen by this
    text TEXT NOT NULL,          -- the question in the user's terms
    options TEXT,                -- JSON list of answers that would settle it
    involves TEXT,               -- JSON list of other entity ids the doubt is about
    touches TEXT,                -- JSON list of what the doubt hangs over: relation:<kind>, attr:<name>, identity
    raised_at TEXT NOT NULL,
    raised_by TEXT NOT NULL,     -- 'world' or 'host'
    answer TEXT,                 -- what settled it, in words
    answered_by TEXT,            -- 'user', or where it came from: a rule, a source, its url
    closed_at TEXT,
    closed_as TEXT               -- answered | settled_itself | dropped
);
CREATE INDEX IF NOT EXISTS idx_questions_entity ON questions(entity_id, closed_at);
"""

_COLUMNS = ("id, entity_id, kind, text, options, involves, touches, raised_at, raised_by, "
            "answer, answered_by, closed_as")


@dataclass
class Question:
    """One thing about an entity that doesn't add up, and isn't the world's to decide."""

    id: int
    about: Any
    kind: str
    text: str
    options: list[str]
    involves: list[Any]
    touches: list[str]
    raised_at: datetime
    raised_by: str
    answer_text: str | None = None
    answered_by: str | None = None
    closed_as: str | None = None
    _book: "Questions" = field(repr=False, compare=False, default=None)

    @property
    def open(self) -> bool:
        return self.closed_as is None

    @property
    def assumption(self) -> str:
        """What the world reads while this is open. An unanswered question must never leave a
        reader with two answers and no way to choose: there is always one standing reading, it
        is the same for every host, and it is written down here (see RULES)."""
        rule = RULES.get(self.kind)
        return rule(self) if rule else "the latest thing recorded stands"

    def answer(self, said: str, by: str = "user") -> None:
        """What settles it. Closes the question; recording what follows from it is yours.

        `by` says where the answer came from — the user (the default), or a source that can be
        checked: "companies house", "https://…". A doubt about a fact the world could look up
        against an accepted norm doesn't need the user's attention; a doubt about whose life it
        is always does. What settled it is kept, so a later reader can weigh it.
        """
        self._book.close(self, "answered", said, by)
        self.answer_text, self.answered_by, self.closed_as = said, by, "answered"

    def drop(self, why: str = "") -> None:
        """It doesn't matter after all — the user isn't going to be asked this."""
        self._book.close(self, "dropped", why or None)
        self.closed_as = "dropped"

    def line(self) -> str:
        """One line for a host to read: the question, the answers, and what holds meanwhile."""
        options = f" [{' / '.join(self.options)}]" if self.options else ""
        return f"{self.about.display_name()}: {self.text}{options} — meanwhile: {self.assumption}"

    def __repr__(self):
        from terraweaver import timeutil

        state = "" if self.open else f", {self.closed_as}"
        options = f" [{' / '.join(self.options)}]" if self.options else ""
        return f"<question about {self.about.display_name()}: {self.text}{options} " \
               f"(raised {timeutil.show(self.raised_at)}{state})>"


class Questions:
    def __init__(self, store, classes: dict[str, type], usage=None):
        self.store = store
        self.classes = classes
        self.usage = usage  # how often each entity is worked with; decides what is worth asking
        store.conn.executescript(SCHEMA)
        columns = {row[1] for row in store.conn.execute("PRAGMA table_info(questions)")}
        if "touches" not in columns:  # a table made before questions knew what they hang over
            store.conn.execute("ALTER TABLE questions ADD COLUMN touches TEXT")
        if "answered_by" not in columns:
            store.conn.execute("ALTER TABLE questions ADD COLUMN answered_by TEXT")
        store.conn.commit()

    # --- writing ---

    def raise_(self, entity, kind: str, text: str, options=(), involves=(), touches=(),
               by: str = "world") -> Question | None:
        """Record a doubt about `entity`. The same doubt about the same entities is only kept once."""
        if entity is None or entity.id is None:
            return None
        involved = [e.id for e in involves if getattr(e, "id", None)]
        existing = self.store.conn.execute(
            "SELECT id FROM questions WHERE entity_id = ? AND kind = ? AND involves = ? AND closed_at IS NULL",
            (entity.id, kind, json.dumps(involved)),
        ).fetchone()
        if existing:
            return None
        answered = self.store.conn.execute(
            "SELECT id FROM questions WHERE entity_id = ? AND kind = ? AND involves = ? AND closed_as = 'answered'",
            (entity.id, kind, json.dumps(involved)),
        ).fetchone()
        if answered:  # the user already settled this one; don't ask again
            return None
        ontology.note_world_call("world_writes")
        cursor = self.store.conn.execute(
            "INSERT INTO questions (entity_id, kind, text, options, involves, touches, raised_at, raised_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (entity.id, kind, text.strip(), json.dumps(list(options)), json.dumps(involved),
             json.dumps(list(touches)), datetime.now(timezone.utc).isoformat(), by),
        )
        ontology.note_question(f"{entity.display_name()}: {text.strip()}")
        return self._load_row(self.store.conn.execute(
            f"SELECT {_COLUMNS} FROM questions WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def close(self, question: Question, how: str, said: str | None = None, by: str | None = None) -> None:
        ontology.note_world_call("world_writes")
        self.store.conn.execute(
            "UPDATE questions SET closed_at = ?, closed_as = ?, answer = ?, answered_by = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), how, said, by, question.id),
        )

    # --- reading ---

    def of(self, entity, include_closed: bool = False) -> list[Question]:
        """Open questions about this entity, oldest first. Ones that no longer hold close here."""
        if entity is None or getattr(entity, "id", None) is None:
            return []
        where = "entity_id = ?" if include_closed else "entity_id = ? AND closed_at IS NULL"
        return self._query(where, (entity.id,), verify=not include_closed)

    def open_(self, limit: int = 20, here: set | None = None) -> list[Question]:
        """Everything open, worth-asking first — what could be cleared up while the user is here.

        Worth asking is not a matter of how old the doubt is: it's how often the entity comes up.
        A doubt about the person the user asks about every week is worth a minute of their time;
        the same doubt about someone met once can wait. `here` narrows it to the entities a
        session actually worked with, which is what to offer at the end of a task.
        """
        questions = self._query("closed_at IS NULL", (), verify=True)
        if here is not None:
            questions = [q for q in questions if q.about.id in here]
        times = self.usage.counts() if self.usage else {}
        questions.sort(key=lambda q: (-times.get(q.about.id, 0), q.raised_at))
        return questions[:limit]

    def tokens(self) -> dict:
        """{entity id: {what it hangs over: the line to show}} for every open question."""
        out: dict = {}
        for question in self._query("closed_at IS NULL", (), verify=False):
            for token in question.touches:
                out.setdefault(question.about.id, {})[token] = question.line()
        return out

    def clear(self) -> None:
        self.store.conn.execute("DELETE FROM questions")

    # --- internals ---

    def _query(self, where: str, params: tuple, verify: bool) -> list[Question]:
        ontology.note_world_call("world_queries")
        rows = self.store.conn.execute(
            f"SELECT {_COLUMNS} FROM questions WHERE {where} ORDER BY id", params).fetchall()
        out = []
        for row in rows:
            question = self._load_row(row)
            if question is None:
                continue
            if verify and not self._still_stands(question):
                self.close(question, "settled_itself")
                continue
            out.append(question)
        return out

    def _load_row(self, row) -> Question | None:
        if row is None:
            return None
        (qid, entity_id, kind, text, options, involves, touches, raised_at, by, answer,
         answered_by, closed_as) = row
        try:
            about = self.store.load(entity_id, self.classes)
        except KeyError:  # the entity is gone; so is the question
            self.store.conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
            return None
        others = []
        for other_id in json.loads(involves or "[]"):
            try:
                others.append(self.store.load(other_id, self.classes))
            except KeyError:
                continue
        return Question(qid, about, kind, text, json.loads(options or "[]"), others,
                        json.loads(touches or "[]"), datetime.fromisoformat(raised_at), by,
                        answer, answered_by, closed_as, self)

    def _still_stands(self, question: Question) -> bool:
        """Whether the reason for the question is still there. A host-raised one always is —
        the world doesn't know what it was about."""
        checker = CHECKS.get(question.kind)
        return checker(question) if checker else True


def _later_of(relations: list):
    """The one that was said last: a later start wins, and failing that a later record."""
    from terraweaver import timeutil

    def key(r):
        return timeutil.as_datetime(getattr(r, "valid_from", None) or r.created_at), r.created_at

    return max(relations, key=key) if relations else None


def _latest_wins(question: Question) -> str:
    later = _later_of([r for r in question.involves if r is not None])
    if later is None:
        return "the latest thing recorded stands"
    from terraweaver import timeutil

    since = getattr(later, "valid_from", None)
    when = f" (from {timeutil.show(since)})" if since else ""
    return f"the later one counts — {later.other(question.about).display_name()}{when}"


def _stay_separate(question: Question) -> str:
    return ("they stay two records — nothing is merged without an answer; a lookup returns the one "
            "it matched, and the doubt travels with it")


# What the world reads while a question of this kind is open. One reading, the same for every
# host, chosen by a rule and not by whoever asks: recency decides, except for identity, where
# recency would silently merge two people.
RULES = {
    "two_at_once": _latest_wins,
    "maybe_the_same": _stay_separate,
    "noticed": lambda q: "the latest value recorded stands",
}


def _both_current(question: Question) -> bool:
    """Two relations at once: moot once one of them has been ended or removed."""
    from terraweaver.relations import _overlaps

    if len(question.involves) < 2:
        return False
    a, b = question.involves[0], question.involves[1]
    return _overlaps(a, getattr(b, "valid_from", None) or b.created_at, getattr(b, "valid_until", None))


def _still_alike(question: Question) -> bool:
    """Recorded as new next to one it resembles: moot once one of them is gone."""
    return len(question.involves) >= 1 and question.about.id is not None


CHECKS = {
    "two_at_once": _both_current,
    "maybe_the_same": _still_alike,
}
