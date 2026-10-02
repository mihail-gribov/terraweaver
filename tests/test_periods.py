"""When things held: derived from the statements, and normalised.

Run: .venv/bin/python tests/test_periods.py
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world, periods

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    # --- the arithmetic on its own ---
    march, june, september = datetime(2026, 3, 1), datetime(2026, 6, 1), datetime(2026, 9, 1)
    april, may = datetime(2026, 4, 1), datetime(2026, 5, 1)
    check("stretches that touch become one",
          periods.coalesce([(march, june), (june, september)]) == [(march, september)],
          str(periods.coalesce([(march, june), (june, september)])))
    check("a stretch inside another disappears into it",
          periods.coalesce([(march, september), (april, may)]) == [(march, september)])
    check("one that never ends swallows what follows",
          periods.coalesce([(march, None), (june, september)]) == [(march, None)])
    check("and stretches with a gap stay two",
          len(periods.coalesce([(march, april), (june, september)])) == 2)

    # --- and the same, derived from what was said ---
    w = open_world()
    w.run('ana = Person.new(name="Ana Borg")\n'
          'ana.tag("apartment-hunt", starts=date(2026, 3, 1), until=date(2026, 6, 1))\n'
          'ana.tag("apartment-hunt", starts=date(2026, 6, 1), until=date(2026, 9, 1))\n'
          'ana.tag("apartment-hunt", starts=date(2026, 4, 1), until=date(2026, 5, 1))\n'
          # A fixed start, not "now". Written without one, this tag began at the moment the test
          # ran and the question below — what held on 2026-10-01 — fell *before* it from
          # 2026-10-01 onwards: a test that passes until the calendar turns. What it means to
          # check is that a tag with no end still holds months later, and that needs a start it
          # can name.
          'ana.tag("berlin", starts=date(2026, 7, 1), permanent=True)', "host")
    ana = w.classes["Person"].get(name="Ana Borg")
    check("four statements about two tags come out as two stretches",
          periods.rebuild(w.world) == 2, str(periods.rebuild(w.world)))
    hunt = [s for s in ana.spells("tags") if s.value == "apartment-hunt"]
    check("and the one with three statements is a single stretch", len(hunt) == 1, str(hunt))
    check("from the first start to the last end",
          hunt[0].starts.date() == date(2026, 3, 1) and hunt[0].until.date() == date(2026, 9, 1),
          str(hunt[0]))

    # --- asking about a moment, from either end ---
    check("what held in May", periods.holding(w.world, ana.subject_id, "tags", datetime(2026, 5, 15))
          == ["apartment-hunt"])
    check("what held in October",
          periods.holding(w.world, ana.subject_id, "tags", datetime(2026, 10, 1)) == ["berlin"])
    check("and who held it, asked from the other end",
          periods.carrying(w.world, "tags", "apartment-hunt", datetime(2026, 5, 15)) == [ana.subject_id])

    # --- it is a derivation, like everything else ---
    said = len(w.world.facts.all())
    w.store.conn.execute("DELETE FROM periods")
    check("throwing it away changes nothing", periods.rebuild(w.world) == 2)
    check("and states nothing", len(w.world.facts.all()) == said, str(said))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all period tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
