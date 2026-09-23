"""Tests for time: one axis for entities, relations and remarks.

Run: .venv/bin/python tests/test_time.py
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import initiative, ontology
from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.store import Store
from terraweaver.world import World
from worlds.job_search import build

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
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
    classes = build_classes(load_specs(ONTOLOGY_DIR), IMPLS)
    store = Store(":memory:")
    build(classes, store)
    world = World(store, classes)
    Person, Organization = classes["Person"], classes["Organization"]
    michael = Person.get(full_name="Michael")
    acme = Organization.new(name="Acme Dental")

    # --- a relation that starts later is not a current one ---
    nina = Person.new(full_name="Nina Patel")
    later = nina.relate(michael, "service", label="dentist", starts=date(2100, 1, 1))
    with ontology.record_changes() as run:
        current = michael.related("served_by")
    check("a relation starting later is out of ordinary reads", nina not in current)
    check("the world hints at what the read hid", any("start later" in h for h in run.hints),
          str(run.hints))
    check("any_time=True brings the future one back", nina in michael.related("served_by", any_time=True))

    # --- a relation that ended is history, not a deletion ---
    olga = Person.new(full_name="Olga Gribova")
    # The marriages below are a sequence and have to read as one: Nadia 2010-2015, Olga
    # 2016-2018, Vera from 2019. Overlapping them is the conflict this section is about, so
    # they must not overlap by accident. Ended on a date rather than with `expire()`, which
    # puts the end at this moment — after everything that follows.
    marriage = olga.relate(michael, "partner", label="wife", starts=date(2016, 1, 1))
    marriage.keep(until=date(2018, 1, 1))
    with ontology.record_changes() as run:
        partners = michael.related("partner")
    check("an ended relation is out of ordinary reads", partners == [])
    check("the world hints that one ended", any("ended" in h for h in run.hints), str(run.hints))
    check("any_time=True shows the ended one", olga in michael.related("partner", any_time=True))

    # --- overlapping periods, not "now", make a conflict ---
    vera = Person.new(full_name="Vera Ilyina")
    vera.relate(michael, "partner", label="wife", starts=date(2019, 7, 6))
    check("a new partner after the old one ended goes through", vera in michael.related("partner"))
    another = Person.new(full_name="Zoya Belova")
    refusal = refused(lambda: another.relate(michael, "partner", label="wife", starts=date(2019, 7, 6)))
    check("a second partner at the same time is refused", refusal is not None, str(refusal))
    past = Person.new(full_name="Nadia Orlova")
    past.relate(michael, "partner", label="wife", starts=date(2010, 1, 1), until=date(2015, 1, 1))
    check("a marriage that ended before this one is no conflict",
          past in michael.related("partner", any_time=True))

    # --- one keyword for every read ---
    listing = classes["Vacancy"].all(limit=None)[0]
    listing.expire()
    check("expired entities leave Class.all", listing not in classes["Vacancy"].all(limit=None))
    check("any_time=True returns them", listing in classes["Vacancy"].all(limit=None, any_time=True))
    michael.describe("on vacation", until=date(2020, 1, 1))
    check("an expired remark is hidden", not [c for c in michael.described() if "vacation" in c.text])
    check("any_time=True shows expired remarks",
          [c for c in michael.described(any_time=True) if "vacation" in c.text] != [])

    # --- timeline: everything dated about one thing ---
    ada = Person.get(full_name="Ada Lovelace")
    was = ada.organization
    ada.organization = acme
    ada.describe("moved teams", when=date(2026, 9, 1))
    moments = ada.timeline()
    what = [m.what for m in moments]
    check("the timeline is ordered oldest first", moments == sorted(moments, key=lambda m: m.when))
    check("the timeline holds the remark with its own date",
          any(m.what == "remark: moved teams" and m.when.date() == date(2026, 9, 1) for m in moments))
    check("the timeline shows the new relation starting", any("Acme Dental" in w for w in what))
    check("the timeline shows the old one ending", any(was.name in w and "until here" in w for w in what))
    check("the timeline says when the record entered the world", any("recorded as Person" in w for w in what))
    check("a relation has a timeline of its own", [m.what for m in later.timeline()] != [])
    check("the timeline can be windowed",
          all(m.when.date() >= date(2026, 9, 1) for m in ada.timeline(since=date(2026, 9, 1))))

    # --- a label that belongs to another type ---
    # The world moving a link to the type its label belongs to is something it does on its own,
    # so the test turns that on and puts it back.
    initiative.REROUTES_BY_LABEL = True
    sister = Person.new(full_name="Lena Gribova")
    refusal = refused(lambda: sister.relate(michael, "kin", label="wife"))
    initiative.REROUTES_BY_LABEL = False
    check("a partner label is refused inside kin", refusal is not None and "partner" in (refusal or ""),
          str(refusal))
    check("the fitting label still goes through", sister.relate(michael, "kin", label="sister") is not None)

    # --- a second provider of the same kind, at the same time, is worth a word ---
    with ontology.record_changes() as run:
        rao = Person.new(full_name="Arun Rao")
        rao.relate(michael, "service", label="dentist")
        Person.new(full_name="Sonia Roy").relate(michael, "service", label="dentist",
                                                 starts=date(2100, 2, 1))
    check("a second dentist for the same time is hinted at, not refused",
          any("already has a dentist" in h for h in run.hints), str(run.hints))

    # --- a relation's ends have names ---
    ends = refused(lambda: later.related("service"))
    check("asking a relation for 'the related one' says which ends it has",
          ends is not None and "rel.subject" in (ends or ""), str(ends))

    # --- a stored time compares with a date, which is what hosts write ---
    when = classes["Event"].new(title="Standup", kind="meeting", status="planned",
                     start_time=datetime(2026, 10, 1, 9, 0))
    check("an attribute time compares with a plain date", when.start_time >= date(2026, 9, 30))
    check("and with a datetime, as before", when.start_time >= datetime(2026, 9, 30))
    check("and is still a datetime for everything else", isinstance(when.start_time, datetime))

    # --- a handover survives the dates a recorder invents when told to say when ---
    # The benchmark's whole subject. Two facts about one thing, recorded in one breath: with no
    # date the later one holds and both are kept; with `starts="now"` on both, the world used
    # to read two microsecond-apart timestamps as deliberate overlapping claims and refuse the
    # second outright, losing it. "now" is when you are being told, not when it began.
    from terraweaver import authoring as _authoring
    import tempfile
    for said in (", starts=held", ', starts="2020-01-01"'):
        where = Path(tempfile.mkdtemp())
        own = build_classes(load_specs(ONTOLOGY_DIR), IMPLS)
        own_store = Store(str(where / "w.db"))
        build(own, own_store)
        own_world = World(own_store, own)
        ontology.set_world(own_world)
        _authoring.install(own_world, where / "grown").define_relation(
            "chairs", "who leads an organisation, one at a time", nature="related_to",
            cardinality="many-to-one", over_time=True)
        org = own["Organization"].new(name="Fatah")
        first = own["Person"].new(full_name="Mahmoud Abbas")
        second = own["Person"].new(full_name="Someone Else")
        from terraweaver import timeutil as _t
        held = _t.now()          # taken once, as a host should: two now() calls are not one moment
        # Recorded without a start rather than refused: the date may be in the agent's own
        # context and it is the agent's to bring, but the world does not lose the fact waiting
        # for it. Checked on a pair of its own so the dated pair below is not disturbed.
        spare = own["Organization"].new(name="Spare Body")
        with ontology.record_changes() as undated:
            own["Person"].new(full_name="Undated One").relate(spare, "chairs")
        check("a type that changes takes a link with no start, and says so",
              any("no start was said" in h for h in undated.hints), str(undated.hints)[:100])
        exec(f'first.relate(org, "chairs"{said})', {"first": first, "org": org, "held": held})
        kept = refused(lambda: exec(f'second.relate(org, "chairs"{said})',
                                    {"second": second, "org": org, "held": held}))
        holds = [p.display_name() for p in org.related("chairs_of")]
        check(f"a second one hands over, said as {said}",
              kept is None and holds == ["Someone Else"], f"{kept or holds}")
        check(f"and the first stays in the record, said as {said}",
              first in org.related("chairs_of", any_time=True))
    ontology.set_world(world)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all time tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
