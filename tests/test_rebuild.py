"""The basic world: statements, and the entities built from them. Nothing else.

Run: .venv/bin/python tests/test_rebuild.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import assembly, open_world

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def nothing_lost(world, classes) -> tuple:
    """Every name and every link the world holds, so a rebuild can be compared with itself."""
    names, links = {}, 0
    for cls in world.classes.values():
        for entity in world.all(cls.__name__, limit=None, history=True):
            if cls._spec.get("relation"):
                links += 1
                continue
            said = (getattr(entity, "name", None) or getattr(entity, "full_name", None)
                    or getattr(entity, "title", None))
            if said:
                names[said] = names.get(said, 0) + 1
    return names, links

def main() -> int:
    # --- a rebuild keeps what the world holds: a city is not the university named after it ---
    # Rebuilding a 455-fact world lost twelve things outright. A name inside another name
    # scores exactly the part-match bar, and the bar was applied to everything: Berkeley went
    # into the University of California, Berkeley, rugby into rugby union, Australia into the
    # Australian Open. The live world restricts that to the classes where a short name is a
    # short name; the rebuild did not, so the two disagreed about the same names.
    apart = open_world()
    apart.run('Thing.ensure(name="Berkeley", nature="place")\n'
              'Thing.ensure(name="University of California, Berkeley", nature="agent")\n'
              'Thing.ensure(name="rugby", nature="abstraction")\n'
              'Thing.ensure(name="rugby union", nature="abstraction")\n'
              'p = Person.new(full_name="Paris Hilton")\n'
              'Thing.ensure(name="Paris", nature="place")', "host")
    held_before, links_before = nothing_lost(apart.world, apart.classes)
    apart.world.rebuild()
    held_after, links_after = nothing_lost(apart.world, apart.classes)
    gone = sorted(set(held_before) - set(held_after))
    check("a rebuild keeps every name the world held", not gone, str(gone))
    check("and every link", links_after == links_before, f"{links_before} -> {links_after}")

    # An address is an attribute the world grows when it is told one; an employer is a link,
    # under a word the world has for it. Both have to come back from the statements alone.
    w = base.world()
    base.attribute(w, "Person", "email", "The address this person reads their mail at.", type="email")
    base.word(w, "works_at", "a person working for an employer", "many-to-one",
              "a person who works", "their employer")
    Person = w.classes["Person"]

    w.run('ada = Person.new(full_name="Ada Lovelace", email="ada@example.com")\n'
          'tc = Thing.new(name="TechCorp")\n'
          'ada.set_works_at(tc)', "k")

    # --- everything the object model wrote is in the record ---
    said = [(s.slot, s.value) for s in w.world.facts.all()]
    check("what was written is what was said",
          ("full_name", "Ada Lovelace") in said and ("email", "ada@example.com") in said, str(said))
    check("and it is filed under the class it is about",
          "facts_Person" in w.world.facts.tables() and "facts_Thing" in w.world.facts.tables(),
          str(w.world.facts.tables()))

    # --- the entities can be thrown away and built again ---
    before = repr(Person.get(email="ada@example.com"))
    built = w.world.rebuild()
    ada = Person.get(email="ada@example.com")
    check("a rebuilt entity holds what it held", ada.full_name == "Ada Lovelace", str(ada.full_name))
    check("links survive the rebuild",
          ada.works_at is not None and ada.works_at.name == "TechCorp", str(ada.works_at))
    check("and the relation between them too", built and len(built) >= 3, str(len(built)))

    # --- the same statements build the same entities ---
    w.world.rebuild()
    check("rebuilding twice changes nothing", repr(Person.get(email="ada@example.com")) == repr(ada),
          repr(Person.get(email="ada@example.com")))
    stated = len(w.world.facts.all())
    w.world.rebuild()
    check("and rebuilding states nothing", len(w.world.facts.all()) == stated, str(stated))

    # --- when something holds is part of the record, so it comes back too ---
    w.run('ada = Person.get(email="ada@example.com")\nada.keep(until=date(2030, 1, 1))', "k")
    w.world.rebuild()
    kept = [p for p in Person.all(limit=None, any_time=True) if p.email == "ada@example.com"]
    check("a period survives the rebuild",
          kept and kept[0].until is not None and kept[0].until.date() == date(2030, 1, 1),
          str(kept[0].until if kept else "gone"))

    # --- a rule can change, and the world is rebuilt by it ---
    w2 = open_world()
    w2.world.facts.state("q1", "full_name", "Anna", source="agent", class_name="Person")
    w2.world.facts.state("q2", "full_name", "Anna", source="agent", class_name="Person")
    w2.world.rebuild()
    check("a loose rule glues two subjects into one entity",
          len([p for p in w2.classes["Person"].all(limit=None) if p.full_name == "Anna"]) == 1,
          str(w2.classes["Person"].all(limit=None)))
    w2.world.rebuild(rule=lambda a, b: False)
    check("a strict one builds two, from the same statements",
          len([p for p in w2.classes["Person"].all(limit=None) if p.full_name == "Anna"]) == 2,
          str(w2.classes["Person"].all(limit=None)))

    # --- an entity has two identities: the image, and the subject words attach to ---
    w3 = open_world()
    base.attribute(w3, "Person", "phone", "The number this person answers.", type="phone")
    facts = w3.world.facts
    facts.state("u1", "full_name", "Anna Sullivan", source="agent", class_name="Person")
    facts.state("u2", "full_name", "Anna Sullivan", source="agent", class_name="Person")
    facts.state("u2", "notes", "met at the meetup", source="agent")
    w3.world.rebuild()
    anna = [p for p in w3.classes["Person"].all(limit=None) if p.full_name == "Anna Sullivan"]
    check("two subjects saying the same name build one entity", len(anna) == 1, str(anna))
    check("which knows the subjects it was built from",
          sorted(anna[0].__dict__["_subjects"]) == ["u1", "u2"], str(anna[0].__dict__.get("_subjects")))
    check("and what either of them said", anna[0].notes == "met at the meetup", str(anna[0].notes))

    w3.run('anna = Person.get(full_name="Anna Sullivan")\nanna.phone = "+15550000000"', "host")
    said = [s for s in facts.all() if s.slot == "phone"]
    check("a new word lands on a subject, not on the image",
          len(said) == 1 and said[0].subject in ("u1", "u2"), str(said))

    # --- and when the world learns they are two people, each keeps its own ---
    facts.state("u1", assembly.NOT_SAME_AS, {"$subject": "u2"}, source="agent")
    w3.world.rebuild()
    split = [p for p in w3.classes["Person"].all(limit=None) if p.full_name == "Anna Sullivan"]
    check("they come apart again", len(split) == 2, str(split))
    check("and what was said about each stays with it",
          sorted(bool(p.notes) for p in split) == [False, True], str([p.notes for p in split]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all rebuild tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
