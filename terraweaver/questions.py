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
    closed_as TEXT,              -- answered | settled_itself | dropped
    put_to_user_at TEXT          -- when an agent handed it on, being unable to settle it itself
);
CREATE INDEX IF NOT EXISTS idx_questions_entity ON questions(entity_id, closed_at);
"""

_COLUMNS = ("id, entity_id, kind, text, options, involves, touches, raised_at, raised_by, "
            "answer, answered_by, closed_as, put_to_user_at")


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
    put_to_user_at: str | None = None
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
        if self.kind.startswith("nature_of_"):
            untouched = self._type_still_as_assumed(said)
            if untouched:
                raise ValueError(untouched)
        self._book.close(self, "answered", said, by)
        self.answer_text, self.answered_by, self.closed_as = said, by, "answered"

    def _type_still_as_assumed(self, said: str = "") -> str | None:
        """For a question about a type the world invented: has the type actually been amended?

        An answer in words settles nothing on its own. A recorder wrote "one spouse at a time,
        can change" and moved on, and the type still said several could hold at once — so the
        world read a second marriage as one standing beside the first. The prose was right and
        the world was unchanged, and nothing connected the two. So the answer is not accepted
        until the type says what the answer says.
        """
        from terraweaver import ontology

        kind = self.kind[len("nature_of_"):]
        world = ontology.current_world()   # raises when nothing is bound; never None
        for cls in world.classes.values():
            rel = (getattr(cls, "_spec", {}) or {}).get("relation") or {}
            if rel.get("kind") != kind:
                continue
            assumed = not rel.get("said_by_hand")
            if not assumed:
                return None
            read = _reads_as(kind, said)
            lines = "\n".join(f"    {line}" for line in read["lines"])
            return (
                f"I have your words and they are kept — but {cls.__name__} still holds what I "
                f"guessed, and words do not change a type. {read['because']}\n{lines}\n"
                f"Run that, then answer again. If I read you wrong, write what is actually true "
                f"instead — any of these settles it, and setting one to what it already is says "
                f"my guess was right:\n"
                f"    {kind}.nature = \"related_to\"    # or part_of / kind_of / same_as / derived_from\n"
                f"    {kind}.one_per_subject = True   # one at a time, a new one ends the last\n"
                f"    {kind}.one_per_subject = False  # several can hold at once"
            )
        return None

    def for_the_user(self, why: str = "") -> None:
        """You cannot settle this one — hand it on, and say why.

        The honest third answer. An agent sent to record facts often genuinely cannot know
        whether two people with one name are one person; guessing puts a fabrication in under
        the user's name, and dropping it pretends the doubt was never real. This keeps the
        question open for whoever can answer it, and stops it standing in the way of finishing
        the task — but only because you said so, in writing.
        """
        stamp = datetime.now(timezone.utc).isoformat()
        self._book.store.conn.execute(
            "UPDATE questions SET put_to_user_at = ?, answered_by = ? WHERE id = ?",
            (stamp, why.strip() or None, self.id))
        self.put_to_user_at, self.answered_by = stamp, why.strip() or None

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
        if "put_to_user_at" not in columns:
            store.conn.execute("ALTER TABLE questions ADD COLUMN put_to_user_at TEXT")
        store.conn.commit()

    # --- writing ---

    def raise_(self, entity, kind: str, text: str, options=(), involves=(), touches=(),
               by: str = "world") -> Question | None:
        """Record a doubt about `entity`. The same doubt about the same entities is only kept once."""
        if entity is None or entity.id is None:
            return None
        involved = [e.id for e in involves if getattr(e, "id", None)]
        # What makes two doubts the same. For the ones the world raises it is the kind and who is
        # involved — "two dentists at once" about these two is one doubt however it is worded. For
        # one the host noticed, the kind says only that a host noticed something, and the text is
        # the doubt: keyed without it, a second question about the same person — "which number is
        # current", then "is DataWorks its registered name" — was silently never recorded.
        same_text = " AND text = ?" if kind == "noticed" else ""
        key = (entity.id, kind, json.dumps(involved)) + ((text.strip(),) if same_text else ())
        existing = self.store.conn.execute(
            "SELECT id FROM questions WHERE entity_id = ? AND kind = ? AND involves = ? "
            "AND closed_at IS NULL" + same_text, key,
        ).fetchone()
        if existing:
            return None
        answered = self.store.conn.execute(
            "SELECT id FROM questions WHERE entity_id = ? AND kind = ? AND involves = ? "
            "AND closed_as = 'answered'" + same_text, key,
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

    def unresolved(self, here: set | None = None, limit: int = 50) -> list[Question]:
        """Open, about these entities, and nobody has said what to do with them.

        Apart from `open_` because the two answer different questions. `open_` asks what could
        usefully be put to the user; this asks what is still nobody's decision — the doubts an
        agent raised and walked past. A question handed on with `for_the_user` is still open,
        and still shown to the user, but it is no longer unresolved: somebody looked at it and
        said it was not theirs to settle.
        """
        found = [q for q in self._query("closed_at IS NULL AND put_to_user_at IS NULL", (), verify=True)
                 if here is None or q.about.id in here
                 or any(getattr(e, "id", None) in here for e in q.involves)]
        return found[:limit]

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
         answered_by, closed_as, put_to_user_at) = row
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
                        answer, answered_by, closed_as, put_to_user_at, self)

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


def _still_bare(question) -> bool:
    """Asked because a thing arrived as a bare name and nothing was known about it.

    The host answers it by saying what the thing is — `rome.describe("...")` — and that is the
    answer, not a separate `q.answer(...)`. So the moment there are words on it the question has
    no reason left and closes itself, the way a doubt about two current relations does once one
    of them ends.
    """
    return not (getattr(question.about, "descriptions", None) or [])


CHECKS = {
    "two_at_once": _both_current,
    "maybe_the_same": _still_alike,
    "what_is_it": _still_bare,
}


# What a sentence about a relation type comes to, in the type's own terms. Reading the words is
# a guess and is said to be one — but repeating the question with the line the answer already
# implies costs the agent one edit instead of a fresh reading of the manual, and an agent that
# has just explained a thing in its own words should not have to work out how to say it again.
_SAYS = (
    # One at a time is the only thing "how many" says now, and a new one always ends the last:
    # `changes` was a second switch beside it and is gone with the category it belonged to.
    (("at a time", "one at a time", "ends the last", "can change", "may change", "changes over",
      "over time", "current", "at any one time", "succeed"), "one_per_subject", "True",
     "You said it holds one at a time, which is:"),
    (("several", "many", "more than one", "multiple", "accumulate", "one or many", "any number"),
     "one_per_subject", "False", "You said several can hold at once, which is:"),
    (("part of", "a part", "belongs to"), "nature", '"part_of"',
     "You described one thing being part of another, which is:"),
    (("kind of", "a sort of", "a type of"), "nature", '"kind_of"',
     "You described one thing being a kind of another, which is:"),
    (("the same", "same thing", "same as", "an alias"), "nature", '"same_as"',
     "You described two names for one thing, which is:"),
    (("follows from", "derived", "worked out", "concluded"), "nature", '"derived_from"',
     "You described one thing following from another, which is:"),
)


def _reads_as(kind: str, said: str) -> dict:
    """The lines a prose answer about a type most likely means."""
    text = " ".join((said or "").lower().split())
    lines, because = [], []
    for words, attr, value, why in _SAYS:
        if any(w in text for w in words):
            lines.append(f"{kind}.{attr} = {value}")
            because.append(why)
    if not lines:
        return {"lines": [f'{kind}.nature = "related_to"'],
                "because": "I could not tell from that which of the three it changes. If my "
                           "guess was right as it stands, confirm it:"}
    return {"lines": lines, "because": " ".join(dict.fromkeys(because))}
