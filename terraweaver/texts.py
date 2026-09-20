"""Everything said in words, in one table, derived from the record.

Free text is scattered by nature: a description here, a tag there, a trait, a note. Each one is
a statement, so the record holds them all — but the record is a pile of statements, and the
questions people ask about text are not statement questions. "Where is Lisbon mentioned", "what
has been said about Ana", "what reads like battery chemistry" all want one list of texts, not a
walk through every class.

So the texts get their own derived tables, the same way periods do: built from the statements
by a deterministic pass, thrown away and rebuilt at will, holding nothing that isn't said
elsewhere. Two tables, because a text and the saying of it are different things:

    texts   id, text            one row per distinct text, named from the words themselves
    said    subject, slot,      who said it of what, and for how long
            text_id, starts, until, source

Storing the name rather than the words is what makes duplicates disappear: the same sentence
about two people is one row, one vector, one thing to compare — and when an image is assembled
from several subjects, their texts merge as a set rather than piling up. Saying the same thing
twice does not even get this far: `facts.state` sees an identical statement and counts it as
said again (`times`), which is the record's own rule and not a second one invented here.

Two things come out of it that were awkward before. Keyword search is one query rather than a
sweep of every entity. And a vector belongs to a text rather than to an entity, so an answer can
say which sentence matched rather than only which person — and the name survives a rebuild,
because it is made from the text.
"""
import hashlib

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS texts (
    id TEXT PRIMARY KEY,         -- made from the text itself, so the same words are one row
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS said (
    subject TEXT NOT NULL,
    slot TEXT NOT NULL,
    text_id TEXT NOT NULL,
    starts INTEGER,
    until INTEGER,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_said_subject ON said(subject, slot);
CREATE INDEX IF NOT EXISTS idx_said_text ON said(text_id);
"""


def name_of(text: str) -> str:
    """What a text is called: made from the words alone, so the same sentence said about two
    people is one text with one name — and one vector, and one row to store."""
    return "text:" + hashlib.sha1(" ".join(str(text).split()).encode()).hexdigest()[:16]


def rebuild(world) -> int:
    """Derive both tables again from every statement. Returns how many sayings there are."""
    from terraweaver import periods, timeutil

    conn = world.store.conn
    run_script(conn, SCHEMA)
    conn.execute("DELETE FROM said")
    rows = 0
    for slot in periods.over_time(world):
        for statement in world.facts.with_slot(slot):
            values = statement.value if isinstance(statement.value, list) else [statement.value]
            for one in values:
                if not isinstance(one, str) or not one.strip():
                    continue
                said = " ".join(one.split())
                text_id = name_of(said)
                conn.execute("INSERT OR IGNORE INTO texts (id, text) VALUES (?, ?)", (text_id, said))
                conn.execute(
                    "INSERT INTO said (subject, slot, text_id, starts, until, source) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (statement.subject, slot, text_id,
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
        where.append("said.subject = ?")
        args.append(subject)
    if slot:
        where.append("said.slot = ?")
        args.append(slot)
    for word in (words or "").split():
        where.append("lower(texts.text) LIKE ?")
        args.append(f"%{word.lower()}%")
    if not any_time:
        moment = timeutil.to_db(at or timeutil.now())
        where.append("(said.starts IS NULL OR said.starts <= ?) "
                     "AND (said.until IS NULL OR said.until > ?)")
        args += [moment, moment]
    rows = conn.execute(
        f"SELECT said.text_id, said.subject, said.slot, texts.text, said.starts, said.until, "
        f"said.source FROM said JOIN texts ON texts.id = said.text_id "
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
