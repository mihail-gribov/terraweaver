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
    facts.state("p1", "name", "Anna", source="agent")
    facts.state("p2", "name", "Anna", source="agent")
    glued = images_of(facts)
    check("two subjects with the same name come out as one image", len(glued) == 1, str(glued))

    # A surname turns up for one of them, and an email for the other. They come apart — and
    # everything each of them said stays with the right one.
    facts.state("p1", "name", "Anna Sullivan", source="agent")
    facts.state("p1", "email", "anna.sullivan@example.com", source="agent")
    facts.state("p2", "name", "Anna Peterson", source="agent")
    facts.state("p2", "email", "anna.peterson@example.com", source="agent")
    apart = images_of(facts)
    check("a distinguishing fact splits them on the next rebuild", len(apart) == 2, str(apart))
    names = sorted(image.values.get("name") for image in apart.values())
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
    facts.state("a1", "name", "Anna Sullivan", source="agent")
    facts.state("a2", "name", "Anna Peterson", source="agent")
    facts.state("a1", assembly.SAME_AS, reference("a2"), source="agent")
    check("the user saying they are the same holds against the rule",
          len(images_of(facts, rule=lambda x, y: False)) == 1, str(images_of(facts, rule=lambda x, y: False)))
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("b1", "name", "Anna", source="agent")
    facts.state("b2", "name", "Anna", source="agent")
    facts.state("b1", assembly.NOT_SAME_AS, reference("b2"), source="agent")
    check("and the user saying they are different survives a rule that would merge them",
          len(images_of(facts, rule=lambda x, y: True)) == 2, str(images_of(facts, rule=lambda x, y: True)))

    # --- whose word wins when two statements cover the same slot ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("c1", "name", "Acme", source="world")
    facts.state("c1", "name", "Acme Inc", source="world")
    facts.state("c1", "name", "Acme Corporation Ltd", source="companies-house.gov.uk")
    facts.state("c1", "email", "hi@acme.test", source="world")
    facts.state("c1", "email", "hello@acme.test", source="agent")
    image = list(images_of(facts).values())[0]
    check("a checkable source outranks what the world worked out itself",
          image.values["name"] == "Acme Corporation Ltd", str(image.values))
    check("and what came through the assistant outranks both",
          image.values["email"] == "hello@acme.test", str(image.values))
    check("the image says where each value came from",
          image.sources["email"] == "agent" and image.sources["name"] == "companies-house.gov.uk",
          str(image.sources))

    # --- two statements of equal standing are a disagreement, not a silent choice ---
    facts.state("c1", "email", "other@acme.test", source="agent")
    image = list(images_of(facts).values())[0]
    check("the later of two equals is shown", image.values["email"] == "other@acme.test", str(image.values))
    check("and the one it beat is reported, not hidden", image.conflicts.get("email"), str(image.conflicts))

    # --- time is part of a statement ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("d1", "name", "Dana", source="agent")
    facts.state("d1", "organization", "TechCorp", source="agent", valid_until=date(2026, 9, 1))
    facts.state("d1", "organization", "DataWorks", source="agent", valid_from=date(2026, 9, 1))
    now = assembly.assemble(facts, at=datetime(2026, 9, 20))
    before = assembly.assemble(facts, at=datetime(2026, 6, 1))
    check("the image shows what holds now",
          list(now.values())[0].values["organization"] == "DataWorks", str(now))
    check("and the same facts build the world as it was",
          list(before.values())[0].values["organization"] == "TechCorp", str(before))

    # --- a run can be taken back ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("e1", "name", "Eve", source="agent")
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
    facts.state("p1", "notes", "never asks twice", source="agent")
    said = facts.about("p1")
    facts.state("p1", "notes", "hates small talk", source="agent")
    basis = facts.about("p1")
    made = facts.conclude("p1", "character", "keeps a distance, decides fast", basis=basis)
    conclusion = [s for s in facts.about("p1") if s.id == made][0]
    check("a conclusion carries what it was drawn from",
          [s.value for s in facts.basis_of(conclusion)] == ["never asks twice", "hates small talk"],
          str(facts.basis_of(conclusion)))
    check("and is fresh while that basis stands", not facts.stale(conclusion))
    check("anything anyone said outranks it",
          assembly.resolve([s for s in facts.about("p1") if s.slot == "notes"])[0].source == "agent")
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
          len([s for s in facts.about("p1") if s.source == "world"]) == 1)

    # --- and a rebuilt image knows which of its values it worked out ---
    image = list(assembly.assemble(facts).values())[0]
    check("the image takes the judgement where nobody stated the slot",
          image.values.get("character") == "keeps a distance, decides fast", str(image.values))
    check("and marks it as worked out, not told", image.judged == {"character"}, str(image.judged))
    check("a judgement whose basis has moved is shown as stale", image.stale == {"character"},
          str(image.stale))
    facts.state("p1", "character", "warmer than he looks", source="agent")
    image = list(assembly.assemble(facts).values())[0]
    check("and a word from the user replaces it outright",
          image.values["character"] == "warmer than he looks" and not image.judged, str(image.values))

    # --- the tables read like the architecture ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("t1", "name", "Tam", source="agent", class_name="Person")
    facts.state("t2", "name", "Acme", source="agent", class_name="Organization")
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
          [s.slot for s in facts.about("t1")] == ["name"], str(facts.about("t1")))

    # --- the same thing said again is the same statement, heard again ---
    facts = Facts(sqlite3.connect(":memory:"))
    first = facts.state("r1", "email", "ada@example.com", source="agent", class_name="Person")
    again = facts.state("r1", "email", "ada@example.com", source="agent")
    check("saying it twice doesn't make two statements", first == again, f"{first} / {again}")
    only = facts.about("r1")[0]
    check("it counts how often it was heard", only.times == 2, str(only.times))
    check("and remembers when it was first said as well as last", only.restated_at > only.stated_at,
          f"{only.stated_at} / {only.restated_at}")
    facts.state("r1", "email", "ada@example.com", source="a-register.example")
    check("another source saying the same is its own statement, because whose word it is matters",
          len(facts.about("r1")) == 2, str(facts.about("r1")))

    # --- some slots hold more than one thing, and that is not a disagreement ---
    specs = {"Person": {"attributes": [{"name": "email", "type": "list[email]"},
                                       {"name": "organization", "type": "ref:Organization"}]}}
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("m1", "email", "ada@work.example", source="agent", class_name="Person")
    facts.state("m1", "email", "ada@home.example", source="agent")
    facts.state("m1", "organization", "TechCorp", source="agent")
    facts.state("m1", "organization", "DataWorks", source="agent")
    image = list(assembly.assemble(facts, specs=specs).values())[0]
    check("two addresses are two addresses, not a quarrel",
          sorted(image.values["email"]) == ["ada@home.example", "ada@work.example"],
          str(image.values["email"]))
    check("two employers at once still are a quarrel", bool(image.conflicts.get("organization")),
          str(image.conflicts))

    # --- a name has forms, and none of them contradicts the others ---
    facts = Facts(sqlite3.connect(":memory:"))
    for form in ("Michael", "Mike", "Michael Gribov"):
        facts.state("n1", "name", form, source="agent", class_name="Person")
    image = list(assembly.assemble(facts).values())[0]
    check("every form of the name is kept", image.names == ["Michael Gribov", "Mike", "Michael"],
          str(image.names))
    check("the fullest is the one shown", image.values["name"] == "Michael Gribov",
          str(image.values["name"]))
    check("and none of it counts as a disagreement", not image.conflicts, str(image.conflicts))

    # --- a name form has to be vouched for, because names decide who is who ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("s1", "name", "Michael Gribov", source="agent", class_name="Person")
    for guess in ("Mike Gribov", "Sota"):
        facts.state("s1", "name", guess, source="world")
    image = list(assembly.assemble(facts).values())[0]
    check("a known form of the name needs nobody's permission", "Mike Gribov" in image.names,
          str(image.names))
    check("a nickname the world invented waits for a word", image.proposed_names == ["Sota"],
          str(image.proposed_names))
    facts.state("s1", "name", "Sota", source="agent")
    image = list(assembly.assemble(facts).values())[0]
    check("and one word from the user is enough",
          "Sota" in image.names and not image.proposed_names, str(image.names))

    # --- and a guessed name takes part in nothing until then ---
    facts = Facts(sqlite3.connect(":memory:"))
    facts.state("x1", "name", "Sasha Orlov", source="agent", class_name="Person")
    facts.state("x2", "name", "Sota Ivanov", source="agent", class_name="Person")
    facts.state("x2", "name", "Sasha Orlov", source="world")  # the world thinks they are one
    check("a guessed name doesn't merge two people",
          len(assembly.assemble(facts)) == 2, str(assembly.assemble(facts)))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all fact tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
