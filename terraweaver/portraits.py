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


# The option names are what a reader has to echo back exactly, so they are short and plain.
# This one read "— none of these: it needs a class of its own" and came back unmatched every
# time: the walk never descended and nothing was ever placed.
NEW_ONE = "none of these"

# The widest classes: a thing is, an event happens. Everything else is a kind of one of them,
# and finding the class is walking down from where the thing already sits, asking at each level
# which child it is. Each of those is a closed question — a list of named options — and a closed
# question is answered by a model an order of magnitude cheaper than one answering in words.
# Only the last step is open, and only when nothing fitted: inventing the class.
ROOTS = ("Thing", "Event")

# What `authoring._described` insists on: a description shorter than this is a label, not an
# account, and the world refuses it.
DESCRIBED_ENOUGH = 12


def children_of(world, name: str) -> dict:
    """The classes declared as kinds of this one."""
    return {n: c for n, c in sorted(world.classes.items())
            if c._spec.get("parent") == name and not c._spec.get("relation")}


def walk_down(world, entity, words: str, picker) -> tuple[str, str | None]:
    """Descend from where the thing sits to the most particular class that fits.

    Returns (the class to stop at, the class under which a new one is wanted or None). At each
    level the options are that class's children plus "none of these", so the answer is either a
    step down, a stop, or a word for something the record has no class for.
    """
    at = type(entity).__name__
    if at not in world.classes:
        at = ROOTS[0]
    state = f"{entity.display_name()}, held so far as {at}.\n\nWhat was said about it:\n{words}"
    seen = {at}
    while True:
        children = children_of(world, at)
        if not children:
            return at, None
        options = {n: (c._spec.get("description") or n)[:200] for n, c in children.items()}
        options[NEW_ONE] = (f"none of the above is what this is; it is a kind of {at} that this "
                            f"record has no class for")
        try:
            scored = picker.choose(state, f"Which of these is {entity.display_name()}?", options)
        except Exception:  # noqa: BLE001 - a picker that fails leaves it where it sits
            return at, None
        if not scored:
            return at, None
        best = max(scored, key=scored.get)
        if best == NEW_ONE:
            return at, at
        if best in seen or best not in children:
            return at, None
        at, _ = best, seen.add(best)


SYSTEM = ("You read an account of one thing and say what sort of thing it is, so a record can "
          "hold it under a class. You never say which thing it is — that is given. You never "
          "judge whether what is said is true.")

NAME_IT = """A record holds a thing it has no class for. Give it one.

Its name: {name}
It is a kind of: {parent} — {parent_is}

What was said about it:
{words}

Name the kind, not this example: "Language", not "LanguageTheUserSpeaks"; "Sport", not
"FinnishBatAndBallGame". The next thing of this kind must fit it without being bent. It is a
kind OF {parent}, so it is not called {parent} — that name is taken by the wider one. Three or
four attributes any of these would have, not everything this one happens to have. Describe each
of them in a sentence rather than a label: "how many people live there", not "Population" — it
is what somebody looking for that attribute later will search by.

One of these is known by its name, and the record adds that itself — do not give a `name`
attribute and do not put this thing's name into any other one.

`brief` is how this class appears in the list every host reads before it writes anything: a
clause, not a sentence, saying what sort of thing goes here and when to reach for it. "A city,
town or village", not "The City class represents urban settlements which may have a population".
It is read after the class's own name and a dash.

**Whether what was said is true is not part of this task and must not affect any answer.**

JSON only, these keys and no others:
{{"name": "...", "brief": "...",
  "description": "one sentence saying what this kind of thing is",
  "attributes": [{{"name": "...", "description": "...", "type": "str|int|date|bool"}}]}}"""


FILL_IT = """A record holds this thing under the class below. Fill in what was said about it.

Its name: {name}
Its class: {class_name} — {class_is}
The attributes it has: {attributes}

What was said about it:
{words}

Give a value only for an attribute named above, and only where the words say so. Leave out
what was not said: a value nobody stated cannot be told apart, later, from one somebody knew.
Dates in the words they were said in ("2019", "June 2019"); do not work one out.

An account of a thing names other things — "the capital of Italy" is how these words say Rome
is a city — and that is not a reason to leave it out.

**Whether any of it is true is not part of this task and must not affect any answer.** A record
that holds "Rome is the capital of France" is filled in exactly as one holding the truth would
be: the words as they stand.

JSON only, these keys and no others:
{{"attributes": {{}}, "nature": null}}"""


# The most general class of thing, and a real one: a book or a dish is a Thing and wants no
# other word. It is shown last and said to be the widest, because a reader that sees it first
# among equals takes it every time — it fits everything — and then no class is ever made.
WIDEST = "Thing"


def classes_here(world) -> str:
    """The classes a reader may name, so it picks one rather than inventing a word."""
    lines = []
    for name, cls in sorted(world.classes.items()):
        if cls._spec.get("relation") or name == WIDEST:
            continue
        lines.append(f"    {name} — {(cls._spec.get('description') or '')[:80]}")
    widest = world.classes.get(WIDEST)
    if widest is not None:
        lines.append(f"    {WIDEST} — the widest of them: a thing with no more particular class "
                     f"here. Name it only when no other fits and none is worth making.")
    return "\n".join(lines[:41])


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


def read_them(world, reader, limit: int = 50, picker=None) -> dict:
    """Read the things nobody has read, and give each one its class. Called at the close.

    Three steps, and the split between them is where the cost is. Finding the class is a walk
    down the tree — which child of Thing is this, then which child of that — and every step is a
    closed question, a list of named options, answered by a model built for exactly that. Only
    when the walk ends at "none of these" is anything asked in words, and then only the one
    thing options cannot hold: the name and shape of a class nobody has made yet. Filling in the
    values is the third, and it is asked of one class rather than of the whole record.

    Everything after the reading is the world as it already is: `define` makes the class,
    `retype` reads the thing under it, assignment fills the attributes.
    """
    from terraweaver import ontology, outside

    picker = picker or getattr(world, "picker", None) or outside.AsChoices(reader)
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
        at, wanting = walk_down(world, entity, words, picker)
        read_as = {"walked_to": at, "new_under": wanting}
        if wanting:
            made = _make_one(world, entity, words, reader, wanting, tally)
            if made:
                at, read_as["defined"] = made, made
        tally["read"] += 1
        became = None
        try:
            with ontology.stating("world"):
                if at and at != type(entity).__name__ and at in world.classes:
                    entity = world.retype(entity, at)
                    became = at
                    tally["placed"] += 1
                filled = _values_for(world, entity, words, reader)
                read_as["attributes"] = filled.get("attributes")
                read_as["nature"] = filled.get("nature")
                _fill(world, entity, filled)
        except Exception as wrong:  # noqa: BLE001 - the world's own refusals still stand
            # The thing stays exactly as it was. A class the world could not apply is a class
            # lost, not a thing lost: the name is recorded and the words are on it.
            mark(world, one["entity_id"], {**read_as, "refused": str(wrong)[:200]})
            continue
        mark(world, one["entity_id"], read_as, became)
    return tally


def _make_one(world, entity, words: str, reader, under: str, tally: dict) -> str | None:
    """The walk ended at "none of these": ask in words for a class, and make it under that one."""
    grow = (getattr(world, "extras", None) or {}).get("define")
    if grow is None:
        return None
    parent = world.classes.get(under)
    try:
        spec = reader.json(SYSTEM, NAME_IT.format(
            name=entity.display_name(), parent=under,
            parent_is=(parent._spec.get("description") or under)[:120] if parent else under,
            words=words))
    except Exception:  # noqa: BLE001 - a reader that fails leaves it where the walk stopped
        return None
    if not isinstance(spec, dict) or not spec.get("name"):
        return None
    if str(spec["name"]).strip().lower() == under.lower():
        # Naming it after the class it is a kind of is not a new class, it is the walk saying
        # "none of these" and then handing back where it started. The thing stays where it is.
        return None
    # What identifies one of these is not the reader's to choose, and it went wrong the one time
    # it was asked: a City identified by `population`, with "Rome" written into it. These things
    # arrive under a name and are known by it — so the class gets a `name` and is identified by
    # it, and the reader's attributes go alongside.
    # An attribute the world refuses does not cost the class. A reader writes attribute
    # descriptions as labels — "Land area" — and `define` wants a sentence; losing City over
    # `area_sqkm` left the thing a bare Thing and every later city with nowhere to go. The
    # class is the thing being made here; an attribute nobody described is not much of a loss
    # and can be declared later, when something is actually written into it.
    attributes = [a for a in (spec.get("attributes") or []) if isinstance(a, dict)
                  and a.get("name") and a["name"] != "name"
                  and len(str(a.get("description") or "").strip()) >= DESCRIBED_ENOUGH]
    try:
        # The parent goes in with it, and is the whole of what makes this a class the walk
        # reaches next time rather than a leaf nobody descends to. What to ask about one of
        # these is not invented here: it comes from the parent, which is what having a parent
        # means, and a line made up for a class nobody has thought about is a line nobody
        # wrote on purpose.
        made = grow(spec["name"], spec.get("description") or spec["name"], "name", attributes,
                    parent=under, brief=spec.get("brief"), source="world")
    except Exception:  # noqa: BLE001 - a name already taken is a class to join, not to force
        cls = world.classes.get(str(spec["name"]).strip())
        if cls is None or cls._spec.get("relation") or cls._spec["name"] == under:
            return None
        return cls._spec["name"]
    tally["defined"] += 1
    return made._spec["name"]


def _values_for(world, entity, words: str, reader) -> dict:
    """What the words fill in, asked of the one class the thing is now under."""
    cls = type(entity)
    named = [a["name"] for a in cls._spec["attributes"]
             if "derived" not in a and a["name"] not in ("descriptions", "tags", "facts", "notes")]
    try:
        said = reader.json(SYSTEM, FILL_IT.format(
            name=entity.display_name(), class_name=cls.__name__,
            class_is=(cls._spec.get("description") or cls.__name__)[:120],
            attributes=", ".join(named), words=words))
    except Exception:  # noqa: BLE001 - a reader that fails leaves the values unfilled
        return {}
    return said if isinstance(said, dict) else {}


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
