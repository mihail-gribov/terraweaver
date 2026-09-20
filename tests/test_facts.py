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

    # --- what the world worked out for itself, and what from ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("p1", "notes", "never asks twice", source="user")
    said = facts.about("p1")
    facts.state("p1", "notes", "hates small talk", source="user")
    basis = facts.about("p1")
    made = facts.conclude("p1", "character", "keeps a distance, decides fast", basis=basis)
    conclusion = [s for s in facts.about("p1") if s.id == made][0]
    check("a conclusion carries what it was drawn from",
          [s.value for s in facts.basis_of(conclusion)] == ["never asks twice", "hates small talk"],
          str(facts.basis_of(conclusion)))
    check("and is fresh while that basis stands", not facts.stale(conclusion))
    check("anything anyone said outranks it",
          assembly.resolve([s for s in facts.about("p1") if s.slot == "notes"])[0].source == "user")
    facts.retract(basis[-1].id)
    check("when the basis moves it goes stale", facts.stale(conclusion))
    second = None
    try:
        facts.conclude("p1", "character", "again", basis=[conclusion])
    except ValueError as exc:
        second = str(exc)
    check("a conclusion is never drawn from a conclusion", second is not None and "guesses" in second,
          str(second))
    check("and the world can take back everything it concluded",
          len([s for s in facts.about("p1") if s.source == "agent"]) == 1)

    # --- and a rebuilt image knows which of its values it worked out ---
    image = list(assembly.assemble(facts).values())[0]
    check("the image takes the judgement where nobody stated the slot",
          image.values.get("character") == "keeps a distance, decides fast", str(image.values))
    check("and marks it as worked out, not told", image.judged == {"character"}, str(image.judged))
    check("a judgement whose basis has moved is shown as stale", image.stale == {"character"},
          str(image.stale))
    facts.state("p1", "character", "warmer than he looks", source="user")
    image = list(assembly.assemble(facts).values())[0]
    check("and a word from the user replaces it outright",
          image.values["character"] == "warmer than he looks" and not image.judged, str(image.values))

    # --- the tables read like the architecture ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("t1", "full_name", "Tam", source="user", class_name="Person")
    facts.state("t2", "name", "Acme", source="user", class_name="Organization")
    said = facts.about("t1")
    facts.conclude("t1", "character", "brisk", basis=said)
    check("what was said goes in its class's facts table",
          sorted(facts.tables()) == ["facts_Organization", "facts_Person", "reasoning_Person"],
          str(facts.tables()))
    check("and a statement knows which table it is in", facts.about("t2")[0].id.startswith("facts_Organization:"),
          facts.about("t2")[0].id)
    check("a subject is registered under its class", facts.class_of("t2") == "Organization",
          str(facts.class_of("t2")))

    # --- forgetting what the world worked out, keeping every word it was told ---
    forgotten = facts.forget_reasoning()
    check("everything worked out can be taken back in one move", forgotten == 1, str(forgotten))
    check("and what was said is untouched",
          [s.slot for s in facts.about("t1")] == ["full_name"], str(facts.about("t1")))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all fact tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
