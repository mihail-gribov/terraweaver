"""Things that happen again: the arithmetic on its own, and one cyclic row in the period table.

Run: .venv/bin/python tests/test_recurrence.py
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world, periods, recurrence

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except ValueError as exc:
        return str(exc)
    return None


def main() -> int:
    # --- the arithmetic, which is all this is ---
    check("a step reads from words", str(recurrence.read("every 2 weeks")) == "2 weeks")
    check("and from a timedelta", str(recurrence.read(timedelta(days=21))) == "3 weeks")
    check("a year is twelve months, not 365 days", str(recurrence.read("year")) == "year")
    check("nonsense is refused where it can still be fixed",
          "no repeat like" in (refused(lambda: recurrence.read("every third-ish Tuesday")) or ""))

    jan31 = datetime(2026, 1, 31, 9, 0)
    monthly = [when.date().isoformat()
               for when, _ in recurrence.occurrences(jan31, "month", jan31, datetime(2026, 5, 1))]
    check("months step by the calendar and clamp",
          monthly == ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"], str(monthly))
    check("and come back to the 31st, because each one counts from the anchor",
          monthly[2].endswith("03-31"))

    rota = (datetime(2026, 9, 7), "3 weeks", timedelta(days=7))
    check("a moment inside an occurrence is covered",
          recurrence.covers(*rota, datetime(2026, 9, 10)))
    check("a moment between them is not",
          not recurrence.covers(*rota, datetime(2026, 9, 20)))
    check("and one months later still lands right",
          recurrence.covers(*rota, datetime(2026, 9, 30)) and
          not recurrence.covers(*rota, datetime(2026, 10, 10)))
    check("nothing before the anchor is covered",
          not recurrence.covers(*rota, datetime(2026, 8, 30)))
    check("a repeat with no length is a moment, so it never holds",
          not recurrence.covers(datetime(2026, 9, 7), "week", None, datetime(2026, 9, 7, 0, 1)))
    check("a series that has stopped stops answering",
          not recurrence.covers(*rota, datetime(2026, 9, 30), until=datetime(2026, 9, 20)))
    check("the next one is the next one",
          recurrence.next_after(datetime(2026, 9, 7), "3 weeks", datetime(2026, 9, 10)) ==
          datetime(2026, 9, 28))
    check("and there is no next one past the end",
          recurrence.next_after(datetime(2026, 9, 7), "3 weeks", datetime(2026, 9, 10),
                                ends=datetime(2026, 9, 20)) is None)

    # --- one rule, one row, and every existing question still works ---
    w = open_world()
    out = w.run('''
from datetime import timedelta
standup = Event.new(title="Standup", kind="meeting", status="confirmed",
                    start_time=datetime(2026, 9, 21, 9, 0))
standup.repeat(every="day", lasting=timedelta(minutes=30))
user.tag("on-call", every="3 weeks", lasting=timedelta(days=7), starts=date(2026, 9, 7))
''', "host")
    assert not out["error"], out["error"]
    world = w.world
    standup = w.classes["Event"].get(title="Standup")

    rows = world.store.conn.execute("SELECT COUNT(*) FROM periods WHERE every IS NOT NULL").fetchone()[0]
    check("a series is one row, not a thousand", rows == 2, f"{rows} cyclic rows")
    check("the rule reads back in words",
          standup.repeats() == ["every day, from 2026-09-21 09:00, 30 minutes at a time"],
          str(standup.repeats()))
    # Asked from a stated moment, never from the wall clock: "the next one" measured against
    # now answers differently before and after nine in the morning, and a test that changes its
    # mind at breakfast is worse than no test.
    check("the next one is known",
          standup.next_occurrence(after=datetime(2026, 9, 20)) == datetime(2026, 9, 21, 9, 0),
          str(standup.next_occurrence(after=datetime(2026, 9, 20))))
    week = standup.occurrences(since=date(2026, 9, 21), until=date(2026, 9, 25))
    check("a window asked about is counted out", len(week) == 4, str(week))
    check("and nothing is counted out without one",
          len(periods.stretches(world, standup.subject_id, "valid")) == 1)

    on_call = [date(2026, 9, 10), date(2026, 9, 20), date(2026, 9, 30), date(2026, 10, 10)]
    answers = [bool(world.where(tagged="on-call", at=when)) for when in on_call]
    check("a cyclic tag answers as of a moment, like every other tag",
          answers == [True, False, True, False], str(answers))
    check("asked from the other end too",
          periods.carrying(world, "tags", "on-call", datetime(2026, 9, 30)) != [] and
          periods.carrying(world, "tags", "on-call", datetime(2026, 9, 20)) == [])
    check("the world says what is cyclic in it", len(world.repeats()) == 2, str(world.repeats()))

    world.rebuild()
    periods.rebuild(world)
    check("the rule survives being derived again", standup.repeats() and
          bool(world.where(tagged="on-call", at=date(2026, 9, 30))))

    print(f"\n{'all good' if not failures else str(len(failures)) + ' failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
