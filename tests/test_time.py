"""Tests for time: one axis for entities, relations and remarks.

Run: .venv/bin/python tests/test_time.py
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import ontology, open_world

import base  # noqa: E402
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except (ValueError, TypeError) as exc:
        return str(exc)
    return None


def main() -> int:
    # A base world, the person it belongs to, and the words these checks need — a dentist, a
    # marriage (the same role at both ends, so it reads the same from either), an employer.
    rt = base.world(None)
    base.word(rt, "patient_of", "a person and the dentist who treats them", "many-to-many",
              "a patient", "their dentist")
    base.word(rt, "spouse_of", "two people married to each other", "one-to-one",
              "a spouse", "a spouse")
    base.word(rt, "works_at", "a person working for an employer", "many-to-one",
              "a person who works", "their employer")
    world = rt.world
    classes = world.classes
    Person, Thing = classes["Person"], classes["Thing"]
    michael = world.owner
    acme = Thing.new(name="Acme Dental")

    # --- a relation that starts later is not a current one ---
    nina = Person.new(full_name="Nina Patel")
    later = michael.set_patient_of(nina, starts=date(2100, 1, 1))
    with ontology.record_changes() as run:
        current = michael.related("patient_of")
    check("a relation starting later is out of ordinary reads", nina not in current)
    check("the world hints at what the read hid", any("start later" in h for h in run.hints),
          str(run.hints))
    check("any_time=True brings the future one back", nina in michael.related("patient_of", any_time=True))

    # --- a relation that ended is history, not a deletion ---
    olga = Person.new(full_name="Olga Gribova")
    # The marriages below are a sequence and have to read as one: Nadia 2010-2015, Olga
    # 2016-2018, Vera from 2019. Overlapping them is the conflict this section is about, so
    # they must not overlap by accident. Ended on a date rather than with `expire()`, which
    # puts the end at this moment — after everything that follows.
    marriage = olga.set_spouse_of(michael, starts=date(2016, 1, 1))
    marriage.keep(until=date(2018, 1, 1))
    with ontology.record_changes() as run:
        partners = michael.related("spouse_of")
    check("an ended relation is out of ordinary reads", partners == [])
    check("the world hints that one ended", any("ended" in h for h in run.hints), str(run.hints))
    check("any_time=True shows the ended one", olga in michael.related("spouse_of", any_time=True))

    # --- overlapping periods, not "now", make a conflict ---
    vera = Person.new(full_name="Vera Ilyina")
    vera.set_spouse_of(michael, starts=date(2019, 7, 6))
    check("a new partner after the old one ended goes through", vera in michael.related("spouse_of"))
    another = Person.new(full_name="Zoya Belova")
    refusal = refused(lambda: another.set_spouse_of(michael, starts=date(2019, 7, 6)))
    check("a second partner at the same time is refused", refusal is not None, str(refusal))
    past = Person.new(full_name="Nadia Orlova")
    past.set_spouse_of(michael, starts=date(2010, 1, 1), until=date(2015, 1, 1))
    check("a marriage that ended before this one is no conflict",
          past in michael.related("spouse_of", any_time=True))

    # --- one keyword for every read ---
    listing = Thing.new(name="Flat on Rua Anjos")
    listing.expire()
    check("expired entities leave Class.all", listing not in Thing.all(limit=None))
    check("any_time=True returns them", listing in Thing.all(limit=None, any_time=True))
    michael.describe("on vacation", until=date(2020, 1, 1))
    check("an expired remark is hidden", not [c for c in michael.described() if "vacation" in c.text])
    check("any_time=True shows expired remarks",
          [c for c in michael.described(any_time=True) if "vacation" in c.text] != [])

    # --- timeline: everything dated about one thing ---
    ada = Person.new(full_name="Ada Lovelace")
    ada.set_works_at(Thing.new(name="TechCorp"), starts=date(2020, 1, 1))
    was = ada.works_at
    ada.set_works_at(acme, starts=date(2026, 8, 1))
    ada.describe("moved teams", when=date(2026, 9, 1))
    moments = ada.timeline()
    what = [m.what for m in moments]
    check("the timeline is ordered oldest first", moments == sorted(moments, key=lambda m: m.when))
    check("the timeline holds the remark with its own date",
          any(m.what == "remark: moved teams" and m.when.date() == date(2026, 9, 1) for m in moments))
    check("the timeline shows the new relation starting", any("Acme Dental" in w for w in what), str(what))
    check("the timeline shows the old one ending", any(was.name in w and "until here" in w for w in what),
          str(what))
    check("the timeline says when the record entered the world", any("recorded as Person" in w for w in what))
    check("a relation has a timeline of its own", [m.what for m in later.timeline()] != [])
    check("the timeline can be windowed",
          all(m.when.date() >= date(2026, 9, 1) for m in ada.timeline(since=date(2026, 9, 1))))

    # --- a relation's ends have names ---
    ends = refused(lambda: later.related("patient_of"))
    check("asking a relation for 'the related one' says which ends it has",
          ends is not None and "rel.subject" in (ends or ""), str(ends))

    # --- a stored time compares with a date, which is what hosts write ---
    when = classes["Event"].new(title="Standup", start_time=datetime(2026, 10, 1, 9, 0))
    check("an attribute time compares with a plain date", when.start_time >= date(2026, 9, 30))
    check("and with a datetime, as before", when.start_time >= datetime(2026, 9, 30))
    check("and is still a datetime for everything else", isinstance(when.start_time, datetime))

    # --- a handover survives the dates a recorder invents when told to say when ---
    # The benchmark's whole subject. Two facts about one thing, recorded in one breath: with no
    # date the later one holds and both are kept; with `starts="now"` on both, the world used
    # to read two microsecond-apart timestamps as deliberate overlapping claims and refuse the
    # second outright, losing it. "now" is when you are being told, not when it began.
    import tempfile
    for said in (", starts=held", ', starts="2020-01-01"'):
        where = Path(tempfile.mkdtemp())
        mine = open_world(str(where / "w.db"))
        own = mine.world.classes
        mine.world.extras["define_relation"](
            # One chair per organisation at a time, which is the *object's* end — so
            # "one-to-many": one subject per object, many objects per subject. Said as
            # many-to-one it was the other end that was limited, and the organisation took a
            # second chair happily. The two ends have to be said apart, which is what removing
            # `over_time` forced: it used to set both from one boolean, so a type that limited
            # one end silently limited the other.
            "chairs", "who leads an organisation, one at a time", cardinality="one-to-many")
        org = own["Thing"].new(name="Fatah")
        first = own["Person"].new(full_name="Mahmoud Abbas")
        second = own["Person"].new(full_name="Someone Else")
        from terraweaver import timeutil as _t
        held = _t.now()          # taken once, as a host should: two now() calls are not one moment
        # Recorded without a start rather than refused. The date may be in the agent's own
        # context and it is the agent's to bring, but the world does not lose the fact waiting
        # for it — and a raise here stops the whole block, so one un-dated link used to cost
        # every fact written after it. What has a time is an event, and Event.start_time is
        # required. Checked on a pair of its own so the dated pair below is not disturbed.
        spare = own["Thing"].new(name="Spare Body")
        undated = refused(lambda: own["Person"].new(full_name="Undated One").set_chairs(spare))
        check("a type that changes takes a link with no start",
              undated is None, str(undated)[:110])
        exec(f'first.set_chairs(org{said})', {"first": first, "org": org, "held": held})
        kept = refused(lambda: exec(f'second.set_chairs(org{said})',
                                    {"second": second, "org": org, "held": held}))
        holds = [p.display_name() for p in org.related("chairs_of")]
        check(f"a second one hands over, said as {said}",
              kept is None and holds == ["Someone Else"], f"{kept or holds}")
        check(f"and the first stays in the record, said as {said}",
              first in org.related("chairs_of", any_time=True))
    ontology.set_world(world)

    # --- a date said the way people say dates ---
    # A month by its name is read, because the alternative is measured: refused `starts="March
    # 2023"`, a reader gave the year alone, the record took it, and a month somebody named went in
    # as the first of January. A date degraded cannot be told apart later from one somebody knew.
    from terraweaver import timeutil

    for said, want in (("March 2023", datetime(2023, 3, 1)),
                       ("march 2023", datetime(2023, 3, 1)),
                       ("mar 2023", datetime(2023, 3, 1)),
                       ("12 March 2023", datetime(2023, 3, 12)),
                       ("March 12, 2023", datetime(2023, 3, 12))):
        bound, _ = timeutil.told(said)
        check(f"{said!r} is read as a date", bound.moment == want, str(bound))
    # The side is read before the date, so the honest form of a month keeps working.
    bound, _ = timeutil.told("since June 2015")
    check("'since June 2015' is a side and a date",
          bound.moment == datetime(2015, 6, 1) and bound.side == timeutil.AFTER, str(bound))
    check("a month nobody has is not a date", refused(lambda: timeutil.told("Marching 2023")))
    check("a day that month has not got is not a date",
          refused(lambda: timeutil.told("February 30 2023")))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all time tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
