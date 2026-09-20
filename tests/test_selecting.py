"""One door for asking: conditions combine, and a question need not be about one kind of thing.

Run: .venv/bin/python tests/test_selecting.py
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


def names(found) -> set:
    return {e.display_name() for e in found}


def kinds(found) -> set:
    return {type(e).__name__ for e in found}


def main() -> int:
    w = open_world()
    out = w.run('''
acme = Organization.new(name="Acme Cells", industry="Energy", tags=["move"])
school = Organization.new(name="Escola Beatriz", industry="Education", tags=["move"])
flat = Place.new(name="Rua Anjos 12", city="Lisbon", category="other", tags=["move"])
rita = Person.new(full_name="Rita Chen", descriptions=["does battery cell chemistry"],
                  tags=["move", "berlin"])
lars = Person.new(full_name="Lars Ek", descriptions=["writes payroll software"], tags=["berlin"])
rita.relate(acme, "membership", title="engineer", primary=True)
lars.relate(acme, "membership", title="engineer", primary=True)
acme.relate(rita, "service", label="employer")
rita.tag("apartment-hunt", starts=date(2026, 3, 1), until=date(2026, 6, 1))
''', "host")
    assert not out["error"], out["error"]
    world = w.world
    Person, Organization = w.classes["Person"], w.classes["Organization"]

    # --- a question about a thing, not about a kind of thing ---
    check("without a class the answer is of any kind",
          kinds(world.where(tagged="move")) == {"Person", "Organization", "Place"},
          str(kinds(world.where(tagged="move"))))
    check("naming a class narrows to it",
          names(world.where(Person, tagged="move")) == {"Rita Chen"},
          str(names(world.where(Person, tagged="move"))))
    check("the class may be its name",
          names(world.where("Person", tagged="move")) == names(world.where(Person, tagged="move")))

    # --- the plain searches are this one with a single condition ---
    check("world.tagged is where(tagged=...)",
          names(world.tagged("move")) == names(world.where(tagged="move")))
    check("world.tagged_all is where(tagged_all=...)",
          names(world.tagged_all("move", "berlin")) == {"Rita Chen"},
          str(names(world.tagged_all("move", "berlin"))))

    # --- every condition given narrows, and they hold at once ---
    check("two tags narrow further than one",
          len(world.where(tagged_all=["move", "berlin"])) < len(world.where(tagged="move")))
    check("attributes and a tag together",
          names(world.where(Organization, industry="Education", tagged="move")) ==
          {"Escola Beatriz"}, str(names(world.where(Organization, industry="Education", tagged="move"))))
    check("a relation, read in its own direction",
          names(world.where(related="membership")) == {"Rita Chen", "Lars Ek"},
          str(names(world.where(related="membership"))))
    check("and the other end of the same link is the reverse name",
          names(world.where(related="served_by")) == {"Rita Chen"},
          str(names(world.where(related="served_by"))))
    check("a relation to a particular other one",
          names(world.where(Person, related=("membership", w.classes["Organization"].get(
              name="Acme Cells")))) == {"Rita Chen", "Lars Ek"})
    check("a link and a tag hold at once",
          names(world.where(related="membership", tagged="move")) == {"Rita Chen"},
          str(names(world.where(related="membership", tagged="move"))))

    # --- tags are read as of a moment, like everything else that holds for a time ---
    check("a tag that has run out does not answer now",
          names(world.where(tagged="apartment-hunt")) == set(),
          str(names(world.where(tagged="apartment-hunt"))))
    check("but it answers at a moment inside its stretch",
          names(world.where(tagged="apartment-hunt", at=date(2026, 4, 1))) == {"Rita Chen"},
          str(names(world.where(tagged="apartment-hunt", at=date(2026, 4, 1)))))
    check("and any_time answers for whatever ever held",
          names(world.where(tagged="apartment-hunt", any_time=True)) == {"Rita Chen"})

    # --- meaning narrows too, and orders what is left ---
    by_sense = world.where(Person, like="battery chemistry", closeness=0.2)
    check("meaning picks out and puts the closest first",
          by_sense and by_sense[0].display_name() == "Rita Chen",
          str([e.display_name() for e in by_sense]))
    check("meaning inside a narrowed set stays inside it",
          all(type(e).__name__ == "Organization"
              for e in world.where(Organization, like="battery chemistry", closeness=0.1)))
    check("nothing close enough is an empty answer, not an error",
          world.where(Person, like="volcanic geology", closeness=0.95) == [])

    # --- a condition nothing answers empties the whole thing ---
    check("one unanswerable condition empties the answer",
          world.where(Person, tagged="move", related="membership", like="volcanic geology",
                      closeness=0.95) == [])
    check("limit cuts the answer, None keeps it whole",
          len(world.where(tagged="move", limit=2)) == 2 and
          len(world.where(tagged="move", limit=None)) == 4,
          str(len(world.where(tagged="move", limit=None))))

    # --- and the host sees the same door ---
    view = w.run("print(sorted(e.display_name() for e in world.where(tagged='move')))", "host")
    check("the host calls it the same way", "Rua Anjos 12" in (view["output"] or ""),
          str(view["output"] or view["error"]))

    print(f"\n{'all good' if not failures else str(len(failures)) + ' failed: ' + ', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
