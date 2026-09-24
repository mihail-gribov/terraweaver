"""What a thing is, said in words, and read afterwards.

The twin of `sentences.py`, for one thing instead of two, and built on the same division. A host
that must choose a class before it can name a city chooses badly, for the same reason it chose
relation types badly: the choice comes before it has anything to choose with. So it names the
thing, the world records it as a bare `Thing`, and the host says what it is in the words it has:

    rome = world.identify(Thing, name="Rome")[0]     # nobody here of that name — recorded
    rome.describe("Rome is the capital of Italy, where the user lived until 2019")

What class that is, which attributes it fills, whether a class for it has to be made at all —
read afterwards, at the close of the task, by a reader whose whole attention is that question.

**Which thing it is, is never read.** The entity is handed over as an entity and its id is what
the reading is written against. A reader that had to find "Rome" in its own answer could name
something that is not in the record at all, and identity recovered from words is the one mistake
no later pass repairs. The reader says what this is; it never says which this is.

**Whether it is true is not the reader's business.** A world that holds "London is the capital of
France" describes it exactly as it would the truth. This is a record of what somebody said.
"""
import json
from datetime import datetime, timezone

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS portraits (
    entity_id TEXT PRIMARY KEY,
    asked_at TEXT NOT NULL,
    task_id TEXT,
    read_as TEXT,              -- JSON of what a reader made of it, once it has been read
    became TEXT                -- the class it turned out to be, if it turned out to be one
);
CREATE INDEX IF NOT EXISTS idx_portraits_unread ON portraits(read_as);
"""


def wanted(world, entity, task_id: str | None = None) -> None:
    """Note that this thing arrived as a bare name, so the close knows to read it.

    Called where the name was recorded, not where it is read. Nothing waits on this: the thing
    is in the world from that moment, findable and linkable, and knowing what it is is an
    improvement on something that is already there.
    """
    run_script(world.store.conn, SCHEMA)
    world.store.conn.execute(
        "INSERT OR IGNORE INTO portraits (entity_id, asked_at, task_id) VALUES (?, ?, ?)",
        (entity.id, datetime.now(timezone.utc).isoformat(), task_id))
    world.store.conn.commit()


def unread(world, limit: int = 50) -> list[dict]:
    run_script(world.store.conn, SCHEMA)
    rows = world.store.conn.execute(
        "SELECT entity_id FROM portraits WHERE read_as IS NULL ORDER BY asked_at LIMIT ?",
        (limit,)).fetchall()
    return [{"entity_id": r[0]} for r in rows]


def mark(world, entity_id: str, read_as: dict, became: str | None = None) -> None:
    world.store.conn.execute(
        "UPDATE portraits SET read_as = ?, became = ? WHERE entity_id = ?",
        (json.dumps(read_as), became, entity_id))
    world.store.conn.commit()


def count(world) -> tuple[int, int]:
    """How many things came in as bare names, and how many are still unread."""
    run_script(world.store.conn, SCHEMA)
    asked = world.store.conn.execute("SELECT count(*) FROM portraits").fetchone()[0]
    waiting = world.store.conn.execute(
        "SELECT count(*) FROM portraits WHERE read_as IS NULL").fetchone()[0]
    return asked, waiting


SYSTEM = ("You read an account of one thing and say what sort of thing it is, so a record can "
          "hold it under a class. You never say which thing it is — that is given. You never "
          "judge whether what is said is true.")

ASK = """A record holds a thing that arrived as a bare name. Here is what is known about it.

Its name: {name}
Held so far as: {held_as}

What was said about it:
{words}

Say what sort of thing this is.

**use** — the name of one of the classes below, when this thing is one of those. Give it and
stop. A second class for an idea the record already holds answers for neither.

{classes}

Nothing else is a class here. If none of them is this thing, do not reach for a wider word —
define one.

**define** — only when none of them is this: a new class, as
{{"name": "...", "description": "one sentence saying what this kind of thing is",
  "identified_by": "<the attribute that tells two of them apart>",
  "attributes": [{{"name": "...", "description": "...", "type": "str|int|date|bool"}}]}}
Widely, not narrowly, and named for the kind and not for this example: "Language", not
"LanguageTheUserSpeaks". Three or four attributes that any of these would have, not everything
this one happens to have. Null when you gave `use`.

**attributes** — values for this thing, as {{"<attribute name>": <value>}}, only for attributes
of the class you named and only where the words say so. Leave out what was not said: a value
nobody stated cannot be told apart, later, from one somebody knew. Dates in the words they were
said in ("2019", "June 2019"); do not work one out.

**nature** — one of "place", "agent", "idea", "event", "object", or null when the words do not
say. What kind of thing it is at the coarsest, for a record that has nothing finer.

An account of a thing names other things — "the capital of Italy" is how these words say Rome
is a city — and that is not a reason to refuse it. Everything here is about the thing named at
the top, whatever else is mentioned.

**Whether any of it is true is not part of this task and must not affect any answer.** A record
that holds "Rome is the capital of France" is described exactly as one holding the truth would
be: same class, same attributes, the words as they stand.

JSON only, these keys and no others:
{{"use": null, "define": null, "attributes": {{}}, "nature": null}}"""


# Where a thing goes when the record has no class for it. Offered as an answer it is always the
# right one — "anything the world has no better class for" describes everything — and then no
# class is ever made and the reading has done nothing. It is the absence of a class, so it is
# not among the classes to choose from.
NO_CLASS_YET = "Thing"


def classes_here(world) -> str:
    """The classes a reader may name, so it picks one rather than inventing a word."""
    lines = []
    for name, cls in sorted(world.classes.items()):
        if cls._spec.get("relation") or name == NO_CLASS_YET:
            continue
        lines.append(f"    {name} — {(cls._spec.get('description') or '')[:80]}")
    if not lines:
        return "    (the record has no class for a thing like this yet)"
    return "\n".join(lines[:40])


def words_about(world, entity) -> str:
    """Everything said about this thing, in the words it was said in."""
    said = []
    try:
        remarks = entity.described() if hasattr(entity, "described") else []
    except Exception:  # noqa: BLE001
        remarks = []
    for remark in remarks:
        text = getattr(remark, "text", None)
        if isinstance(text, str) and text.strip():
            said.append(text.strip())
    if not said:
        # The attribute holds them as plain strings; `described()` is the dated reading of the
        # same thing and is not always there.
        said = [line.strip() for line in (getattr(entity, "descriptions", None) or [])
                if isinstance(line, str) and line.strip()]
    return "\n".join(f"    {line}" for line in said[:20])


def read_them(world, reader, limit: int = 50) -> dict:
    """Read the things nobody has read, and give each one its class. Called at the close.

    Everything after the reading is the world as it already is: `define` makes the class,
    `retype` reads the thing under it, assignment fills the attributes. What is new is only
    where the class comes from — read out of what was said rather than chosen by a host before
    it had anything to choose with.
    """
    from terraweaver import ontology

    tally = {"read": 0, "placed": 0, "defined": 0, "no_words": 0, "failed": 0}
    for one in unread(world, limit):
        try:
            entity = world.store.load(one["entity_id"], world.classes)
        except Exception:  # noqa: BLE001 - a thing that has gone is not a thing we can read
            mark(world, one["entity_id"], {"gone": True})
            continue
        if entity is None:
            mark(world, one["entity_id"], {"gone": True})
            continue
        words = words_about(world, entity)
        if not words:
            # Nothing was said about it, so there is nothing to read. It keeps its bare name and
            # waits: the next task that says something about it will find this row still open.
            tally["no_words"] += 1
            continue
        try:
            said = reader.json(SYSTEM, ASK.format(
                name=entity.display_name(), held_as=type(entity).__name__,
                words=words, classes=classes_here(world)))
        except Exception:  # noqa: BLE001 - a reader that fails leaves the words for a later pass
            tally["failed"] += 1
            continue
        if not said:
            tally["failed"] += 1
            continue
        tally["read"] += 1
        class_name = _class_for(world, said, tally)
        became = None
        try:
            with ontology.stating("world"):
                if class_name and class_name != type(entity).__name__:
                    entity = world.retype(entity, class_name)
                    became = class_name
                    tally["placed"] += 1
                _fill(world, entity, said)
        except Exception as wrong:  # noqa: BLE001 - the world's own refusals still stand
            # The thing stays exactly as it was. A class the world could not apply is a class
            # lost, not a thing lost: the name is recorded and the words are on it.
            mark(world, one["entity_id"], {**said, "refused": str(wrong)[:200]})
            continue
        mark(world, one["entity_id"], said, became)
    return tally


def _class_for(world, said: dict, tally: dict) -> str | None:
    """The class this reading names — one already here, or one defined now."""
    if said.get("use"):
        named = str(said["use"]).strip()
        cls = world.classes.get(named)
        if cls is not None and not cls._spec.get("relation"):
            return named
    spec = said.get("define")
    if not isinstance(spec, dict) or not spec.get("name"):
        return None
    grow = (world.extras or {}).get("define")
    if grow is None:
        return None
    attributes = [a for a in (spec.get("attributes") or []) if isinstance(a, dict) and a.get("name")]
    try:
        made = grow(spec["name"], spec.get("description") or spec["name"],
                    spec.get("identified_by") or "name", attributes)
    except Exception:  # noqa: BLE001 - a name already taken is a class to join, not to force
        cls = world.classes.get(str(spec["name"]).strip())
        return None if cls is None or cls._spec.get("relation") else cls._spec["name"]
    tally["defined"] += 1
    return made._spec["name"]


def _fill(world, entity, said: dict) -> None:
    """Put the values the reader gave where the class has somewhere for them.

    Only declared attributes, and only ones still empty: a reading is the weakest thing here and
    has no business overwriting what somebody stated. What has no attribute to go into is
    already in the record as the words it was said in, which is where it belongs.
    """
    declared = {a["name"] for a in type(entity)._spec["attributes"] if "derived" not in a}
    values = dict(said.get("attributes") or {})
    if said.get("nature") and "nature" in declared:
        values.setdefault("nature", said["nature"])
    for name, value in values.items():
        if name not in declared or value in (None, "", []):
            continue
        if getattr(entity, name, None) not in (None, "", []):
            continue
        try:
            setattr(entity, name, value)
        except Exception:  # noqa: BLE001 - a value of the wrong shape is not worth the thing
            continue
    world.save(entity)
