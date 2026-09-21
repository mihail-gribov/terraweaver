"""Tests for world lookup — the part everything else leans on.

`find` decides who the agent is talking about, so its behaviour can't be left to live
runs through a model: those are slow, costly, and vary between runs. These are plain
deterministic checks over the prepared world.

Run: python3 tests/test_find.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import matching
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

    result = Person.find(full_name="Barb Liskov")
    check("nickname with surname matches", not isinstance(result, NeedsResolution)
          and names(result.main) == ["Barbara Liskov"], f"got {result!r}")

    result = Person.find(email="ada@example.com")
    check("strong key matches without a name", not isinstance(result, NeedsResolution)
          and names(result.main) == ["Ada Lovelace"])

    # --- a name that doesn't settle it: the user has to ---
    result = Person.find(full_name="Annie")
    check("shared alias asks", isinstance(result, NeedsResolution) and len(result.candidates) == 2, f"got {result!r}")
    check("shared alias says several match", isinstance(result, NeedsResolution) and "equally well" in result.reason)

    # A name the entity answers to — part of its name — with nothing that disagrees, is them:
    # "Robert" is his first name, and he is the only person in this world it can mean.
    result = Person.find(full_name="Robert")
    check("a bare first name with one candidate is them",
          not isinstance(result, NeedsResolution) and names(result.main) == ["Robert Wolfe"], f"got {result!r}")

    # A name that merely resembles is not a name they answer to: a misspelling still asks,
    # because the same leniency would swallow "William Chen" into "Wilma Chen".
    result = Person.find(full_name="Ada Lovelase")
    check("a misspelling still asks", isinstance(result, NeedsResolution), f"got {result!r}")
    check("and says nothing matches exactly",
          isinstance(result, NeedsResolution) and "merely resemble" in result.reason)

    # Something that disagrees brings the question back: then the world really doesn't know.
    result = Person.get(full_name="Robert", email="someone.else@example.com")
    check("a value that disagrees makes it a question again", isinstance(result, NeedsResolution), f"got {result!r}")

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
    # "Data" is part of its recorded alias "Data Works", so it is a name this company answers
    # to — and it is the only one. A company that merely resembled would still ask.
    check("a company name it answers to, with no rival, is it",
          names(Organization.find(name="Data").main) == ["DataWorks"])

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

    # --- a title is how a name is said, not part of it: "Dr. Rao" is Arun Rao ---
    check("a name given with a title still resembles the person",
          matching.similarity("Dr. Rao", "Arun Rao") >= matching.PLAUSIBLE,
          str(matching.similarity("Dr. Rao", "Arun Rao")))

    # --- a merely similar name must not stop a new person from being recorded ---
    # "Wilma Chen" blocked "William Chen" from ever entering the world: new() returned a
    # question, nobody answered it, and the person simply wasn't there.
    made = Person.new(full_name="William Chen", email="william.chen@stripe.com")
    check("a name that merely resembles doesn't block a new record",
          not isinstance(made, NeedsResolution) and made.full_name == "William Chen", f"got {made!r}")
    twin = Person.new(full_name="William", email="other.william@example.com")
    check("a name they answer to still asks", isinstance(twin, NeedsResolution), f"got {twin!r}")

    # --- an unsettled question reads like an unsettled result ---
    # Host code checks a result the same way every time; when the question raised AttributeError
    # on .matched the run was rolled back and the question came back from scratch, four times.
    asked = Person.find(full_name="Annie")
    check("a question answers .matched with False", asked.matched is False)
    check("its candidates are there as .similar", names(asked.similar) == ["Anna Sullivan", "Anna Peterson"],
          str(names(asked.similar)))
    check("and it doesn't read as nothing at all", bool(asked) is True and list(asked) == [])

    # --- a lookup by an attribute the class hasn't got is a typo, not a miss ---
    typo = refused(lambda: Organization.find(full_name="TechCorp")) if "refused" in dir() else None
    if typo is None:
        try:
            Organization.find(full_name="TechCorp")
            typo = ""
        except TypeError as exc:
            typo = str(exc)
    check("looking up by an attribute the class lacks says so",
          "no attribute 'full_name'" in typo and "did you mean 'name'" in typo, typo or "(no error)")

    # --- when there is no answer, say what was probably meant (docs/architecture.md) ---
    def refusal(action):
        try:
            action()
            return ""
        except (TypeError, ValueError, AttributeError) as exc:
            return str(exc)

    ada = Person.get(email="ada@example.com")
    cases = [
        (lambda: Organization.find(full_name="TechCorp"), "did you mean 'name'"),
        (lambda: setattr(ada, "fullname", "x"), "did you mean 'full_name'"),
        (lambda: ada.add("descrptions", "note"), "did you mean 'descriptions'"),
        (lambda: ada.relate(Organization.get(name="TechCorp"), "memberships"), "did you mean 'membership'"),
    ]
    for action, wanted in cases:
        said = refusal(action)
        check(f"a near miss is named: {wanted}", wanted in said, said or "(no refusal)")
    check("and the same question twice gets the same answer",
          refusal(lambda: Organization.find(full_name="TechCorp"))
          == refusal(lambda: Organization.find(full_name="TechCorp")))
    check("nothing close enough is simply refused, not guessed at",
          "did you mean" not in refusal(lambda: Organization.find(zzzz="x")))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all find tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
