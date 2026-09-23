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

from terraweaver import authoring
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def world(**types):
    """A world with the types this case needs, and a task open to record into."""
    work = Path(tempfile.mkdtemp(prefix="tw-sup-"))
    rt = WorldRuntime(str(work / "w.db"), fixture="job_search", rebuild=True)
    made = authoring.install(rt.world, work / "grown")
    for kind, over_time in types.items():
        made.define_relation(kind, f"what {kind.replace('_', ' ')} means here, for the test",
                             nature="related_to", cardinality="many-to-one", over_time=over_time)
    rt.start_task("k", "record what the user said, more than once about one thing", "recording")
    return rt


def ran(rt, code):
    got = rt.run(code, "k")
    return (got["output"] or "").strip(), got


def settle_direction(rt):
    """Take the read-back the close asks for first — not what these tests are about."""
    rt.finish_task("k")


def main() -> int:
    # --- a correction: one value and no more, and no date is invented ---
    rt = world(hq_in=False)
    out, _ = ran(rt, 'org = Thing.ensure(name="Acme Corp", nature="agent")\n'
                     'org.relate(Thing.ensure(name="Dublin", nature="place"), "hq_in")\n'
                     'org.relate(Thing.ensure(name="Tallinn", nature="place"), "hq_in")\n'
                     'print([t.display_name() for t in org.related("hq_in")])\n'
                     'print([t.display_name() for t in org.related("hq_in", any_time=True)])\n'
                     'print([l.until for l in org.relations("hq_in", any_time=True)])')
    holds, ever, ends = out.splitlines() if out.count("\n") == 2 else ("", "", "")
    check("a correction leaves the later one holding", holds == "['Tallinn']", holds)
    check("and the earlier one still in the record", "Dublin" in ever and "Tallinn" in ever, ever)
    check("and invents no end date for it", ends.count("None") == 2, ends)

    # --- a handover: one at a time, and the new one's start is where the last ends ---
    rt = world(chairs=True)
    out, _ = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                     'Person.new(full_name="Yasser Arafat").relate(org, "chairs", starts=date(1969, 2, 3))\n'
                     'Person.new(full_name="Mahmoud Abbas").relate(org, "chairs", starts=date(2004, 11, 11))\n'
                     'for l in sorted(org.relations("chairs_of", any_time=True), key=lambda x: x.starts):\n'
                     '    print(f"{l.subject.display_name()} {l.starts.date()} -> {l.until.date() if l.until else None}")')
    check("a handover ends the first where the second begins",
          "Yasser Arafat 1969-02-03 -> 2004-11-11" in out, out.replace("\n", " | "))
    check("and the second one is open", "Mahmoud Abbas 2004-11-11 -> None" in out, out.replace("\n", " | "))

    # --- what the nature decides ---
    rt = world()
    _, got = ran(rt, 'a = Person.new(full_name="A One")\nb = Organization.new(name="B Two")\n'
                     'a.relate(b, "authority", label="manager")')
    check("a related_to link that changes will not be made without a start",
          not got["ok"] and "when it began is part of the fact" in str(got.get("error")),
          str(got.get("error"))[:80])
    _, got = ran(rt, 'dept = Organization.new(name="Newsroom")\ndept.relate(b, "part_of")')
    check("a part_of link needs no start", got["ok"], str(got.get("error"))[:80])

    # --- a date given earlier than the standing one is a conflict, not a handover ---
    rt = world(chairs=True)
    _, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                     'Person.new(full_name="Later").relate(org, "chairs", starts=date(2024, 1, 1))\n'
                     'Person.new(full_name="Earlier").relate(org, "chairs", starts=date(2020, 1, 1))')
    check("a start before the standing one is refused", not got["ok"], str(got.get("error"))[:70])

    # --- the same moment, taken once, is a handover and not an overlap ---
    rt = world(chairs=True)
    out, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\nt = now()\n'
                       'Person.new(full_name="First").relate(org, "chairs", starts=t)\n'
                       'Person.new(full_name="Second").relate(org, "chairs", starts=t)\n'
                       'print([p.display_name() for p in org.related("chairs_of")])')
    check("one moment passed to both hands over", out == "['Second']", out or str(got.get("error"))[:70])

    # --- the other shape: the subject changes, and the world can only count ---
    rt = world(led_by=False)
    out, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                       'Person.new(full_name="One").relate(org, "led_by")\n'
                       'Person.new(full_name="Two").relate(org, "led_by")\n'
                       'print(len(org.related("led_by_of")))')
    check("two subjects on one object both stand, since nothing said otherwise", out == "2", out)
    check("and the world asks about it once, naming the fix",
          any("one_per_object" in q for q in (got.get("questions") or [])),
          str(got.get("questions"))[:110])
    out, _ = ran(rt, 'led_by.one_per_object = True\n'
                     'Person.new(full_name="Three").relate(org, "led_by")\n'
                     'print([p.display_name() for p in org.related("led_by_of")])')
    check("and once it is said, the later one supersedes", out == "['Three']", out)

    # --- a link written from the wrong end is a different fact, and the world had the check ---
    # `relations.verify` worked this out from the day it was written and nothing called it, so
    # the world noticed a type running both ways and told nobody.
    rt = world(author_of=False)
    ran(rt, 'p1 = Person.new(full_name="Ursula K. Le Guin")\n'
            'b1 = Thing.ensure(name="A Wizard of Earthsea", nature="object")\n'
            'p1.relate(b1, "author_of")\n'
            'b2 = Thing.ensure(name="Starship Troopers", nature="object")\n'
            'p2 = Person.new(full_name="Robert A. Heinlein")\n'
            'b2.relate(p2, "author_of")\n'
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
    rt = world(born_in=False, wrote=False)
    out, _ = ran(rt, 'p = Person.new(full_name="Ursula K. Le Guin")\n'
                     'p.relate(Thing.ensure(name="Portland", nature="place"), "born_in")\n'
                     'p.relate(Thing.ensure(name="Earthsea", nature="object"), "wrote")\n'
                     'print(sorted(type(l).__name__ for l in p.relations()))')
    check("two links of two one-value types both stand",
          out == "['BornIn', 'Wrote']", out)

    # --- a type that keeps ending the last one on the same thing is a type in doubt ---
    # `citizen_of` was declared one citizen per country, so every American ended the last
    # American's citizenship: twelve links to the United States, six still holding.
    rt = world(citizen_of=True)
    out, got = ran(rt, 'usa = Thing.ensure(name="United States", nature="place")\nt = now()\n'
                       'for n in ("A One", "B Two", "C Three", "D Four", "E Five"):\n'
                       '    Person.new(full_name=n).relate(usa, "citizen_of", starts=t)\n'
                       'print(len(usa.related("citizen_of_of")))')
    check("one per object leaves only the last", out == "1", out)
    check("and the world asks whether it can have several at once",
          any("each ending the last" in q for q in (got.get("questions") or [])),
          str(got.get("questions"))[:110])
    # Withdrawing the premise withdraws the conclusion. The ends were the world's, drawn from
    # "there is one at a time"; told otherwise, it takes them back. What a person ended stays
    # ended, because that was said rather than worked out.
    out, got = ran(rt, 'citizen_of.one_per_object = False\n'
                       'print(len(usa.related("citizen_of_of")))')
    check("and saying it can brings back the ones the world ended", out == "5", out)
    check("and it says what it took back",
          any("hold again" in h for h in (got.get("hints") or [])), str(got.get("hints"))[:110])

    print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
                  else "all superseding tests passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
