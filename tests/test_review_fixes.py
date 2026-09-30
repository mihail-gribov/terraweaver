"""Tests for the findings of docs/code-review-2026-09-30.md, one test per finding.

Every high finding in that review sat on a path no test touched, which is why each of them
survived a hundred runs. The fixes go in with a test here, named by the finding, so the next
sweep over these seams has something that fails when it is undone.

Run: .venv/bin/python tests/test_review_fixes.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class StubEngineer:
    """An engineer shaped like `outside.Open`: it answers `.json` and `.say`, it is not callable."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def json(self, system: str, asked: str):
        self.asked.append(asked)
        return self.answer

    def say(self, system: str, asked: str) -> str:
        self.asked.append(asked)
        return str(self.answer)


def finding_3_4_1_the_engineer_is_not_a_function() -> None:
    """`look_at_types` must reach an engineer that answers `.json`, not call it as a function."""
    from terraweaver import inspector

    rt = base.world()
    base.word(rt, "wrote", "who wrote what", cardinality="many-to-many",
              subject_is="", object_is="")
    person = rt.world.new("Person", full_name="Ann")
    book = rt.world.new("Thing", name="a book")
    rt.world.relate(person, book, "wrote")

    engineer = StubEngineer({"subject_is": "writer", "object_is": "written",
                             "clear": True, "clear_name": "wrote"})
    rt.world.engineer = engineer
    out = inspector.look_at_types(rt.world)

    read = rt.world.store.conn.execute(
        "SELECT count(*) FROM type_checks WHERE looked_at IS NOT NULL").fetchone()[0]
    check("3.4.1 the engineer is asked at all", bool(engineer.asked),
          f"nothing was asked of it; look_at_types said {out}")
    check("3.4.1 what it said is written down", read > 0, f"{read} types marked read")
    check("3.4.1 the ends it named are on the type",
          (rt.world.classes["Wrote"]._spec.get("relation") or {}).get("roles") is not None,
          "the roles were not filled in")


class StubPicker:
    """A picker that answers nothing: the look finds no word, the check has nothing to judge."""

    def choose(self, state, question, options):
        raise RuntimeError("this picker does not answer")

    def ask(self, state, questions):
        return {}


class SilentEngineer:
    """It writes a line that runs and joins nothing — the case the trace calls "gave up"."""

    def __init__(self):
        self.goes = 0

    def say(self, system: str, asked: str) -> str:
        self.goes += 1
        return "x = 1"


def finding_3_4_2_a_link_that_was_already_there_is_not_this_readings_work() -> None:
    """A typed link standing before the reading must not be counted as what the reading wrote."""
    from terraweaver import formalise
    from terraweaver.formalise import write

    rt = base.world()
    base.word(rt, "mayor_of", "who is the mayor of what", cardinality="one-to-one",
              subject_is="mayor", object_is="city")
    person = rt.world.new("Person", full_name="Anne Hidalgo")
    city = rt.world.new("Thing", name="Paris")
    standing = rt.world.relate(person, city, "mayor_of")

    bare = rt.world.relate(person, city, "related",
                           description="Anne Hidalgo was born in Paris")
    check("3.4.2 typed_between sees it without the exclusion",
          len(write.typed_between(rt.world, person, city)) == 1)
    check("3.4.2 and not with it",
          write.typed_between(rt.world, person, city, apart_from={standing.id}) == [])

    engineer, picker = SilentEngineer(), StubPicker()
    trace = formalise.formalise_one(rt, bare, engineer, picker)
    again = rt.world.store.load(bare.id, rt.world.classes) or bare
    check("3.4.2 the reading does not claim the standing link", trace.get("went") == "gave up",
          f"it said {trace.get('went')!r}, typed {trace.get('typed')}")
    check("3.4.2 the bare link holding the real words is still standing",
          getattr(again, "valid_until", None) is None,
          "it was ended, and the words went with it")
    check("3.4.2 what was already there is in the trace", trace.get("was_typed") == 1,
          f"was_typed={trace.get('was_typed')}")


def main() -> None:
    finding_3_4_1_the_engineer_is_not_a_function()
    finding_3_4_2_a_link_that_was_already_there_is_not_this_readings_work()
    print()
    if failures:
        print(f"{len(failures)} failed: " + ", ".join(failures))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
