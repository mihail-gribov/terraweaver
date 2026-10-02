"""Fill one of everything, then take the world apart and put it back together three ways.

The two-layer design rests on one promise: the images are a reading of the record, and the
record is what is true. It had been checked on fixtures, and the first real world put through
it came back twelve names short. So this fills every kind of value the ontology can declare and
every structure the world keeps — one instance apiece, as full as it goes — and then does the
three things that can lose it:

  rebuild  the images thrown away and built again from the statements alone
  reopen   the database closed and opened again, in case something lived only in memory
  move     the files copied elsewhere and opened there, in case something lived outside them

What the last two keep and the first one does not is not a bug but the boundary, and the test
says where it runs: the side tables are not statements, so a rebuild leaves them alone rather
than restoring them. That distinction is the point of checking all three.

Run: .venv/bin/python tests/test_round_trip.py
"""
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import terraweaver
from terraweaver import periods as periods_mod, selves, texts as texts_mod
from terraweaver.runtime import WorldRuntime

KEY = "host"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def open_world(work: Path) -> WorldRuntime:
    """A world at this place, with whatever types have been grown there."""
    return terraweaver.open_world(str(work / "world.db"))


# --- one of every kind of value the ontology can declare ---
# Written as a grown spec rather than through `define`, because several of these shapes the
# host surface doesn't offer and a test that went through it would quietly skip them.
SPECIMEN = {
    "name": "Specimen",
    "description": "A thing made to carry one of every kind of value the world can hold.",
    "identified_by": "name",
    "attributes": [
        {"name": "name", "type": "str", "required": True, "description": "What it is called."},
        {"name": "count", "type": "int", "description": "A whole number of something."},
        {"name": "weight", "type": "float", "description": "A number with a fraction."},
        {"name": "settled", "type": "bool", "description": "Whether it is so or not."},
        {"name": "when", "type": "datetime", "description": "A moment it is tied to."},
        {"name": "site", "type": "url", "description": "Where it is on the web."},
        {"name": "reach", "type": "email", "description": "The address it is written to at."},
        {"name": "ring", "type": "phone", "description": "The number it is called on."},
        {"name": "coordinates", "type": "dict", "description": "Where it is, as lat and lon."},
        {"name": "shape", "type": "enum[round, square, other]", "default": "other",
         "description": "Which of three shapes it is."},
        {"name": "labels", "type": "list[str]", "description": "Several words about it."},
        {"name": "owner", "type": "ref:Person", "description": "Whose it is."},
        {"name": "about", "type": "ref:any", "description": "What it concerns, of any class."},
        {"name": "held_by", "type": "list[ref:Person]", "description": "Who has had it."},
        {"name": "touching", "type": "list[ref:any]", "description": "What it bears on."},
        {"name": "notes", "type": "list[text]", "changes": False,
         "description": "How it has been written about, in whoever's words."},
        {"name": "descriptions", "type": "list[text]", "changes": False,
         "description": "How it has been described, in whoever's words."},
        {"name": "tags", "type": "list[str]", "description": "Loose ties to other things."},
    ],
    "methods": [],
}



FIRST = """
t = now()
world.attribute(Person, "email", "The address this person reads their mail at.", type="email")
world.attribute(Person, "phone", "The number this person answers.", type="phone")
world.attribute(Thing, "website", "Where this thing is on the web.", type="domain")
anna = Person.new(name="Anna Weber", aliases=["Anna W."], email="anna@example.org",
                  phone="+49 30 000001")
mila = Person.new(name="Mila Toft", email="mila@example.org")
town = Thing.new(name="Bremen", nature="place")
firm = Thing.new(name="Brightwork", aliases=["BW"], website="https://brightwork.example",
                 nature="agent")
meeting = Event.new(title="First interview", about=firm,
                    start_time=datetime(2026, 2, 10, 14, 0), end_time=datetime(2026, 2, 10, 15, 0))
thing = Thing.new(name="The corner desk", nature="object", aliases=["the desk"])
one = Specimen.new(name="One", count=3, weight=1.5, settled=True,
                   when=datetime(2020, 5, 4, 9, 30), site="https://example.org/one",
                   reach="one@example.org", ring="+7 900 000-00-01",
                   coordinates={"lat": 1.0, "lon": 2.0}, shape="round",
                   labels=["first", "second"], owner=anna, about=firm,
                   held_by=[anna, mila], touching=[firm, town], starts=date(2019, 1, 1))
two = Specimen.new(name="Two", shape="square", count=1)
three = Specimen.new(name="Three", shape="other")
print("entities in")
"""

SECOND = """
t = now()
anna = Person.get(name="Anna Weber")
mila = Person.get(name="Mila Toft")
firm = Thing.get(name="Brightwork")
town = Thing.get(name="Bremen")
meeting = Event.get(title="First interview")
thing = Thing.get(name="The corner desk")
one, two, three = (Specimen.get(name=n) for n in ("One", "Two", "Three"))

for it, said in ((anna, "the person the user talks about most"),
                 (mila, "someone Anna works with"),
                 (firm, "where Anna hopes to work"),
                 (town, "the city the office is in"),
                 (meeting, "the first of the interviews"),
                 (thing, "a thing with no class of its own"),
                 (two, "the second specimen, plainer than the first"),
                 (three, "the third, made to take the link over")):
    it.describe(said)
one.describe("what the user said about it, on a day they named", when=date(2021, 3, 2))
one.describe("something only half-heard", tentative=True)
one.describe("true until the year turns", until=date(2026, 12, 31))

anna.tag("colleague", "berlin")
firm.tag("employer")
one.tag("kept", "looked at", starts=t)

# One word of each shape a link can take: one-to-many from either end, many-to-many with the
# same role at both ends, one-to-one, and a word with attributes of its own.
world.define_relation("works_at", "a person working for an employer", cardinality="many-to-one",
                      subject_is="a person who works", object_is="their employer",
                      attributes=[{"name": "role", "type": "str", "description": "What they do there."}])
world.define_relation("lives_in", "a person living in a place", cardinality="many-to-one",
                      subject_is="a resident", object_is="the place they live")
world.define_relation("knows", "two people who know each other", cardinality="many-to-many",
                      subject_is="an acquaintance", object_is="an acquaintance")
world.define_relation("owns", "a person owning a thing", cardinality="one-to-many",
                      subject_is="the owner", object_is="what they own")
world.define_relation("attends", "a person taking part in an event", cardinality="many-to-many",
                      subject_is="a participant", object_is="the event")
world.define_relation("part_of", "a place inside a larger one", cardinality="many-to-one",
                      subject_is="the part", object_is="the whole")
world.define_relation("stands_beside", "one specimen standing next to another, one at a time",
                      cardinality="one-to-one", subject_is="the near one", object_is="the far one")

held = anna.set_works_at(firm, starts=date(2018, 4, 1))
held.role = "engineer"
held.describe("as the user put it: she has been there since spring")
anna.set_lives_in(town, starts=t)
anna.set_knows(mila, starts=t)
anna.set_owns(thing, starts=t)
anna.set_attends(meeting, starts=t)
district = Thing.new(name="Neustadt", nature="place")
district.describe("the part of the city she is looking in")
district.set_part_of(town, starts=t)
loose = thing.relate(firm, "related", label="bought_from", starts=t)
one.set_stands_beside(two, starts=t)
print("links in")
"""


THIRD = """
one = Specimen.get(name="One")
world.pin("one", one, "the specimen this task is about", keep=False)
world.pin("anna", Person.get(name="Anna Weber"), "the person the task is about", keep=True)
one.count = 4
one.shape = "square"
print("pinned")
"""


def grow(work: Path) -> None:
    """Specimen is written as a grown type before the world opens, which is how one really arrives.

    Defining the class in place instead left it out of `world.specs`, and every list slot on it
    was then read back as a single value — the last tag, a list of raw references. That is not a
    fault in the world; it is what a class the assembler has never been told about looks like.
    """
    import json

    (work / "grown").mkdir(parents=True, exist_ok=True)
    (work / "grown" / "Specimen.json").write_text(json.dumps(SPECIMEN, indent=2))


def fill(rt: WorldRuntime, work: Path) -> None:
    """One instance of every structure, each as full as the world lets it be."""
    rt.start_task(KEY, "put one instance of every kind of thing into this world", "recording")
    made = rt.run(FIRST, KEY)
    if not made["ok"]:
        raise SystemExit(f"the fill did not go in: {made.get('error')}\n{made.get('output', '')}")
    handed = rt.run(SECOND, KEY)
    if not handed["ok"]:
        raise SystemExit(f"the second half did not go in: {handed.get('error')}")

    # Names pinned for this session and beyond it, and a value written twice so it has a history.
    pinned = rt.run(THIRD, KEY)
    if not pinned["ok"]:
        raise SystemExit(f"the pins did not go in: {pinned.get('error')}")

    world = rt.world
    # A name two people answer to, settled by hand — which is what writes a name choice down.
    rt.run('Person.new(name="Sam Lee", email="sam1@example.org")\n'
           'Person.new(name="Sam Lee", email="sam2@example.org")\n'
           'print("two of them")', KEY)
    asking = rt.run('Person.ensure(name="Sam Lee")\nprint("which one?")', KEY)
    if world.pending is not None:
        world.settle(world.pending, world.find(world.classes["Person"], name="Sam Lee")[0])

    # A task dropped part-way, which is the one kind that leaves a statement behind: the note
    # saying why. A rebuild that read a Task out of the record got that note and nothing else.
    rt.finish_task(KEY, abandon="stopping here on purpose, to leave one task dropped")
    rt.start_task(KEY, "carry on filling this world with one of everything", "recording")

    # What the files say about the two parties, and the note that they have been read.
    (work / "USER.md").write_text("---\nname: Nadia Ivanov\n---\nThe person this world is for.\n")
    (work / "soul.md").write_text("---\nname: Weaver\n---\nThe assistant that keeps it.\n")
    selves.refresh(world, work)

    # The structures no host call reaches, put in by hand so the round trip covers them too.
    world.questions.raise_(world.get(world.classes["Specimen"], name="Two"), "named_elsewhere",
                           "Is Two the same specimen as the one called Second?",
                           options=["the same", "separate"])
    asked = world.questions.raise_(world.get(world.classes["Specimen"], name="Three"),
                                   "named_elsewhere", "And is Three a fourth one?",
                                   options=["the same", "separate"])
    asked.answer("separate")
    world.procedures.define("beside", "beside(name)",
                            "return Specimen.get(name=name).related('stands_beside')",
                            "asked for often enough to be worth a name")
    world.meanings.refresh(world)
    texts_mod.rebuild(world)
    periods_mod.rebuild(world)
    world.usage.record(world.get(world.classes["Specimen"], name="One"))


def picture(rt: WorldRuntime) -> dict:
    """Everything the world can be asked for, in a shape two runs can be compared by."""
    world = rt.world
    seen: dict = {"values": {}, "links": [], "descriptions": {}, "tags": {}, "periods": {}}
    for name, cls in sorted(world.classes.items()):
        for entity in world.all(cls, limit=None, history=True):
            said = _name_of(entity)
            key = f"{name}:{said}"
            if cls._spec.get("relation"):
                seen["links"].append((name, _name_of(getattr(entity, "subject", None)),
                                      _name_of(getattr(entity, "object", None)),
                                      str(getattr(entity, "label", None)),
                                      str(getattr(entity, "valid_from", None)),
                                      str(getattr(entity, "valid_until", None))))
                continue
            held = {}
            for attr in cls._spec.get("attributes", []):
                if "derived" in attr or attr["name"] in ("descriptions", "tags"):
                    continue
                held[attr["name"]] = _plain(getattr(entity, attr["name"], None))
            seen["values"][key] = held
            seen["descriptions"][key] = sorted(_plain(d) for d in (
                getattr(entity, "descriptions", None) or []))
            seen["tags"][key] = sorted(str(t) for t in (getattr(entity, "tags", None) or []))
            seen["periods"][key] = (str(getattr(entity, "valid_from", None)),
                                    str(getattr(entity, "valid_until", None)))
    seen["links"].sort()
    return seen


def aside(rt: WorldRuntime) -> dict:
    """The structures that are not statements: kept beside the record, not derived from it."""
    world = rt.world
    rows = {}
    for table in ("comments", "questions", "world_variables", "name_choices", "procedures",
                  "meanings", "value_history", "entity_access", "self_files", "texts", "said",
                  "periods", "runs", "subjects", "instances"):
        try:
            rows[table] = world.store.conn.execute(f"SELECT count(*) FROM '{table}'").fetchone()[0]
        except Exception:
            rows[table] = None
    return rows


def _name_of(entity) -> str:
    if entity is None:
        return "None"
    for attr in ("name", "full_name", "title", "stated"):
        said = getattr(entity, attr, None)
        if said:
            return str(said)
    return str(getattr(entity, "id", entity))


def _plain(value):
    if isinstance(value, list):
        return sorted((_plain(v) for v in value), key=repr)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in sorted(value.items())}
    if hasattr(value, "id") and not isinstance(value, (str, int, float, bool)):
        return f"->{_name_of(value)}"
    return str(value)


def compare(what: str, before: dict, after: dict) -> None:
    for part in sorted(before):
        same = before[part] == after[part]
        detail = ""
        if not same and isinstance(before[part], dict):
            detail = "; ".join(
                f"{k}: {before[part].get(k)!r} -> {after[part].get(k)!r}"
                for k in sorted(set(before[part]) | set(after[part]))
                if before[part].get(k) != after[part].get(k))[:4000]
        elif not same:
            gone = [x for x in before[part] if x not in after[part]]
            new = [x for x in after[part] if x not in before[part]]
            detail = f"lost {gone}, gained {new}"[:400]
        check(f"{what} keeps {part}", same, detail)


def check_the_user_is_not_merged_away() -> None:
    """The self file names the user; the host records facts about them under the same name.

    They are the same person and a rebuild says so. What matters is which of the two ids the
    one image keeps: anything but `person:user` and the world comes back not knowing whose it
    is — no owner, an assistant belonging to nobody, and a person no lookup reaches.
    """
    work = Path(tempfile.mkdtemp(prefix="tw-parties-"))
    rt = open_world(work)
    rt.start_task(KEY, "record what the user said about her own week", "recording")
    rt.run('anna = Person.new(name="Anna Weber")\n'
           'anna.describe("the person this is all about")\n'
           'print("in")', KEY)
    # The file comes second on purpose. The other way round the world sees the duplicate as it
    # is written and asks which one is meant, and there is nothing left to merge — so the only
    # order in which two subjects ever reach a rebuild under one name is this one.
    (work / "USER.md").write_text("---\nname: Anna Weber\n---\nThe person this world is for.\n")
    selves.refresh(rt.world, work)
    rt.world.rebuild()
    owner = rt.world.owner
    check("a rebuild does not merge the user away",
          getattr(owner, "id", None) == rt.world.USER_ID,
          f"owner is {owner!r}")
    check("and the one person left answers to what both said",
          owner is not None and owner.name == "Anna Weber"
          and len(owner.descriptions or []) == 2,
          f"{getattr(owner, 'name', None)!r}, {getattr(owner, 'descriptions', None)!r}")
    check("and the assistant still belongs to them",
          getattr(getattr(rt.world.me, "owner", None), "id", None) == rt.world.USER_ID)
    rt.world.store.conn.close()
    shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="tw-trip-"))
    grow(work)
    rt = open_world(work)
    fill(rt, work)

    before, sides = picture(rt), aside(rt)
    counts = {k: len(v) for k, v in before.items()}
    check("every kind of structure has something in it",
          counts["values"] >= 8 and counts["links"] >= 5
          and sum(1 for v in before["descriptions"].values() if v) >= 6
          and sum(1 for v in before["tags"].values() if v) >= 2, str(counts))
    check("and so does every side table",
          all(sides[t] for t in ("comments", "questions", "world_variables", "procedures",
                                 "meanings", "value_history", "entity_access", "texts", "said",
                                 "subjects", "instances")),
          str({k: v for k, v in sides.items() if not v}))

    # --- the images thrown away and built again from the statements alone ---
    rt.world.rebuild()
    compare("a rebuild", before, picture(rt))
    after_sides = aside(rt)
    moved_on = {t: (sides[t], after_sides[t]) for t in sides
                if sides[t] and after_sides[t] != sides[t]}
    check("a rebuild leaves the side tables alone",
          all(after_sides[t] >= sides[t] for t in sides if sides[t]),
          str({t: (sides[t], after_sides[t]) for t in sides if sides[t]
               and after_sides[t] < sides[t]}))
    check("a rebuild changes no side table but the periods it derives",
          set(moved_on) <= {"periods", "texts", "said"}, str(moved_on))

    # --- the database closed and opened again ---
    rt.world.store.conn.close()
    again = open_world(work)
    compare("reopening", before, picture(again))
    reopened_sides = aside(again)
    check("reopening keeps the side tables",
          all(reopened_sides[t] >= sides[t] for t in sides if sides[t]),
          str({t: (sides[t], reopened_sides[t]) for t in sides if sides[t]
               and reopened_sides[t] < sides[t]}))
    check("and the procedure it was taught",
          again.world.procedures.get("beside") is not None)
    check("and the name pinned to outlive the session",
          "anna" in again.variables.names(),
          str(sorted(again.variables.names())))
    check("and the question left open",
          any("same specimen" in q.text for q in again.world.questions.open_(limit=20)))
    check("and the two parties the world is between",
          getattr(again.world.owner, "id", None) == again.world.USER_ID
          and getattr(getattr(again.world.me, "owner", None), "id", None) == again.world.USER_ID,
          f"owner={again.world.owner!r}, me.owner={getattr(again.world.me, 'owner', None)!r}")

    # --- the files moved somewhere else and opened there ---
    again.world.store.conn.close()
    elsewhere = Path(tempfile.mkdtemp(prefix="tw-moved-"))
    shutil.rmtree(elsewhere)
    shutil.copytree(work, elsewhere)
    moved = open_world(elsewhere)
    compare("moving the files", before, picture(moved))
    check("moving the files keeps the side tables",
          all(aside(moved)[t] >= sides[t] for t in sides if sides[t]))

    check_the_user_is_not_merged_away()

    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(elsewhere, ignore_errors=True)
    print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
                  else "all round-trip tests passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
