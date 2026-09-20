"""Tests for the two upper levels of change: what the world adds to its classes, and the
methods it writes for itself.

Run: .venv/bin/python tests/test_growth.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import growth
from terraweaver.ontology import load_specs
from terraweaver.runtime import WorldRuntime

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - any refusal counts; the point is that it didn't go through
        return str(exc)
    return None


def main() -> int:
    core = load_specs(ONTOLOGY_DIR, grown_dir=Path("/nonexistent"))

    # --- the world adds to a class, and the core file stays what it was ---
    addition = {"name": "PersonWithDiet", "extends": "Person", "added_at": "2026-09-20",
                "because": "seven people had a dietary note in a remark",
                "attributes": [{"name": "dietary_notes", "type": "str", "description": "What they don't eat."}]}
    grown = growth.apply_growth(core, [addition])
    names = [a["name"] for a in grown["Person"]["attributes"]]
    check("a grown attribute joins the class", "dietary_notes" in names, str(names[-3:]))
    check("and the core spec is untouched",
          "dietary_notes" not in [a["name"] for a in core["Person"]["attributes"]])
    check("the world can say what it added to itself",
          "dietary_notes" in growth.describe_growth(grown) and "seven people" in growth.describe_growth(grown),
          growth.describe_growth(grown))

    # --- growth adds; it never rewrites ---
    clash = dict(addition, name="PersonEmail",
                 attributes=[{"name": "email", "type": "str", "description": "another email"}])
    check("redefining a core attribute is refused",
          "can't be redefined" in (refused(lambda: growth.apply_growth(core, [clash])) or ""),
          str(refused(lambda: growth.apply_growth(core, [clash]))))
    check("extending something that isn't a core class is refused",
          refused(lambda: growth.apply_growth(core, [dict(addition, extends="Wizard")])) is not None)
    check("a change nobody can explain is refused",
          "review" in (refused(lambda: growth.apply_growth(core, [dict(addition, because="  ")])) or ""))
    check("a grown file can't smuggle in anything else",
          refused(lambda: growth.apply_growth(core, [dict(addition, impls="rm -rf")])) is not None)

    # --- a procedure the world wrote for itself ---
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.world.procedures.define(
        "colleagues", "colleagues(self)",
        "org = self.organization\n"
        "return [p for p in Person.find(organization=org).main if p != self] if org else []",
        because="asked three times this week: who else works where this person works",
        attaches_to="Person")
    rt.world.procedures.bind(rt.classes)
    called = rt.run('ada = Person.get(full_name="Ada Lovelace")\nprint(ada.colleagues())', "host")
    check("host code calls it like any method", called["ok"], str(called["error"]))
    check("and the call is counted", rt.world.procedures.get("colleagues").uses == 1,
          str(rt.world.procedures.get("colleagues")))
    check("it says why it exists",
          "three times this week" in rt.run('print(Person.colleagues.__doc__)', "host")["output"])

    # --- a procedure that can't run is never stored ---
    check("code the sandbox refuses is refused here",
          refused(lambda: rt.world.procedures.define("bad", "bad(self)", "import os\nreturn os",
                                                     because="x", attaches_to="Person")) is not None)
    check("and it wasn't kept", rt.world.procedures.get("bad") is None)
    check("a procedure with no reason to exist is refused",
          refused(lambda: rt.world.procedures.define("nope", "nope(self)", "return 1",
                                                     because="", attaches_to="Person")) is not None)

    # --- unused procedures are named so they can be dropped ---
    rt.world.procedures.define("unused", "unused(self)", "return 1",
                               because="tried once, never needed again", attaches_to="Person")
    check("a procedure just added isn't forgotten yet", rt.world.procedures.forgotten() == [])
    check("an old unused one is named",
          [p.name for p in rt.world.procedures.forgotten(older_than_days=-1)] == ["unused"],
          str(rt.world.procedures.forgotten(older_than_days=-1)))
    rt.world.procedures.drop("unused")
    check("and dropping it leaves nothing behind", rt.world.procedures.get("unused") is None)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all growth tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
