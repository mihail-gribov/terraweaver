"""A list of texts is a type: several free texts, each dated, each able to end.

Run: .venv/bin/python tests/test_texts.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world

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
    w = open_world()
    out = w.run('''
ana = Person.new(name="Ana Borg")
ana.add("descriptions", "does cell chemistry at a battery startup")
ana.add("descriptions", "on parental leave", starts=date(2026, 3, 1), until=date(2026, 9, 1))
''', "host")
    assert not out["error"], out["error"]
    world, Person = w.world, w.classes["Person"]
    ana = Person.get(name="Ana Borg")

    check("what holds now is what the entity carries",
          ana.descriptions == ["does cell chemistry at a battery startup"], str(ana.descriptions))
    check("a text with a period that is over does not hold",
          "parental" not in " ".join(ana.descriptions))
    spells = ana.spells("descriptions")
    check("but its stretch is kept, like any other period", len(spells) == 2, str(spells))
    from datetime import datetime

    from terraweaver import periods

    periods.rebuild(world)
    check("and it held at a moment inside it",
          "on parental leave" in periods.holding(world, ana.subject_id, "descriptions",
                                                 datetime(2026, 4, 1)),
          str(periods.holding(world, ana.subject_id, "descriptions", datetime(2026, 4, 1))))

    w.run('ana.drop("descriptions", "does cell chemistry at a battery startup")\n'
          'ana.add("descriptions", "back at work")', "host")
    ana = Person.get(name="Ana Borg")
    check("dropping one ends it without deleting anything",
          ana.descriptions == ["back at work"], str(ana.descriptions))
    check("the record still has all three",
          len(ana.spells("descriptions")) == 3, str(ana.spells("descriptions")))

    w.run('ana.descriptions = ["back at work", "learning Portuguese"]', "host")
    ana = Person.get(name="Ana Borg")
    check("assigning the whole list says 'these are the ones now'",
          ana.descriptions == ["back at work", "learning Portuguese"], str(ana.descriptions))

    # --- the same shape, drawn from a vocabulary ---
    spec = dict(Person._spec)
    Person._spec = {**spec, "attributes": spec["attributes"] + [
        {"name": "temper", "type": "list[enum[calm, quick, stubborn]]", "description": "test only"}]}
    try:
        out = w.run('ana.temper = ["calm", "stubborn"]', "host")
        ana = Person.get(name="Ana Borg")
        check("a vocabulary list takes several of its own words",
              sorted(ana.temper or []) == ["calm", "stubborn"], str(getattr(ana, "temper", None)))
        said = w.run('ana.temper = ["grumpy"]', "host")
        check("and refuses a word that is not in it, saying where such a word goes",
              "none of them" in (said["error"] or ""), str(said["error"]))
    finally:
        Person._spec = spec

    print(f"\n{'all good' if not failures else str(len(failures)) + ' failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
