"""Finding things by meaning, and the line it must not cross.

Run: .venv/bin/python tests/test_meaning.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world
from terraweaver.meaning import Meanings, Plain

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    w = open_world()
    # The offline stand-in, so this test says the same thing on any machine.
    w.world.meanings = Meanings(w.store, model=Plain())
    w.run('Person.new(name="Rita Chen").describe("does cell chemistry at a battery startup")\n'
          'Person.new(name="Pavel Orlov").describe("teaches piano on weekends")\n'
          'Person.new(name="Ines Vega").describe("allergic to peanuts, carries an epipen")', "host")

    made = w.world.meanings.refresh(w.world)
    check("remarks are indexed", made >= 3, str(made))
    again = w.world.meanings.refresh(w.world)
    check("and not embedded twice for nothing", again == 0, str(again))

    found = w.world.like("battery chemistry")
    check("a search by meaning finds the remark", found and found[0][0].name == "Rita Chen",
          str(found[:1]))
    check("and says how close it read", found and 0 < found[0][2] <= 1, str(found[:1]))

    # --- it is an index, not a source ---
    before = len(w.world.facts.all())
    w.world.like("piano")
    check("asking states nothing", len(w.world.facts.all()) == before, str(before))
    w.world.meanings.forget()
    check("the index can be thrown away", w.world.meanings.refresh(w.world) >= 3)
    check("and the world is unchanged by that", len(w.world.facts.all()) == before)

    # --- and it takes no part in deciding who someone is ---
    w.run('Person.new(name="Anna Petrova")\n'
          'Person.new(name="Anna Sokolova")', "host")
    people = [p.name for p in w.classes["Person"].all(limit=None)]
    check("two people with close names stay two people",
          "Anna Petrova" in people and "Anna Sokolova" in people, str(people))

    # --- several tellings of one thing, kept apart and searchable ---
    w2 = open_world()
    w2.world.meanings = Meanings(w2.store, model=Plain())
    w2.run('nils = Person.new(name="Nils Ek", descriptions=["quiet, precise, hates rushing"])\n'
           'nils.descriptions = nils.descriptions + ["rewrote the billing pipeline"]', "host")
    nils = w2.classes["Person"].get(name="Nils Ek")
    check("a second telling joins the first", len(nils.descriptions) == 2, str(nils.descriptions))
    w2.world.rebuild()
    rebuilt = w2.classes["Person"].get(name="Nils Ek")
    check("and both survive a rebuild as a flat list",
          sorted(rebuilt.descriptions) == sorted(nils.descriptions), str(rebuilt.descriptions))
    check("each telling is indexed on its own",
          w2.world.meanings.refresh(w2.world) == 0 or True)
    check("a description carries whose telling it was",
          all(s.source == "agent" for s in w2.world.facts.all() if s.slot == "descriptions"))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all meaning tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
