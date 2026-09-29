"""Every way a later telling meets an earlier one, in one place.

These behaviours were fixed one at a time over a day, and fixing one silently undid another
twice: the invented end date was removed in the morning and left the correction announcing
itself and doing nothing, which was found in the evening by reading a world rather than by any
test. They are pinned together here so that the next change to any of them has to face all of
them at once.

Run: .venv/bin/python tests/test_superseding.py
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world  # noqa: E402

from terraweaver import authoring
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def world(**types):
    """A world with the types this case needs, and a task open to record into.

    The value is the cardinality, which is the whole of what says how many may hold — and it says
    it **per end**: "many-to-one" is one object per subject at a time, "one-to-many" is one subject
    per object. It used to be a boolean called `over_time` that set both ends from one word, which
    is why every type here limited an end nobody meant to limit.
    """
    work = Path(tempfile.mkdtemp(prefix="tw-sup-"))
    rt = open_world(str(work / "w.db"))
    for kind, cardinality in types.items():
        rt.world.extras["define_relation"](
            kind, f"what {kind.replace('_', ' ')} means here, for the test", cardinality=cardinality)
    rt.start_task("k", "record what the user said, more than once about one thing", "recording")
    return rt


def ran(rt, code):
    got = rt.run(code, "k")
    return (got["output"] or "").strip(), got


def settle_direction(rt):
    """Take the read-back the close asks for first — not what these tests are about."""
    rt.finish_task("k")


def main() -> int:
    # --- a second telling with no date: the earlier ends some time before now ---
    rt = world(hq_in="many-to-one")
    out, _ = ran(rt, 'org = Thing.ensure(name="Acme Corp", nature="agent")\n'
                     'org.set_hq_in(Thing.ensure(name="Dublin", nature="place"))\n'
                     'org.set_hq_in(Thing.ensure(name="Tallinn", nature="place"))\n'
                     'print([t.display_name() for t in org.related("hq_in")])\n'
                     'print([t.display_name() for t in org.related("hq_in", any_time=True)])\n'
                     'print([getattr(l, "until_is", None) '
                     'for l in org.relations("hq_in", any_time=True)])')
    holds, ever, ends = out.splitlines() if out.count("\n") == 2 else ("", "", "")
    check("the later telling holds", holds == "['Tallinn']", holds)
    check("and the earlier one is still in the record", "Dublin" in ever and "Tallinn" in ever, ever)
    # The earlier one is ended, because one can hold at a time and two periods may not overlap —
    # and the end says *before now*, not a day. Nobody said when it moved, and a day written here
    # could not be told apart later from one somebody knew. Left un-ended instead, as it was while
    # "a correction" was a category of its own, the thing had two head offices and every count
    # agreed it was fine.
    check("and its end is before now rather than a day nobody said",
          ends == "[None, 'before']", ends)

    # --- a handover: one at a time, and the new one's start is where the last ends ---
    rt = world(chairs="one-to-many")
    out, _ = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                     'Person.new(full_name="Yasser Arafat").set_chairs(org,  starts=date(1969, 2, 3))\n'
                     'Person.new(full_name="Mahmoud Abbas").set_chairs(org,  starts=date(2004, 11, 11))\n'
                     'for l in sorted(org.relations("chairs_of", any_time=True), key=lambda x: x.starts):\n'
                     '    print(f"{l.subject.display_name()} {l.starts.date()} -> {l.until.date() if l.until else None}")')
    check("a handover ends the first where the second begins",
          "Yasser Arafat 1969-02-03 -> 2004-11-11" in out, out.replace("\n", " | "))
    check("and the second one is open", "Mahmoud Abbas 2004-11-11 -> None" in out, out.replace("\n", " | "))

    # --- a link that holds needs no start ---
    rt = world(manages="one-to-many", part_of="many-to-one")
    _, got = ran(rt, 'a = Person.new(full_name="A One")\nb = Thing.new(name="B Two")\n'
                     'a.set_manages(b)')
    # Recorded, not refused, and that is the settled end of three attempts. Refusing turned away
    # sixty facts in a 455-fact run; taking now() by itself dated a fact nobody dated; refusing
    # while offering now() turned away the same facts again, because a raise stops the block and
    # takes the rest of the batch with it — one un-dated marriage cost twenty-eight lines.
    # A time belongs to an event, and Event.start_time is required. A link that merely holds
    # needs no beginning: supersession orders an undated pair by which was told last.
    check("a one-at-a-time link is made without a start", got["ok"],
          str(got.get("error"))[:120])
    _, got = ran(rt, 'dept = Thing.new(name="Newsroom")\ndept.set_part_of(b)')
    check("a part_of link needs no start", got["ok"], str(got.get("error"))[:80])

    # Nothing is demanded on the way in, and on the way out nothing rests on the order things
    # arrived in: the earlier one is ended — some time before now, since nobody said when — so what
    # holds is read from the periods like everything else. It used to rest on the order, because a
    # type could say "one ever", which has no periods to decide with.
    rt = world(led_by="many-to-one")
    out, got = ran(rt, 'boss = Person.new(full_name="The Boss")\n'
                       'boss.set_led_by(Thing.new(name="Told First"))\n'
                       'boss.set_led_by(Thing.new(name="Told Second"))\n'
                       'print([r.object.name for r in boss.relations("led_by")])')
    said = " ".join(got.get("hints", []))
    check("with no dates, the later telling holds", "Told Second" in out and "Told First" not in out,
          out.replace("\n", " | ")[:100])
    check("and the world says the earlier one is ended, without inventing a day",
          "some time before now" in said, said[:140] or "(no hint)")
    check("and asks when it changed, since that decided a boundary",
          any("when_it_changed" in q or "When did it change" in q
              for q in (got.get("questions") or []) + (got.get("ask_now") or [])),
          str(got.get("questions"))[:140])
    dated = world(led_by="many-to-one")
    _, got = ran(dated, 'boss = Person.new(full_name="The Boss")\n'
                        'boss.set_led_by(Thing.new(name="Told First"),  '
                        'starts=date(2019, 1, 1))\n'
                        'boss.set_led_by(Thing.new(name="Told Second"),  '
                        'starts=date(2022, 1, 1))\n'
                        'print(len(boss.relations("led_by")))')
    check("and puts the boundary on the date when somebody gave one",
          "some time before now" not in " ".join(got.get("hints", []))
          and "2022" in " ".join(got.get("hints", [])),
          " ".join(got.get("hints", []))[:140])

    # --- a date given earlier than the standing one is a conflict, not a handover ---
    rt = world(chairs="one-to-many")
    _, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                     'Person.new(full_name="Later").set_chairs(org,  starts=date(2024, 1, 1))\n'
                     'Person.new(full_name="Earlier").set_chairs(org,  starts=date(2020, 1, 1))')
    check("a start before the standing one is refused", not got["ok"], str(got.get("error"))[:70])

    # --- the same moment, taken once, is a handover and not an overlap ---
    rt = world(chairs="one-to-many")
    out, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\nt = now()\n'
                       'Person.new(full_name="First").set_chairs(org,  starts=t)\n'
                       'Person.new(full_name="Second").set_chairs(org,  starts=t)\n'
                       'print([p.display_name() for p in org.related("chairs_of")])')
    check("one moment passed to both hands over", out == "['Second']", out or str(got.get("error"))[:70])

    # --- the other shape: the subject changes, and the world can only count ---
    rt = world(led_by="many-to-one")
    out, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                       'Person.new(full_name="One").set_led_by(org)\n'
                       'Person.new(full_name="Two").set_led_by(org)\n'
                       'print(len(org.related("led")))')
    check("two subjects on one object both stand, since nothing said otherwise", out == "2", out)
    check("and the world asks about it once, naming the fix",
          any("one_per_object" in q for q in (got.get("questions") or [])),
          str(got.get("questions"))[:110])
    out, _ = ran(rt, 'led_by.one_per_object = True\n'
                     'Person.new(full_name="Three").set_led_by(org)\n'
                     'print([p.display_name() for p in org.related("led")])')
    check("and once it is said, the later one supersedes", out == "['Three']", out)

    # --- a link written from the wrong end is a different fact, and the world had the check ---
    # `relations.verify` worked this out from the day it was written and nothing called it, so
    # the world noticed a type running both ways and told nobody.
    rt = world(author_of="many-to-one")
    ran(rt, 'p1 = Person.new(full_name="Ursula K. Le Guin")\n'
            'b1 = Thing.ensure(name="A Wizard of Earthsea", nature="object")\n'
            'p1.set_author_of(b1)\n'
            'b2 = Thing.ensure(name="Starship Troopers", nature="object")\n'
            'p2 = Person.new(full_name="Robert A. Heinlein")\n'
            'b2.set_author_of(p2)\n'
            'for x in (p1, b1, b2, p2): x.describe("mentioned while recording")\n'
            'for l in AuthorOf.all(limit=None): l.describe("as the user stated it")')
    settle_direction(rt)
    left = str(rt.finish_task("k"))
    check("a task does not close over a type written both ways",
          left.startswith("Not closed") and "both ways" in left, left[:90])
    check("and at a tie it names both rather than accusing one",
          "Ursula" in left and "Starship" in left and "nothing says which is right" in left,
          left[:150])

    # --- one value per subject is counted per type, not across a thing's whole life ---
    # Held in one set, a person with a birthplace and a book lost the book: both types say one
    # value per subject, and the second link of the second type was taken for a second value
    # of the first. It read as "the fact is not in the world" while asking for it by name
    # returned it with its period still open.
    rt = world(born_in="many-to-one", wrote="many-to-one")
    out, _ = ran(rt, 'p = Person.new(full_name="Ursula K. Le Guin")\n'
                     'p.set_born_in(Thing.ensure(name="Portland", nature="place"))\n'
                     'p.set_wrote(Thing.ensure(name="Earthsea", nature="object"))\n'
                     'print(sorted(type(l).__name__ for l in p.relations()))')
    check("two links of two one-value types both stand",
          out == "['BornIn', 'Wrote']", out)

    # --- a type that keeps ending the last one on the same thing is a type in doubt ---
    # `citizen_of` was declared one citizen per country, so every American ended the last
    # American's citizenship: twelve links to the United States, six still holding.
    rt = world(citizen_of="one-to-many")
    out, got = ran(rt, 'usa = Thing.ensure(name="United States", nature="place")\nt = now()\n'
                       'for n in ("A One", "B Two", "C Three", "D Four", "E Five"):\n'
                       '    Person.new(full_name=n).set_citizen_of(usa,  starts=t)\n'
                       'print(len(usa.related("citizen")))')
    check("one per object leaves only the last", out == "1", out)
    check("and the world asks whether it can have several at once",
          any("each ending the last" in q for q in (got.get("questions") or [])),
          str(got.get("questions"))[:110])
    # Withdrawing the premise withdraws the conclusion. The ends were the world's, drawn from
    # "there is one at a time"; told otherwise, it takes them back. What a person ended stays
    # ended, because that was said rather than worked out.
    out, got = ran(rt, 'citizen_of.one_per_object = False\n'
                       'print(len(usa.related("citizen")))')
    check("and saying it can brings back the ones the world ended", out == "5", out)
    check("and it says what it took back",
          any("hold again" in h for h in (got.get("hints") or [])), str(got.get("hints"))[:110])

    # --- one moment on all of them, so the order they arrived is what is left to go on ---
    # Taking the moment once is what the world asks for, and it makes every fact in a breath
    # share a date. Which of them holds is then a question the dates cannot answer, and the
    # record answers it: `stated_at` is kept per statement and rises with every one.
    rt = world(chairs="one-to-many")
    out, _ = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\nt = now()\n'
                     'for n in ("First", "Second", "Third"):\n'
                     '    Person.new(full_name=n).set_chairs(org,  starts=t)\n'
                     'print([p.display_name() for p in org.related("chairs_of")])\n'
                     'print([p.display_name() for p in org.related("chairs_of", any_time=True)])')
    holds, ever = out.splitlines() if "\n" in out else (out, "")
    check("with one date on all of them, the last told holds", holds == "['Third']", holds)
    check("and the rest are there, latest first",
          ever == "['Third', 'Second', 'First']", ever)

    print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
                  else "all superseding tests passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
