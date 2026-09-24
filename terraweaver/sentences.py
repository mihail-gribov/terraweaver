"""Facts said in words, and typed later.

A host that must choose a relation type before it can say a fact chooses badly: measured over
455 facts, one recorder collected two ideas under `Speaks`, wrote three links backwards because
an argument order had to be right, and answered `over_time` by guess. None of those is a failure
of care — each is a decision it was made to take before it had anything to decide it with.

So there is a second door. The host says the fact in words and names the two things it is about:

    world.say(paris, france, "Paris is the capital of France")

That is recorded at once and costs nothing. What relation it is, which end holds which role,
how many may hold at a moment and when it began are read afterwards, at the close of the task,
by a reader whose whole attention is that one question. A host's run is stopped after ten
seconds and a reader takes four to twenty, so this cannot happen where the fact is said — and
it does not need to: the words are in the record and reading them is free of any hurry.

What is never read and never guessed: **which two things**. They are handed over as things, not
as names in a sentence, because identity cannot be recovered from words and no later reading
repairs a confusion of two Annas.
"""
import json
from datetime import datetime, timezone

from terraweaver.store import run_script

SCHEMA = """
CREATE TABLE IF NOT EXISTS sentences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    words TEXT NOT NULL,
    said_at TEXT NOT NULL,
    task_id TEXT,
    read_as TEXT,              -- JSON of what a reader made of it, once it has been read
    link_id TEXT               -- the link it became, if it became one
);
CREATE INDEX IF NOT EXISTS idx_sentences_unread ON sentences(read_as);
"""


def say(world, subject, obj, words: str, task_id: str | None = None):
    """Write down the fact in the words it came in, and join the two things at once.

    The link is made immediately, untyped — the world's bare `related`, carrying the host's
    words as its description. The fact is in the world from that moment: joined, findable,
    countable, answerable. Typing it is an improvement on a fact that is already there, not a
    condition of it being there at all.

    This is the difference between a fact and a fact-in-waiting, and it is the whole lesson of
    the day. A sentence held in a side table until somebody could type it is a fact nothing can
    find, and if the reader never runs it is a fact that was never recorded. An untyped link is
    a poor link — it cannot supersede, cannot be asked about by type, has nothing to be checked
    against — and it is still a link. The world knows that these two are joined and what the
    host said about it, which is exactly what the host said and no less.
    """
    if not (words or "").strip():
        raise ValueError(
            "link(a, b, words) needs the fact in words — that is the whole of what it takes. "
            "Not a type, not a role, not which end is which: those are read from the words "
            "afterwards. \"Anna has worked at Brightwork since 2019\" is a fact; \"employment\" "
            "is a type, and choosing one is the thing this call exists to spare you.")
    _about_two(subject, obj, words)
    run_script(world.store.conn, SCHEMA)
    # `related_to` on purpose, and it is the honest one: it means nothing follows from this
    # link but the link itself, which is exactly true of a link nobody has read yet. Any other
    # nature would be a claim about what may be inferred, made before anybody knows what the
    # link is.
    #
    # The label is the sore point and is left as it is knowingly. A free link must carry one,
    # and an unread link has no word — `display_name` renders it "Tokyo is Japan's said", which
    # is nonsense. It is nonsense for a few minutes: the link is read at the close of the task
    # and becomes what it is. Choosing a better word would be inventing the very thing that has
    # not been read, and a word read as content is the failure measured all day.
    link = subject.relate(obj, "related", label="said", nature="related_to")
    link.describe(words.strip())
    cursor = world.store.conn.execute(
        "INSERT INTO sentences (subject_id, object_id, words, said_at, task_id, link_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (subject.id, obj.id, words.strip(), datetime.now(timezone.utc).isoformat(), task_id,
         link.id))
    world.store.conn.commit()
    return link


def _about_two(subject, obj, words: str) -> None:
    """A link is about two things. Said as one, it is probably about the thing, not the joining.

    Not refused — said. The commonest wrong move measured today was a fact about two things
    written as a description of one, and the commonest wrong move in the other direction was an
    account of one thing written onto the link between two. Both passed every check there was.
    The host knows which it meant; the world can only notice that the sentence names one thing
    and not the other, and say so while there is still somebody to say it to.
    """
    from terraweaver import matching, ontology

    said = matching.normalize(words)
    named = [t for t in (subject, obj)
             if matching.normalize(str(t.display_name())) in said
             or any(matching.normalize(w) in said
                    for w in str(t.display_name()).split() if len(w) > 3)]
    if len(named) >= 2:
        return
    if not named:
        ontology.note_hint(
            f"That names neither {subject.display_name()} nor {obj.display_name()}. A link is a "
            f"fact about the two together — say which is what to the other, in the words the "
            f"user used. Recorded as a link either way, and it will be read as one.")
        return
    missing = obj if named[0] is subject else subject
    ontology.note_hint(
        f"That reads as being about {named[0].display_name()} alone — "
        f"{missing.display_name()} is not in it. A link is a fact about the two together: what "
        f"one of them is to the other. If this is an account of {named[0].display_name()} "
        f"rather than of what joins them, it belongs on the thing: "
        f"{named[0].display_name()}.describe(...). Recorded as a link either way.")


def unread(world, limit: int = 100) -> list[dict]:
    """Sentences nobody has read yet."""
    run_script(world.store.conn, SCHEMA)
    rows = world.store.conn.execute(
        "SELECT id, subject_id, object_id, words, link_id FROM sentences WHERE read_as IS NULL "
        "ORDER BY id LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "subject_id": r[1], "object_id": r[2], "words": r[3], "link_id": r[4]}
            for r in rows]


def mark(world, sentence_id: int, read_as: dict, link_id: str | None = None) -> None:
    world.store.conn.execute(
        "UPDATE sentences SET read_as = ?, link_id = ? WHERE id = ?",
        (json.dumps(read_as), link_id, sentence_id))
    world.store.conn.commit()


def count(world) -> tuple[int, int]:
    """How many sentences are down, and how many are still unread."""
    run_script(world.store.conn, SCHEMA)
    said = world.store.conn.execute("SELECT count(*) FROM sentences").fetchone()[0]
    waiting = world.store.conn.execute(
        "SELECT count(*) FROM sentences WHERE read_as IS NULL").fetchone()[0]
    return said, waiting


SYSTEM = ("You place a fact in a record of relations. A relation joins two things and each end "
          "has a role. You answer with JSON and nothing else.")

ASK = """Two things are in a record of facts, and somebody has said how they are related.
Your task is to describe that relation, and nothing else.

    the first thing:   {a}   (a {a_is})
    the second thing:  {b}   (a {b_is})
    what was said:     {words}

{held}

A relation in this record is four things and no others. Give them.

**use** — the name of one of the relations listed above, when this is that same relation. Give
it and stop: a second word for an idea the record already holds answers for neither. Null when
none of them is this, and then give the four below.

**the roles** — `subject_is` and `object_is`: what each END of the relation IS, as a short noun
phrase a thing could be checked against. "a city that serves as a capital", not "Paris"; "the
country whose capital it is", not "France". When both ends hold the same role, give the same
word — two siblings are both siblings, and that sameness is the whole of what symmetry is here,
so there is no separate thing to say about it. `also_called`: up to four other words this
relation is said with, so the next person who says it another way lands here instead of making
a second word for it.

**what may stand there** — `subject_class` and `object_class`: what sort of thing may fill each
role, chosen from the classes this record has:

{classes}

Widely, not narrowly. A role written tight turns every honest fact into an alarm: a religion's
followers are people as well as bodies, so an affiliation takes both and not just one. Give
"any" when anything may stand there, and say nothing a first example taught you that a second
would contradict. These are watched, not enforced — a fact whose ends do not fit is reported
and kept, because a fact refused goes somewhere nothing can find it.

**how many** — `one_object` is true when the first end may have only one of the second AT ONE
MOMENT; `one_subject` is the same the other way. About one moment, never about a lifetime:
somebody has one employer now and many over a life, so that is true. A parent has several
children at once, so for a parent that is false.

**what follows** — `implies`, a list of what becomes true *in addition* when a link of this kind
is written. Only these words, and empty is a common and honest answer:

    "transitive"   A to B and B to C makes A to C. A part of a part is part of the whole.
                   A mother of a mother is not a mother.
    "inherits"     what holds of the second end holds of the first by virtue of this link.
                   A dog is a kind of mammal, so what is true of mammals is true of dogs.
                   A wheel is part of a car and is not a car.
    "identity"     the two are one and the same thing under two names — "Bombay is Mumbai".
                   A part is not the whole and a member is not the group.

**what it is** — `description`: one sentence saying what this kind of relation is, for somebody
who has never seen it. About the kind of link, not about these two things.

Then, about this one fact rather than about the relation:

**which end is which** — `subject` and `object`, by the names given at the top. This is the
whole of the direction; nothing else decides it. Do not name anything that is not one of those
two things.

**when** — `starts`, if what was said says so, in the words it said it ("2019", "June 2019",
"since she moved"). Null when nothing was said about when. Do not work one out: a date nobody
said cannot be told apart, later, from one somebody knew.

**Whether the fact is true is not part of this task and must not affect any answer.** This
record holds what somebody said, including what contradicts common knowledge: "London is the
capital of France" is described exactly as "Paris is the capital of France" would be — same
relation, same roles, London in the capital's role.

JSON only, these keys and no others:
{{"use": null,
  "subject_is": "...", "object_is": "...", "also_called": ["..."],
  "subject_class": "...", "object_class": "...",
  "one_object": true, "one_subject": true,
  "implies": [],
  "description": "...",
  "subject": "...", "object": "...", "starts": null}}"""


def classes_here(world) -> str:
    """The classes a role may name, so a reader picks one rather than inventing a word.

    Shown rather than remembered: a reader told to name a class and not shown which exist will
    write a reasonable word that is nobody's class, and the world then holds a condition it
    cannot check against anything.
    """
    names = sorted(n for n, c in world.classes.items() if not c._spec.get("relation"))
    return "    " + ", ".join(names) + ", or \"any\""


def held(world) -> str:
    """What the world already holds, so a reader joins rather than invents."""
    from terraweaver import relations

    lines = []
    for name, cls in sorted(world.classes.items()):
        rel = cls._spec.get("relation")
        if not rel:
            continue
        roles = (rel.get("roles") or [{}])[0]
        if not roles.get("name"):
            continue
        lines.append(f"    {name}: {roles['name']} ↔ {roles.get('inverse') or '?'}"
                     f" — {cls._spec.get('description', '')[:70]}")
    if not lines:
        return "The record holds no relations with named ends yet."
    return "Relations the record already holds:\n" + "\n".join(lines[:30])


def read_them(world, reader, limit: int = 100) -> dict:
    """Read the sentences nobody has read, and make each one a link. Called at the close.

    Everything that happens after the reading is the world as it already is: `define_relation`
    makes the type, `relate` writes the link, and periods, supersession and questions are the
    ones that were there. What is new is only where the type comes from — read out of the words
    rather than chosen by a host before it had anything to choose with.
    """
    from terraweaver import ontology

    tally = {"read": 0, "joined": 0, "defined": 0, "astray": 0, "failed": 0}
    for one in unread(world, limit):
        try:
            subject = world.store.load(one["subject_id"], world.classes)
            obj = world.store.load(one["object_id"], world.classes)
        except Exception:  # noqa: BLE001 - a thing that has gone is not a sentence we can read
            mark(world, one["id"], {"gone": True})
            continue
        if subject is None or obj is None:
            mark(world, one["id"], {"gone": True})
            continue
        try:
            said = reader.json(SYSTEM, ASK.format(
                words=one["words"],
                a=subject.display_name(), a_is=type(subject).__name__,
                b=obj.display_name(), b_is=type(obj).__name__,
                held=held(world), classes=classes_here(world)))
        except Exception:  # noqa: BLE001 - a reader that fails leaves the words for a later pass
            tally["failed"] += 1
            continue
        if not said:
            tally["failed"] += 1
            continue
        tally["read"] += 1
        kind = _type_for(world, said, tally)
        if kind is None:
            tally["failed"] += 1
            mark(world, one["id"], {**said, "no_type": True})
            continue
        # The roles must be given to the two things handed over. Given names that say nothing, a
        # reader once made "She" the subject of a fact about X and Y — a role given to somebody
        # who is not in the record. The two things are the one part of this the world is sure of.
        by_name = {subject.display_name(): subject, obj.display_name(): obj}
        near = by_name.get(said.get("subject"))
        far = by_name.get(said.get("object"))
        if near is None or far is None or near is far:
            near, far, = subject, obj
            tally["astray"] += 1
        link = None
        try:
            with ontology.stating("world"):
                link = near.relate(far, kind, starts=_when(said.get("starts")))
                _let_go_of_the_bare_one(world, one.get("link_id"))
        except Exception as wrong:  # noqa: BLE001 - the world's own refusals still stand
            # The bare link stays. A typing the world could not apply is a typing lost, not a
            # fact lost: the two are still joined and the host's words are still on it.
            mark(world, one["id"], {**said, "refused": str(wrong)[:200]})
            continue
        mark(world, one["id"], said, getattr(link, "id", None))
    return tally


def _let_go_of_the_bare_one(world, link_id: str | None) -> None:
    """The untyped link has been replaced by a typed one: end it, do not erase it.

    What was said is not unsaid. The bare link held the host's own words and the moment they
    were said; it stops holding where the typed one begins, and anybody asking what this was
    before it was typed still has it.
    """
    from terraweaver import ontology, timeutil

    if not link_id:
        return
    try:
        bare = world.store.load(link_id, world.classes)
    except Exception:  # noqa: BLE001
        return
    if bare is None or getattr(bare, "valid_until", None) is not None:
        return
    with ontology.trusted_writes(), ontology.stating("world"):
        bare.valid_until = timeutil.now()
        world.save(bare)


def _type_for(world, said: dict, tally: dict) -> str | None:
    """The relation this reading names — one already here, or one defined now."""
    from terraweaver import relations

    if said.get("use"):
        cls = world.classes.get(said["use"])
        if cls is not None and cls._spec.get("relation"):
            tally["joined"] += 1
            return cls._spec["relation"]["kind"]
    subject_is, object_is = said.get("subject_is"), said.get("object_is")
    if not subject_is:
        return None
    for name, cls in world.classes.items():
        rel = cls._spec.get("relation")
        roles = (rel or {}).get("roles") or [{}]
        if roles[0].get("name") == subject_is and roles[0].get("inverse") == object_is:
            tally["joined"] += 1
            return rel["kind"]
    grow = (world.extras or {}).get("define_relation")
    if grow is None:
        return None
    word = _one_word(subject_is) + "_of"
    try:
        made = grow(word, said.get("description") or f"{subject_is} and {object_is}",
                    nature=CLAIMS_NOTHING,
                    cardinality=_cardinality(said), over_time=False,
                    subject_is=subject_is, object_is=object_is,
                    subject=_class_named(world, said.get("subject_class")),
                    object=_class_named(world, said.get("object_class")))
        if "transitive" in (said.get("implies") or []):
            # The one rule of `implies` this world already acts on: a read follows the chain.
            # Written onto the type rather than asked of the nature, because the nature is not
            # where it belongs and one of the two has to give.
            made._spec["relation"]["transitive"] = True
        for word_for_it in (said.get("also_called") or [])[:4]:
            if isinstance(word_for_it, str) and word_for_it.strip():
                made._spec["relation"].setdefault("labels", []).append(word_for_it.strip())
    except Exception:  # noqa: BLE001 - a word already taken is a word to join, not to force
        cls = world.classes.get("".join(p[:1].upper() + p[1:] for p in word.split("_")))
        return cls._spec["relation"]["kind"] if cls is not None else None
    tally["defined"] += 1
    return made._spec["relation"]["kind"]


# `nature` is a field of the world as it stands and not of the relation as it was settled
# (`docs/relation-properties.md`, `sketch/relation_class.py`). The argument that removed it: a
# nature was meant to bundle properties and instead repeated them — cardinality said again in
# other words — and what is left when the repetition is taken out is a **set of inference
# rules**, which is `implies` and which one word cannot carry. So nothing here works one out.
# The field is filled with the value that claims nothing, and the rules the reader gives are
# kept where they belong: `transitive` on the type, the rest waiting for `implies` to exist.
CLAIMS_NOTHING = "related_to"


def _class_named(world, said):
    """The class a reader named, if this world has it. Watched, never enforced.

    `define_relation` takes the ends as classes and does not hold a link to them — the comment
    there says why, and it was measured: ends declared from the first example refuse the second,
    and the host answers by defining a second type with the class names in it. So this is
    evidence for the checking and not a promise, and a word that names no class is simply not
    taken rather than being made into one.
    """
    if not said or str(said).strip().lower() in ("any", "anything", "thing", ""):
        return None
    return world.classes.get(str(said).strip())


def _cardinality(said: dict) -> str:
    one_object, one_subject = bool(said.get("one_object")), bool(said.get("one_subject"))
    return {(True, True): "one-to-one", (True, False): "many-to-one",
            (False, True): "one-to-many", (False, False): "many-to-many"}[(one_object, one_subject)]


def _one_word(role: str) -> str:
    words = (role or "").strip().lower().replace("-", "_").split()
    while words and words[0] in ("a", "an", "the"):
        words = words[1:]
    return words[-1] if words else "related"


def _when(said):
    """A date the words gave, or None. Nothing is invented from a phrase nobody can read."""
    from terraweaver import timeutil

    if not said or not str(said).strip():
        return None
    try:
        return timeutil.told(str(said))[0]
    except Exception:  # noqa: BLE001 - a date nobody can read is no date
        return None
