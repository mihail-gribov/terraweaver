"""What a thing is, said in words, and read afterwards.

The twin of `sentences.py`, for one thing instead of two, and built on the same division. A host
that must choose a class before it can name a city chooses badly, for the same reason it chose
relation types badly: the choice comes before it has anything to choose with. So it names the
thing, the world records it as a bare `Thing`, and the host says what it is in the words it has:

    rome = world.identify(Thing, name="Rome")[0]     # nobody here of that name — recorded
    rome.describe("Rome is the capital of Italy, where the user lived until 2019")

What class that is, which attributes it fills, whether a class for it has to be made at all —
read afterwards, at the close of the task, by an engineer of knowledge whose whole
attention is that one question.

**Which thing it is, is never read.** The entity is handed over as an entity and its id is what
the reading is written against. An engineer that had to find "Rome" in its own answer could name
something that is not in the record at all, and identity recovered from words is the one mistake
no later pass repairs. The engineer says what this is; it never says which this is.

**Whether it is true is not the engineer's business.** A world that holds "London is the capital of
France" describes it exactly as it would the truth. This is a record of what somebody said.
"""
import json
from datetime import datetime, timezone

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS bare_names (
    entity_id TEXT PRIMARY KEY,
    asked_at TEXT NOT NULL,
    task_id TEXT
);
CREATE TABLE IF NOT EXISTS portraits (
    statement_id TEXT PRIMARY KEY,   -- the prose-fact that was read
    entity_id TEXT NOT NULL,
    read_at TEXT NOT NULL,           -- when it was taken apart
    read_as TEXT,                    -- what the engineer made of it
    became TEXT                      -- the class it put the thing under, if it moved it
);
CREATE INDEX IF NOT EXISTS idx_portraits_entity ON portraits(entity_id);
"""


def wanted(world, entity, task_id: str | None = None) -> None:
    """Note that this thing arrived as a bare name, so the close knows to read what is said of it.

    Called where the name was recorded, not where it is read. Nothing waits on this: the thing is
    in the world from that moment, findable and linkable, and knowing what it is is an improvement
    on something that is already there.
    """
    run_script(world.store.conn, SCHEMA)
    world.store.conn.execute(
        "INSERT OR IGNORE INTO bare_names (entity_id, asked_at, task_id) VALUES (?, ?, ?)",
        (entity.id, datetime.now(timezone.utc).isoformat(), task_id))
    world.store.conn.commit()


# What the world said itself. Its own writing is not an account to be read: the engineer's code
# calls `it.describe(...)` for what no attribute could hold, that lands as a prose-fact like any
# other, and reading it sets the whole circuit off again over a sentence the world composed.
# Only what came from outside is an account of anything.
OURS = "world"


def unread(world, limit: int = 50) -> list[dict]:
    """Prose-facts said from outside about a bare-named thing, that nobody has taken apart yet.

    The unit is the prose-fact and not the thing, because a thing is described more than once.
    Kept per thing, a second account arriving a week later found the row already marked read and
    was never looked at — the class stayed whatever one sentence had made of it. What a prose
    fact carries about itself it already carries (`facts.Statement`): where it came from, when,
    in which run. What is added here is when it was read and what came of it.
    """
    run_script(world.store.conn, SCHEMA)
    bare = [r[0] for r in world.store.conn.execute(
        "SELECT entity_id FROM bare_names ORDER BY asked_at").fetchall()]
    done = {r[0] for r in world.store.conn.execute(
        "SELECT statement_id FROM portraits").fetchall()}
    out = []
    for entity_id in bare:
        try:
            said = world.facts.about(entity_id, "descriptions")
        except Exception:  # noqa: BLE001 - a thing that has gone says nothing
            continue
        for statement in said:
            if statement.id in done or statement.source == OURS:
                continue
            out.append({"statement_id": statement.id, "entity_id": entity_id,
                        "words": str(statement.value), "source": statement.source,
                        "said_at": statement.stated_at})
            if len(out) >= limit:
                return out
    return out


def still_only_a_name(world) -> list[str]:
    """Things that came in as a bare name and have had nothing said about them yet."""
    run_script(world.store.conn, SCHEMA)
    silent = []
    for (entity_id,) in world.store.conn.execute("SELECT entity_id FROM bare_names").fetchall():
        try:
            if not world.facts.about(entity_id, "descriptions"):
                silent.append(entity_id)
        except Exception:  # noqa: BLE001
            continue
    return silent


def mark(world, statement_id: str, entity_id: str, read_as: dict, became: str | None = None) -> None:
    world.store.conn.execute(
        "INSERT OR REPLACE INTO portraits (statement_id, entity_id, read_at, read_as, became) "
        "VALUES (?, ?, ?, ?, ?)",
        (statement_id, entity_id, datetime.now(timezone.utc).isoformat(),
         json.dumps(read_as), became))
    world.store.conn.commit()


def count(world) -> tuple[int, int]:
    """How many things came in as bare names, and how many prose-facts are still unread."""
    run_script(world.store.conn, SCHEMA)
    asked = world.store.conn.execute("SELECT count(*) FROM bare_names").fetchone()[0]
    return asked, len(unread(world, limit=10_000))


NEW_ONE = "none of these"

# The widest classes: a thing is, an event happens. Everything else is a kind of one of them,
# and finding the class is walking down from where the thing already sits, asking at each level
# which child it is. Each of those is a closed question — a list of named options — and a closed
# question is answered by a model an order of magnitude cheaper than one answering in words.
# Only the last step is open, and only when nothing fitted.
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
    step down, a stop, or word that the record has no class for this.

    The option names are what an engineer has to echo back, so they are short and plain. This one
    read "— none of these: it needs a class of its own" and came back unmatched every time: the
    walk never descended and nothing was ever placed.
    """
    at = type(entity).__name__
    if at not in world.classes:
        at = ROOTS[0]
    state = f"{entity.display_name()}, held so far as {at}.\n\nWhat was said about it:\n{words}"
    seen = {at}
    while True:
        children = children_of(world, at)
        if not children:
            return at, at if at in ROOTS else None
        options = {n: (c._spec.get("brief") or c._spec.get("description") or n)[:200]
                   for n, c in children.items()}
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

FORMALISE = """A record holds a thing and an account of it in words. Put the account into the
record's own terms: describe the class it belongs to, and write the code that fills this one in.

The thing: {name}   (bound in the code as `it`)
It is a kind of: {parent} — {parent_is}
{standing}

What was said about it:
{words}

**Everything comes out of those words and nothing else.** You know a great deal about the world
and none of it belongs here: a city is in a country, a sport has a ball, a person has a birthday
— and if the words did not say so, it is not here. An empty answer to either part is a common
and correct one, and the shortest account is often the whole of it: "Rome is a city" gives a
class and no code at all.

**Whether any of it is true is not part of this task and must not affect any answer.** A record
that holds "Rome is the capital of France" is written exactly as one holding the truth would be,
with France in the country's place. Correcting it would be inventing too — it would put in the
record something nobody said.

**class** — {class_ask}

**code** — the lines that fill this thing in, in the same language a person writing to this
record uses. `it` is already bound to the thing; never make it again, never rename it.

    it.population = 2800000                      a value the words gave
    italy = world.identify(Thing, name="Italy")[0]    another thing the words named
    it.relate(italy, "capital_of")               what this thing is to that one

`world.identify(<class>, name="...")` is how another thing is reached: it finds the one of that
name or records it, and hands back a list. Take `[0]`. The class must be one of these, and
`Thing` is always right for something you have no narrower word for here:

{classes}

A class that is not on that list does not exist and the line will fail.

A link is written from this thing outward, and the word is what THIS one is to the other:
"Rome is the capital of Italy" is a link from Rome with the word `capital_of`, because Rome is
Italy's capital and not the other way round.

**`it.relate(other, "the_word")` is how a link is written, always.** `it.the_word(other)` is a
short form that exists only for words the record already has — used for any other word it is a
missing attribute and the line fails.

{new_words}

**A link is never an attribute.** `it.capital_of = italy` puts a thing in a slot: it cannot be
asked about by type, nothing can supersede it, and it is invisible to everything that reads
links. If a line joining two things fails, the answer is `relate`, never `world.attribute`.

Words the record already has, to use rather than invent a second for the same idea:

{held}

Anything else is one of these, and nothing else is available:

    it.<attribute> = <value>                    only attributes the class has, never a thing
    it.describe("...")                          something with no attribute to go in
    it.relate(other, "<word>")                  what this thing is to another thing

Dates as `date(2019, 6, 1)`, and only where the words gave one; do not work one out.

JSON only, these two keys and no others:
{{"class": {class_shape}, "code": "..."}}"""

MAKE_ONE = """the record has no class for this thing, so describe one. Name the kind, not this
example: "Language", not "LanguageTheUserSpeaks"; "Sport", not "FinnishBatAndBallGame". The
next thing of this kind must fit it without being bent. It is a kind OF {parent}, so it is not
called {parent} — that name is taken by the wider one. Three or four attributes any of these
would have, not everything this one happens to have, each described in a sentence rather than
a label: "how many people live there", not "Population". One of these is known by its name and
the record adds that itself, so give no `name` attribute. `brief` is how the class appears in
the list every host reads before it writes: a clause, not a sentence."""

KEEP_ONE = """this thing is a {parent} and the record has the class already, so `class` is
null."""

MAKE_SHAPE = ('{{"name": "...", "brief": "...", "description": "one sentence saying what this '
              'kind of thing is", "attributes": [{{"name": "...", "description": "...", '
              '"type": "str|int|date|bool"}}]}}')


# The most general class of thing, and a real one: a book or a dish is a Thing and wants no
# other word. It is shown last and said to be the widest, because an engineer that sees it first
# among equals takes it every time — it fits everything — and then no class is ever made.
WIDEST = "Thing"


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


# How many times the world will hand its own failure back and ask for the next lines. The same
# loop a host is in, and bounded for the same reason: past a few goes the writer is writing
# against a record it has misunderstood, and going on spends the budget on forty copies of one
# error. Three is a mistake repeated.
GOES = 3


def read_them(world, engineer, limit: int = 50, picker=None, run=None) -> dict:
    """Read the prose-facts nobody has read, and put each into the record's own terms.

    Two steps, and the split between them is where the cost is. Finding the class is a walk down
    the tree — which child of Thing is this, then which child of that — and every step is a
    closed question, a list of named options, answered by a model built for exactly that. Then
    one open call: the class if none of them fitted, and the code that fills this thing in.

    The code runs the way a host's code runs, through the same door, and what comes back goes
    to whoever wrote it — the same loop, with Nemotron where the agent usually stands.
    """
    from terraweaver import ontology, outside

    picker = picker or getattr(world, "picker", None) or outside.AsChoices(engineer)
    tally = {"read": 0, "placed": 0, "defined": 0, "ran": 0, "failed": 0, "gave_up": 0}
    # Things that changed class. Whoever is holding one of these is holding the instance it was
    # before, and the next thing they save writes that back — the reading undone by the very
    # next line the agent runs, quietly, with nothing to show it happened.
    moved: list[str] = []
    for one in unread(world, limit):
        try:
            entity = world.store.load(one["entity_id"], world.classes)
        except Exception:  # noqa: BLE001 - a thing that has gone is not a thing we can read
            mark(world, one["statement_id"], one["entity_id"], {"gone": True})
            continue
        if entity is None:
            mark(world, one["statement_id"], one["entity_id"], {"gone": True})
            continue
        # This prose-fact is what set the reading off; the reading itself sees everything said
        # about the thing. A second account arriving later says what the first did not, and
        # placing the thing on half of what is known about it is worse than waiting.
        words = words_about(world, entity) or f"    {one['words']}"
        at, wanting = walk_down(world, entity, words, picker)
        asked = _asking(world, entity, words, at, make_new=bool(wanting))
        said = _say(engineer, asked)
        if said is None:
            tally["failed"] += 1
            continue
        tally["read"] += 1
        read_as = {"words": one["words"], "source": one["source"], "walked_to": at,
                   "new_under": wanting, "class": said.get("class")}
        became = None
        try:
            with ontology.stating("world"):
                if wanting:
                    made = _make_one(world, said.get("class"), wanting, tally)
                    if made:
                        at, read_as["defined"] = made, made
                if at and at != type(entity).__name__ and at in world.classes:
                    entity = world.retype(entity, at)
                    became = at
                    moved.append(one["entity_id"])
                    tally["placed"] += 1
        except Exception as wrong:  # noqa: BLE001 - the world's own refusals still stand
            # The thing stays exactly as it was. A class the world could not apply is a class
            # lost, not a thing lost: the name is recorded and the words are on it.
            mark(world, one["statement_id"], one["entity_id"],
                 {**read_as, "refused": str(wrong)[:200]})
            continue
        read_as["code"], read_as["went"] = _the_loop(engineer, run, entity, asked, said, tally)
        mark(world, one["statement_id"], one["entity_id"], read_as, became)
    tally["moved"] = moved
    return tally


def _the_loop(engineer, run, entity, asked: str, said: dict, tally: dict) -> tuple[list, str]:
    """Run what the engineer wrote, and hand back whatever the world says until it is done.

    Exactly the loop a host is in: write, read what the world says back, answer that. The only
    difference is who is on the other end. A host that is told its line failed writes the
    continuation under it, and so does this — which is the whole reason the reading is asked
    for as code rather than as a shape somebody here has to interpret.
    """
    from terraweaver.runtime import format_result

    written = []
    code = str(said.get("code") or "").strip()
    if run is None or not code:
        return written, "nothing to run" if run is not None else "nowhere to run it"
    for go in range(GOES):
        written.append(code)
        got = run(entity, code)
        if got.get("ok"):
            tally["ran"] += 1
            return written, "done"
        if go == GOES - 1:
            break
        back = (f"{asked}\n\nYou wrote this, and the record answered:\n\n{code}\n\n"
                f"{format_result(got)[:1500]}\n\nWrite the lines that still have to run — the "
                f"ones that finished are done and must not be sent again. `class` is null now; "
                f"the class is made. Nothing new is invented: only what the words above say.")
        again = _say(engineer, back)
        code = str((again or {}).get("code") or "").strip()
        if not code:
            break
    tally["gave_up"] += 1
    return written, "gave up"


def _say(engineer, asked: str) -> dict | None:
    try:
        said = engineer.json(SYSTEM, asked)
    except Exception:  # noqa: BLE001 - an engineer that fails leaves the words for a later pass
        return None
    return said if isinstance(said, dict) else None


def _asking(world, entity, words: str, at: str, make_new: bool) -> str:
    """The one open question: describe the class, and write the code that fills this one in."""
    from terraweaver import sentences

    parent = world.classes.get(at)
    parent_is = (parent._spec.get("brief") or parent._spec.get("description") or at)[:150] \
        if parent is not None else at
    standing = ""
    if not make_new and parent is not None:
        named = [a["name"] for a in parent._spec["attributes"]
                 if "derived" not in a and a["name"] not in ("descriptions", "tags", "facts", "notes")]
        standing = f"The attributes it has: {', '.join(named)}"
    return FORMALISE.format(
        name=entity.display_name(), parent=at, parent_is=parent_is, standing=standing,
        words=words, held=sentences.held(world), classes=_classes_here(world),
        new_words=_a_word_it_has_not(world),
        class_ask=(MAKE_ONE if make_new else KEEP_ONE).format(parent=at),
        class_shape=MAKE_SHAPE if make_new else "null")


def _a_word_it_has_not(world) -> str:
    """What to do with a word for a link this record has no type for — as this world stands.

    Whether an unknown word makes its own type is a switch (`initiative.MAKES_TYPES`), off by
    default and turned on one at a time against a record somebody can already read. Telling the
    engineer the wrong one costs a whole reading: promised that `relate` would make the type, it
    wrote the line, watched it refused, and spent its three goes on `define_relation` calls the
    world refused for a different reason.
    """
    from terraweaver import initiative

    if initiative.MAKES_TYPES:
        return ("A word this record has not got makes its own type when you use it, so write "
                "the link and say no more about it.")
    return ('A word this record has not got has to be declared before it can be used, on its '
            'own line first:\n\n'
            '    world.define_relation("capital_of", "a city that is the seat of a country\'s '
            'government", nature="related_to", cardinality="many-to-one", over_time=False)\n'
            '    it.relate(italy, "capital_of")\n\n'
            'The second argument is a sentence saying what that kind of link is — about the '
            'kind, not about these two — and a record refuses anything shorter than a few '
            'words. `nature` is one of related_to / part_of / kind_of / same_as / derived_from. '
            '`cardinality` is "many-to-one" when this thing has one of those, "one-to-many" the '
            'other way, "many-to-many" when neither is limited. `over_time=True` when one holds '
            'at a time and a new one ends the last (an employer, a spouse), False when they '
            'simply accumulate.')


def _classes_here(world) -> str:
    """Every class something can be looked up under, so a name that is not one is not written.

    Shown rather than remembered: an engineer given an example that names a class this world has
    not got copies the example. `world.identify(Place, ...)` came back a NameError three times
    running in a world whose widest classes were Thing and Event.
    """
    from terraweaver import matching

    lines = []
    for name, cls in sorted(world.classes.items()):
        if cls._spec.get("relation") or cls._spec.get("own"):
            continue
        by = cls._spec.get("identified_by") or matching.NAME_KEYS.get(name) or "name"
        lines.append(f"    {name}({by}=\"...\") — "
                     f"{(cls._spec.get('brief') or cls._spec.get('description') or '')[:70]}")
    return "\n".join(lines[:40])


def _make_one(world, spec, under: str, tally: dict) -> str | None:
    """Make the class the engineer described, under the class the walk stopped at.

    Under it, and that is the whole of what makes it reachable: placing a thing walks down from
    the widest class asking which child it is, so a class with no parent is a leaf nobody ever
    descends to. What to ask about one of these is not invented here — it comes from the parent,
    which is what having a parent means, and a line made up for a class nobody has thought about
    is a line nobody wrote on purpose.
    """
    grow = (getattr(world, "extras", None) or {}).get("define")
    if grow is None or not isinstance(spec, dict) or not spec.get("name"):
        return None
    if str(spec["name"]).strip().lower() == under.lower():
        # Naming it after the class it is a kind of is not a new class, it is the walk saying
        # "none of these" and then handing back where it started.
        return None
    # An attribute the world refuses does not cost the class. An engineer writes attribute
    # descriptions as labels — "Land area" — and `define` wants a sentence; losing City over
    # `area_sqkm` left the thing a bare Thing and every later city with nowhere to go.
    attributes = [a for a in (spec.get("attributes") or []) if isinstance(a, dict)
                  and a.get("name") and a["name"] not in ("name", "full_name")
                  and len(str(a.get("description") or "").strip()) >= DESCRIBED_ENOUGH]
    # What tells two of these apart is what tells two of the parent apart: a kind of Person is
    # known by a full name, not by a `name` nobody writes. Identity is declared per class here,
    # so a child that says nothing starts from what is above it.
    from terraweaver import matching

    above = world.classes.get(under)
    known_by = ((above._spec.get("identified_by") if above is not None else None)
                or matching.NAME_KEYS.get(under) or "name")
    try:
        made = grow(spec["name"], spec.get("description") or spec["name"], known_by, attributes,
                    parent=under, brief=spec.get("brief"), source="world")
    except Exception:  # noqa: BLE001 - a name already taken is a class to join, not to force
        cls = world.classes.get(str(spec["name"]).strip())
        if cls is None or cls._spec.get("relation") or cls._spec["name"] == under:
            return None
        return cls._spec["name"]
    tally["defined"] += 1
    return made._spec["name"]
