"""Everything said in words, in one table, derived from the record.

Free text is scattered by nature: a description here, a tag there, a trait, a note. Each one is
a statement, so the record holds them all — but the record is a pile of statements, and the
questions people ask about text are not statement questions. "Where is Lisbon mentioned", "what
has been said about Ana", "what reads like battery chemistry" all want one list of texts, not a
walk through every class.

So the texts get their own derived table, the same way periods do: built from the statements by
a deterministic pass, thrown away and rebuilt at will, holding nothing that isn't said elsewhere.

    ref       stable name of this text — subject, slot and the text itself
    subject   whom it is about
    slot      which list it belongs to: descriptions, tags, character
    text      as it was said
    starts    from                    (null: since it was said)
    until     to                      (null: still holding)
    source    who said it: the agent, a named source, or the world itself

Two things come out of it that were awkward before. Keyword search is one query rather than a
sweep of every entity. And a vector belongs to a text rather than to an entity — `ref` is stable
across rebuilds, because it is made from the text, so the index survives and an answer can say
which sentence matched rather than only which person.
"""
import hashlib

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS texts (
    ref TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    slot TEXT NOT NULL,
    text TEXT NOT NULL,
    starts INTEGER,
    until INTEGER,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_texts_subject ON texts(subject, slot);
"""


def name_of(subject: str, slot: str, text: str) -> str:
    """What this text is called, made from the text: the same text keeps the same name."""
    return "text:" + hashlib.sha1(f"{subject}|{slot}|{text}".encode()).hexdigest()[:16]


def rebuild(world) -> int:
    """Derive the table again from every statement. Returns how many texts it holds."""
    from terraweaver import periods, timeutil

    conn = world.store.conn
    run_script(conn, SCHEMA)
    conn.execute("DELETE FROM texts")
    rows = 0
    for slot in periods.over_time(world):
        for statement in world.facts.with_slot(slot):
            values = statement.value if isinstance(statement.value, list) else [statement.value]
            for one in values:
                if not isinstance(one, str) or not one.strip():
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO texts (ref, subject, slot, text, starts, until, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (name_of(statement.subject, slot, one), statement.subject, slot, one,
                     timeutil.to_db(statement.valid_from or statement.stated_at),
                     timeutil.to_db(statement.valid_until), statement.source))
                rows += 1
    conn.commit()
    return rows


def holding(world, subject: str, slot: str | None = None, at=None) -> list[str]:
    """The texts that hold for this one at a moment."""
    return [row["text"] for row in search(world, subject=subject, slot=slot, at=at)]


def search(world, words: str | None = None, *, subject: str | None = None, slot: str | None = None,
           at=None, any_time: bool = False, limit: int = 200) -> list[dict]:
    """Texts matching every word given — the plain, literal search, with no model in it.

    Words, not a phrase: "lisbon flat" finds a text with both, in any order. Case doesn't matter
    and nothing is stemmed — this is the search that is exactly predictable, and `like=` in
    world.where() is the one that isn't.
    """
    from terraweaver import timeutil

    rebuild(world)  # derived, and cheap: always exactly what the statements say
    conn = world.store.conn
    where, args = ["1 = 1"], []
    if subject:
        where.append("subject = ?")
        args.append(subject)
    if slot:
        where.append("slot = ?")
        args.append(slot)
    for word in (words or "").split():
        where.append("lower(text) LIKE ?")
        args.append(f"%{word.lower()}%")
    if not any_time:
        moment = timeutil.to_db(at or timeutil.now())
        where.append("(starts IS NULL OR starts <= ?) AND (until IS NULL OR until > ?)")
        args += [moment, moment]
    rows = conn.execute(
        f"SELECT ref, subject, slot, text, starts, until, source FROM texts "
        f"WHERE {' AND '.join(where)} LIMIT ?", args + [limit]).fetchall()
    return [{"ref": ref, "subject": subject_id, "slot": slot_name, "text": text,
             "starts": timeutil.from_db(starts), "until": timeutil.from_db(until), "source": source}
            for ref, subject_id, slot_name, text, starts, until, source in rows]


def mentioning(world, words: str, *, at=None, any_time: bool = False) -> set[str]:
    """Whose texts mention all of these words — the subjects, for narrowing by."""
    return {row["subject"] for row in search(world, words, at=at, any_time=any_time, limit=5000)}


def about(world, entity, at=None) -> list[dict]:
    """Everything said about this one, in words, whatever slot it went into."""
    return search(world, subject=getattr(entity, "subject_id", None) or entity.id, at=at)
