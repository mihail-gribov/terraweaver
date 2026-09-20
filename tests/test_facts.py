"""Tests for the two layers: facts that are never lost, images that can always be rebuilt.

Run: .venv/bin/python tests/test_facts.py
"""
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import assembly
from terraweaver.facts import Facts, reference

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def images_of(facts, rule=assembly.same_name):
    return assembly.assemble(facts, rule)


def main() -> int:
    facts = Facts(sqlite3.connect(":memory:"))

    # Two people the user mentioned on different days, both called Anna. Nothing yet says whether
    # they are one person; the loose rule glues them, which is usually right.
    facts.state("p1", "full_name", "Anna", source="user")
    facts.state("p2", "full_name", "Anna", source="user")
    glued = images_of(facts)
    check("two subjects with the same name come out as one image", len(glued) == 1, str(glued))

    # A surname turns up for one of them, and an email for the other. They come apart — and
    # everything each of them said stays with the right one.
    facts.state("p1", "full_name", "Anna Sullivan", source="user")
    facts.state("p1", "email", "anna.sullivan@example.com", source="user")
    facts.state("p2", "full_name", "Anna Peterson", source="user")
    facts.state("p2", "email", "anna.peterson@example.com", source="user")
    apart = images_of(facts)
    check("a distinguishing fact splits them on the next rebuild", len(apart) == 2, str(apart))
    names = sorted(image.values.get("full_name") for image in apart.values())
    check("and each keeps what was said about them", names == ["Anna Peterson", "Anna Sullivan"], str(names))

    # Nothing was lost by being wrong: the first, vaguer statement is still in the record.
    kept = [s for s in facts.about("p1") if s.value == "Anna"]
    check("the statement that caused the wrong guess is still there", len(kept) == 1, str(facts.about("p1")))

    # --- the rule is a rule, not a decision written into the data ---
    strict = images_of(facts, rule=lambda a, b: False)
    check("a stricter rule rebuilds the world without touching a fact", len(strict) == 2, str(strict))
    loose = images_of(facts, rule=lambda a, b: True)
    check("a looser one glues everything, from the same facts", len(loose) == 1, str(loose))

    # --- what the user settles outranks any rule ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("a1", "full_name", "Anna Sullivan", source="user")
    facts.state("a2", "full_name", "Anna Peterson", source="user")
    facts.state("a1", assembly.SAME_AS, reference("a2"), source="user")
    check("the user saying they are the same holds against the rule",
          len(images_of(facts, rule=lambda x, y: False)) == 1, str(images_of(facts, rule=lambda x, y: False)))
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("b1", "full_name", "Anna", source="user")
    facts.state("b2", "full_name", "Anna", source="user")
    facts.state("b1", assembly.NOT_SAME_AS, reference("b2"), source="user")
    check("and the user saying they are different survives a rule that would merge them",
          len(images_of(facts, rule=lambda x, y: True)) == 2, str(images_of(facts, rule=lambda x, y: True)))

    # --- whose word wins when two statements cover the same slot ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("c1", "full_name", "Acme", source="agent")
    facts.state("c1", "name", "Acme Inc", source="agent")
    facts.state("c1", "name", "Acme Corporation Ltd", source="companies-house.gov.uk")
    facts.state("c1", "email", "hi@acme.test", source="agent")
    facts.state("c1", "email", "hello@acme.test", source="user")
    image = list(images_of(facts).values())[0]
    check("a checkable source outranks the assistant's own conclusion",
          image.values["name"] == "Acme Corporation Ltd", str(image.values))
    check("and the user outranks both", image.values["email"] == "hello@acme.test", str(image.values))
    check("the image says whose word each value is",
          image.sources["email"] == "user" and image.sources["name"] == "companies-house.gov.uk",
          str(image.sources))

    # --- two statements of equal standing are a disagreement, not a silent choice ---
    facts.state("c1", "email", "other@acme.test", source="user")
    image = list(images_of(facts).values())[0]
    check("the later of two equals is shown", image.values["email"] == "other@acme.test", str(image.values))
    check("and the one it beat is reported, not hidden", image.conflicts.get("email"), str(image.conflicts))

    # --- time is part of a statement ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("d1", "full_name", "Dana", source="user")
    facts.state("d1", "organization", "TechCorp", source="user", valid_until=date(2026, 9, 1))
    facts.state("d1", "organization", "DataWorks", source="user", valid_from=date(2026, 9, 1))
    now = assembly.assemble(facts, at=datetime(2026, 9, 20))
    before = assembly.assemble(facts, at=datetime(2026, 6, 1))
    check("the image shows what holds now",
          list(now.values())[0].values["organization"] == "DataWorks", str(now))
    check("and the same facts build the world as it was",
          list(before.values())[0].values["organization"] == "TechCorp", str(before))

    # --- a run can be taken back ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("e1", "full_name", "Eve", source="user")
    facts.state("e1", "email", "eve@example.com", source="agent", run_id="r-7")
    facts.state("e1", "phone", "+15550000000", source="agent", run_id="r-7")
    undone = facts.retract_run("r-7")
    image = list(images_of(facts).values())[0]
    check("undoing a run takes back everything it stated", undone == 2 and "email" not in image.values,
          str(image.values))
    check("and what it stated is still in the record, marked",
          len(facts.about("e1", include_retracted=True)) == 3, str(facts.about("e1", include_retracted=True)))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all fact tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
