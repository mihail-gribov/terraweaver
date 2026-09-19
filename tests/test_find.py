"""Tests for world lookup — the part everything else leans on.

`find` decides who the agent is talking about, so its behaviour can't be left to live
runs through a model: those are slow, costly, and vary between runs. These are plain
deterministic checks over the prepared world.

Run: python3 tests/test_find.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.resolution import NeedsResolution
from terraweaver.store import Store
from terraweaver.world import World
from worlds.job_search import build

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def fresh_world():
    specs = load_specs(ONTOLOGY_DIR)
    classes = build_classes(specs, IMPLS)
    store = Store(":memory:")
    build(classes, store)
    return classes, store, World(store, classes)


def names(result) -> list[str]:
    return [getattr(e, "full_name", None) or e.name for e in result]


def main() -> int:
    classes, store, world = fresh_world()
    Person, Organization, Vacancy = classes["Person"], classes["Organization"], classes["Vacancy"]

    # --- a name that identifies exactly one person ---
    result = Person.find(full_name="Alan Turing")
    check("exact full name matches", not isinstance(result, NeedsResolution) and names(result.main) == ["Alan Turing"])

    result = Person.find(full_name="Barb")
    check("recorded alias matches", not isinstance(result, NeedsResolution) and names(result.main) == ["Barbara Liskov"],
          f"got {result!r}")

    result = Person.find(email="ada@example.com")
    check("strong key matches without a name", not isinstance(result, NeedsResolution)
          and names(result.main) == ["Ada Lovelace"])

    # --- a name that doesn't settle it: the user has to ---
    result = Person.find(full_name="Annie")
    check("shared alias asks", isinstance(result, NeedsResolution) and len(result.candidates) == 2, f"got {result!r}")
    check("shared alias says several match", isinstance(result, NeedsResolution) and "equally well" in result.reason)

    result = Person.find(full_name="Ada Lovelase")
    check("an unrecorded misspelling asks", isinstance(result, NeedsResolution), f"got {result!r}")
    check("and says nothing matches exactly",
          isinstance(result, NeedsResolution) and "merely resemble" in result.reason)

    # "Robert" is his first name but not one of his recorded names ("Bob" is), so matching
    # one part of "Robert Wolfe" can only ever be a resemblance.
    result = Person.find(full_name="Robert")
    check("bare first name is not certainty", isinstance(result, NeedsResolution), f"got {result!r}")

    # --- match and resemblance are kept apart ---
    result = Person.find(full_name="Ann")
    check("one certain match wins", not isinstance(result, NeedsResolution) and names(result.main) == ["Anna Sullivan"],
          f"got {result!r}")
    check("resemblances are set aside, not dropped",
          not isinstance(result, NeedsResolution) and names(result.similar) == ["Anna Peterson"])
    check("iterating still yields everything",
          not isinstance(result, NeedsResolution) and len(result) == 2)

    # --- nobody at all ---
    result = Person.find(full_name="Zoe")
    check("no candidates is an empty result, not a question",
          not isinstance(result, NeedsResolution) and not result.matched and len(result) == 0, f"got {result!r}")

    # --- ordinary attributes filter ---
    techcorp = Organization.find(name="TechCorp").main[0]
    check("filters by an ordinary attribute", names(Person.find(organization=techcorp).main) == ["Ada Lovelace"])
    check("filters by several attributes",
          all(v.remote and v.status == "not_applied" for v in Vacancy.find(remote=True, status="not_applied").main))
    check("a filter that matches nothing yields nothing", len(Vacancy.find(status="withdrawn")) == 0)

    # A list attribute is satisfied by containing the value. Comparing the whole list to one
    # value matches nothing, and an empty result reads as "there are none" — confidently wrong.
    Event = classes["Event"]
    owner = world.owner
    check("filters by membership of a list attribute",
          len(Event.find(participants=owner).main) == len(Event.all(limit=None)),
          f"got {len(Event.find(participants=owner).main)}")
    check("membership works for plain values too",
          all("Python" in v.stack for v in Vacancy.find(stack="Python").main))
    check("and a value that's in no list matches nothing", len(Vacancy.find(stack="COBOL")) == 0)

    # --- companies get the same treatment as people ---
    check("company alias matches", names(Organization.find(name="Data Works").main) == ["DataWorks"])
    check("company short form matches", names(Organization.find(name="DW").main) == ["DataWorks"])
    check("company resemblance asks", isinstance(Organization.find(name="Data"), NeedsResolution))

    # --- searching is not working with anything ---
    ada = Person.find(email="ada@example.com").main[0]
    before = ada.accessed_at
    Person.find(full_name="Alan Turing")
    Person.find(organization=techcorp)
    check("a search leaves access times alone",
          Person.find(email="ada@example.com").main[0].accessed_at == before)

    # --- equal relevance is broken by who was dealt with most recently ---
    remote = Vacancy.find(remote=True).main
    world._determined(remote[-1])
    check("ties go to the most recently handled",
          Vacancy.find(remote=True).main[0].id == remote[-1].id)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all find tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
