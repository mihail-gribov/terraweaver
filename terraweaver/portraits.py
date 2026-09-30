"""What a thing is, said in words, and read afterwards.

The twin of `sentences.py`, for one thing instead of two, and built on the same division. A host
that must choose a class before it can name a city chooses badly, for the same reason it chose
relation types badly: the choice comes before it has anything to choose with. So it names the
thing, the world records it as a bare `Thing`, and the host says what it is in the words it has:

    rome = Thing.identify(name="Rome")[0]     # nobody here of that name — recorded
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
import time
from terraweaver import prompts
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

-- Somebody looked for this thing under a class it is not in. Not an answer and not a correction:
-- a question for the reading to put, and the reason it is worth putting. Measured 2026-09-29: a
-- world whose `Country` held five countries while Germany stayed a `Thing` answered "not
-- recorded" about a fact it held, because the host asked `Country.find(name="Germany")` — which
-- is the sensible question of a class the world itself had made.
CREATE TABLE IF NOT EXISTS looked_for (
    entity_id TEXT NOT NULL,
    class_name TEXT NOT NULL,     -- what somebody expected it to be
    was TEXT,                     -- what it is now
    asked_at TEXT NOT NULL,
    read_at TEXT,                 -- when the reading put the question, if it has
    PRIMARY KEY (entity_id, class_name)
);
"""


def comes_in(world, entity, task_id: str | None = None) -> None:
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


def looked_for(world, entity, class_name: str, was: str | None = None) -> None:
    """Note that somebody expected this thing to be a `class_name`, for the reading to check.

    The world does not act on it: whether Prague is a city or a café is not settled by somebody
    having asked for a café. It is a hypothesis with a reason behind it — a host asked, which is
    evidence about the idea — and it goes to the reading, which tests it the way it tests every
    placing: by walking down from where the thing sits. That walk is the priority, because a class
    somebody expected is almost always below the one the thing is in.
    """
    run_script(world.store.conn, SCHEMA)
    try:
        world.store.conn.execute(
            "INSERT OR IGNORE INTO looked_for (entity_id, class_name, was, asked_at) "
            "VALUES (?, ?, ?, ?)",
            (entity.id, class_name, was or type(entity).__name__,
             datetime.now(timezone.utc).isoformat()))
        world.store.conn.commit()
    except Exception:  # noqa: BLE001 - never what stops a lookup
        return


def expected_of(world, entity_id: str) -> list[str]:
    """The classes somebody has looked for this thing under, newest last. For the reading to read."""
    run_script(world.store.conn, SCHEMA)
    try:
        return [row[0] for row in world.store.conn.execute(
            "SELECT class_name FROM looked_for WHERE entity_id = ? ORDER BY asked_at", (entity_id,))]
    except Exception:  # noqa: BLE001
        return []


def mark(world, statement_id: str, entity_id: str, read_as: dict, became: str | None = None) -> None:
    world.store.conn.execute(
        "INSERT OR REPLACE INTO portraits (statement_id, entity_id, read_at, read_as, became) "
        "VALUES (?, ?, ?, ?, ?)",
        (statement_id, entity_id, datetime.now(timezone.utc).isoformat(),
         json.dumps(read_as), became))
    world.store.conn.commit()


def shape(world) -> str:
    """What the names pass did, and on what it failed — the same instrument the links have.

    A tally of `read / placed / defined / gave_up` says a fifth of the names ended badly and nothing
    about which fifth or why. This reads the rows back: how they ended, what the walk decided, and
    the words the world said to the engineer when its code would not run. Nothing here calls a model.
    """
    import collections

    run_script(world.store.conn, SCHEMA)
    rows = world.store.conn.execute("SELECT read_as, became FROM portraits").fetchall()
    if not rows:
        return "no name has been read in this world yet."
    went, walked, said, placed = collections.Counter(), collections.Counter(), collections.Counter(), 0
    for raw, became in rows:
        try:
            one = json.loads(raw or "{}")
        except Exception:  # noqa: BLE001
            continue
        went[one.get("went") or ("refused" if "refused" in one else "(nothing said)")] += 1
        walked[one.get("walked_to") or "(nowhere)"] += 1
        if became:
            placed += 1
        if one.get("went") in ("gave up", "nothing to run") or "refused" in one:
            trouble = one.get("refused") or one.get("said_back") or ""
            said[" ".join(str(trouble).split())[:100] or "(nothing recorded)"] += 1
    out = [f"{len(rows)} name(s) read, {placed} of them placed under another class"]
    out.append("  ended:     " + "; ".join(f"{k} {n}" for k, n in went.most_common()))
    out.append("  walked to: " + "; ".join(f"{k} {n}" for k, n in walked.most_common(6)))
    if said:
        out.append("  and what the world said on the ones that failed:")
        for what, n in said.most_common(5):
            out.append(f"             {n}x {what}")
    return "\n".join(out)


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
# Only the last step is open, and only when nothing fitted. `world.jev` is the picker, named
# for the class of model rather than for one of them: a system-one model answering a question
# with named options, and which weights are behind it is a deployment question, not the world's.
ROOTS = ("Thing", "Event")

# What `authoring._described` insists on: a description shorter than this is a label, not an
# account, and the world refuses it.
DESCRIBED_ENOUGH = 12


def children_of(world, name: str) -> dict:
    """The classes declared as kinds of this one."""
    return {n: c for n, c in sorted(world.classes.items())
            if c._spec.get("parent") == name and not c._spec.get("relation")}


def walk_down(world, entity, words: str, jev) -> tuple[str, str | None]:
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
            scored = jev.choose(state, f"Which of these is {entity.display_name()}?", options)
        except Exception:  # noqa: BLE001 - one that fails leaves it where it sits
            return at, None
        if not scored:
            return at, None
        best = max(scored, key=scored.get)
        if best == NEW_ONE:
            return at, at
        if best in seen or best not in children:
            return at, None
        at, _ = best, seen.add(best)


SYSTEM = prompts.PLACING_A_THING

FORMALISE = prompts.FORMALISE

MAKE_ONE = prompts.MAKE_ONE

KEEP_ONE = prompts.KEEP_ONE

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


def formalise(world, engineer, limit: int = 50, jev=None, run=None,
              seconds: float | None = None) -> dict:
    """Read the prose-facts nobody has read, and put each into the record's own terms.

    Two steps, and the split between them is where the cost is. Finding the class is a walk down
    the tree — which child of Thing is this, then which child of that — and every step is a
    closed question, a list of named options, answered by a model built for exactly that. Then
    one open call: the class if none of them fitted, and the code that fills this thing in.

    The code runs the way a host's code runs, through the same door, and what comes back goes
    to whoever wrote it — the same loop, with Nemotron where the agent usually stands.

    `seconds` bounds it, because this runs inside the host's `finish_task` too. Measured
    2026-09-28: the sentence reading was given a budget and this one was not, and a batch with
    forty-eight bare names in it timed the close out anyway. What is not read stays unread, which
    is what it is.
    """
    from terraweaver import ontology, outside

    jev = jev or getattr(world, "jev", None) or outside.AsChoices(engineer)
    tally = {"read": 0, "placed": 0, "defined": 0, "ran": 0, "failed": 0, "gave_up": 0}
    # Things that changed class. Whoever is holding one of these is holding the instance it was
    # before, and the next thing they save writes that back — the reading undone by the very
    # next line the agent runs, quietly, with nothing to show it happened.
    moved: list[str] = []
    began = time.monotonic()
    for one in unread(world, limit):
        if seconds is not None and time.monotonic() - began > seconds:
            break
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
        # What somebody expected it to be, put first, because a class a host asked for is almost
        # always below the one the thing is in — and because the asking is evidence about the idea
        # that nothing else here carries. It is a hypothesis to test, never an answer: Prague is a
        # city and a café and a cinema, and which was meant the world does not decide.
        expected = expected_of(world, one["entity_id"])
        if expected:
            words = (f"{words}\n    Somebody looked for this under "
                     f"{' and '.join(sorted(set(expected)))} and did not find it there.")
        at, wanting = walk_down(world, entity, words, jev)
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
        read_as["code"], read_as["went"], read_as["said_back"] = _the_loop(
            engineer, run, entity, asked, said, tally, getattr(world, "better", None))
        mark(world, one["statement_id"], one["entity_id"], read_as, became)
    tally["moved"] = moved
    return tally


def _the_loop(engineer, run, entity, asked: str, said: dict, tally: dict,
              senior=None) -> tuple[list, str, str]:
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
        return written, "nothing to run" if run is not None else "nowhere to run it", ""
    said_back = ""
    for go in range(GOES):
        written.append(code)
        got = run(entity, code)
        # Kept, because a count of give-ups says a reading failed and not why — and why is a
        # sentence the world has already written. Measured 2026-09-29 on the link side: the same
        # column named the cause of 24 failures at a glance, where an hour had gone on guessing.
        # 56 of 285 names ended here with nothing anywhere to say on what.
        said_back = format_result(got)[:600]
        if got.get("ok"):
            tally["ran"] += 1
            return written, "done", said_back
        if go == GOES - 1:
            break
        back = (f"{asked}\n\nYou wrote this, and the record answered:\n\n{code}\n\n"
                f"{format_result(got)[:1500]}\n\nWrite the lines that still have to run — the "
                f"ones that finished are done and must not be sent again. `class` is null now; "
                f"the class is made. Nothing new is invented: only what the words above say.")
        # The senior engineer writes the go that follows a refusal, where the world can reach one.
        again = _say(getattr(entity, "_better", None) or senior or engineer, back)
        code = str((again or {}).get("code") or "").strip()
        if not code:
            break
    tally["gave_up"] += 1
    return written, "gave up", said_back


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
        words=words, joined=_already_joined(world, entity), held=sentences.held(world),
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
        return ("A word this record has not got makes its own type the first time it is "
                "said, so `it.relate(other, \"the_word\")` writes the link and makes the word "
                "in one go. `set_` exists only for words that are already here.")
    return ('A word this record has not got has to be declared before it can be used, on its '
            'own line first:\n\n'
            '    world.define_relation("capital_of", "a city that is the seat of a country\'s '
            'government", nature="related_to", cardinality="many-to-one")\n'
            '    it.set_capital_of(italy)\n\n'
            'The second argument is a sentence saying what that kind of link is — about the '
            'kind, not about these two — and a record refuses anything shorter than a few '
            'words. `nature` is one of related_to / part_of / kind_of / same_as / derived_from. '
            '`cardinality` is about one moment: "many-to-one" when this thing has one of those '
            'at a time, "one-to-many" the other way, "many-to-many" when neither is limited. '
            'One at a time means a new one ends the standing one where it begins, and both stay '
            'in the record.')

def _already_joined(world, entity) -> str:
    """What this thing is joined to now, so the same fact is not said a second time.

    Not shown, it was said again from the other end under another word: London, described as
    the city somebody was born in, came back as `London.set_birthplace_of(...)` beside the
    `born_in` that already held. Two words for one birth, and nothing afterwards can tell that
    they are one fact.
    """
    lines = []
    try:
        for link in entity.relations():
            lines.append(f"    {link.display_name()[:100]}")
    except Exception:  # noqa: BLE001 - a thing whose links cannot be read is joined to nothing
        return "    (nothing yet)"
    return "\n".join(sorted(set(lines))[:30]) or "    (nothing yet)"


def _classes_here(world) -> str:
    """Every class something can be looked up under, so a name that is not one is not written.

    Shown rather than remembered: an engineer given an example that names a class this world has
    not got copies the example. `Place.identify(...)` came back a NameError three times
    running in a world whose widest classes were Thing and Event.
    """
    from terraweaver import matching

    lines = []
    for name, cls in sorted(world.classes.items()):
        if cls._spec.get("relation") or cls._spec.get("own"):
            continue
        by = cls._spec.get("identified_by") or matching.NAME_KEYS.get(name) or "name"
        lines.append(f"    {name}.identify({by}=\"...\") — "
                     f"{(cls._spec.get('brief') or cls._spec.get('description') or '')[:70]}")
    return "\n".join(lines[:40])


def _as_attribute(said: dict) -> dict:
    """One attribute as the world's own door takes it, and nothing else the engineer wrote.

    `define` takes five named arguments and a sixth key is a `TypeError`. The engineer writes what
    it thinks belongs on an attribute — `unit`, `example`, `source` — and one extra key took the
    whole class down: the raise landed in the "name already taken" branch, which read it as a
    class to join, so the thing stayed a bare Thing and every later one of its kind had nowhere to
    go (docs/code-review-2026-09-30.md 3.4.4).
    """
    out = {"name": said["name"], "description": str(said.get("description") or "")}
    if isinstance(said.get("type"), str) and said["type"].strip():
        out["type"] = said["type"].strip()
    for word in ("changes", "required"):
        if isinstance(said.get(word), bool):
            out[word] = said[word]
    return out


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
    attributes = [_as_attribute(a) for a in (spec.get("attributes") or []) if isinstance(a, dict)
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
