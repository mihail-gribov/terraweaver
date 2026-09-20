"""Tests for open questions: what doesn't add up is taken, remembered, and raised again.

Run: .venv/bin/python tests/test_questions.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.runtime import WorldRuntime, format_result

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    rt = WorldRuntime(":memory:", fixture="job_search")

    # --- two providers of the same kind: taken, and remembered ---
    first = rt.run('rao = Person.new(full_name="Arun Rao")\n'
                   'old = rao.relate(owner, "service", label="dentist")\n'
                   'nina = Person.new(full_name="Nina Patel")\n'
                   'nina.relate(owner, "service", label="dentist", starts=date(2026, 10, 1))', "host")
    check("the write goes through", first["ok"], str(first["error"]))
    check("and the doubt is recorded", any("two dentists" in q for q in first["questions"]),
          str(first["questions"]))

    # --- it outlives the run, and the session ---
    later = rt.run('m = Person.get(full_name="Michael")', "another-host")
    check("another host working with the entity is told", any("two dentists" in q for q in later["questions"]),
          str(later["questions"]))
    check("the answers that would settle it come with it",
          "both stand" in format_result(later), format_result(later))

    # --- ending the old relation settles it without anyone answering ---
    rt.run('old.keep(until=date(2026, 10, 1))', "host")
    quiet = rt.run('m = Person.get(full_name="Michael")', "another-host")
    check("a question whose reason is gone closes itself", not quiet["questions"], str(quiet["questions"]))

    # --- recorded as new next to a lookalike ---
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.run('Person.new(full_name="Olga Gribova", email="olga@example.com")', "host")
    made_new = rt.run('q = Person.new(full_name="Olga")\nolga = world.settle(q, new=True)', "host")
    check("settling as new goes through", made_new["ok"], str(made_new["error"]))
    check("and leaves the doubt about the twin",
          any("the same one?" in q for q in made_new["questions"]), str(made_new["questions"]))

    # --- answering closes it, and it isn't raised again ---
    answered = rt.run('q = olga.questions()[0]\nq.answer("a different Olga — the user said so")\n'
                      'print(olga.questions())', "host")
    check("answering closes it", answered["output"].strip() == "[]", answered["output"])
    again = rt.run('other = Person.new(full_name="Olga")\nworld.settle(other, new=True)', "host")
    check("the same doubt about the same pair isn't raised twice",
          not any("Olga Gribova" in q and "the same one?" in q for q in again["questions"]),
          str(again["questions"]))

    # --- one the host noticed itself ---
    own = rt.run('before = len(world.questions())\n'
                 'anna = Person.get(full_name="Anna Peterson")\n'
                 'anna.question("two numbers on file, which is current?", options=["the mobile", "the old one"])\n'
                 'print(len(world.questions()) - before)', "host")
    check("the host can record a question of its own", own["output"].strip() == "1", own["output"])
    dropped = rt.run('anna.questions()[0].drop("asked, it is the mobile")\nprint(anna.questions())', "host")
    check("and drop it when it stops mattering", dropped["output"].strip() == "[]", dropped["output"])

    # --- a question blocks nothing ---
    check("nothing about it raised an error", own["ok"] and dropped["ok"], str(own["error"] or dropped["error"]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all question tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
