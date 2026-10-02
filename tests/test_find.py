"""Tests for world lookup — the part everything else leans on.

`find` decides who the agent is talking about, so its behaviour can't be left to live
runs through a model: those are slow, costly, and vary between runs. These are plain
deterministic checks over the prepared world.

Run: python3 tests/test_find.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import matching
from terraweaver.resolution import NeedsResolution

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def fresh_world():
    """A base world and the cast the lookups talk about, said the way a host says them.

    Addresses and cities are attributes the world grows when it is told one; a vacancy is a class
    the world defines for itself — which is also the point: finding things in a class the world
    made works exactly as it does in one it started with.
    """
    rt = base.world(None)
    base.attribute(rt, "Person", "email", "The address this person reads their mail at.", type="email")
    base.attribute(rt, "Person", "city", "The city this person lives in.")
    rt.world.extras["define"](
        "Vacancy", "A job opening the user might apply for.", identified_by="title",
        attributes=[{"name": "title", "type": "str", "description": "What the job is called."},
                    {"name": "remote", "type": "bool", "description": "Whether it can be done from home."},
                    {"name": "status", "type": "enum[not_applied, applied, withdrawn]",
                     "description": "Where the user is with it."}])
    classes = rt.world.classes
    P, T, V = classes["Person"], classes["Thing"], classes["Vacancy"]
    P.new(name="Alan Turing")
    P.new(name="Barbara Liskov", aliases=["Barb"])
    P.new(name="Ada Lovelace", email="ada@example.com", city="London")
    P.new(name="Anna Sullivan", aliases=["Annie", "Ann"])
    P.new(name="Anna Peterson", aliases=["Annie"])
    P.new(name="Robert Wolfe", email="robert@wolfe.example")
    P.new(name="Wilma Chen")
    T.new(name="TechCorp")
    T.new(name="DataWorks", aliases=["Data Works", "DW"])
    V.new(title="Backend engineer", remote=True, status="not_applied")
    V.new(title="Data analyst", remote=True, status="applied")
    V.new(title="Office manager", remote=False, status="not_applied")
    return rt, classes, rt.world


def names(result) -> list[str]:
    return [getattr(e, "full_name", None) or getattr(e, "title", None) or e.name for e in result]


def main() -> int:
    rt, classes, world = fresh_world()
    Person, Thing, Vacancy = classes["Person"], classes["Thing"], classes["Vacancy"]

    # --- a name that identifies exactly one person ---
    result = Person.find(name="Alan Turing")
    check("exact full name matches", not isinstance(result, NeedsResolution) and names(result.matches) == ["Alan Turing"])

    result = Person.find(name="Barb")
    check("recorded alias matches", not isinstance(result, NeedsResolution) and names(result.matches) == ["Barbara Liskov"],
          f"got {result!r}")

    result = Person.find(name="Barb Liskov")
    check("nickname with surname matches", not isinstance(result, NeedsResolution)
          and names(result.matches) == ["Barbara Liskov"], f"got {result!r}")

    result = Person.find(email="ada@example.com")
    check("strong key matches without a name", not isinstance(result, NeedsResolution)
          and names(result.matches) == ["Ada Lovelace"])

    # --- a name that doesn't settle it: the user has to ---
    result = Person.find(name="Annie")
    check("shared alias asks", isinstance(result, NeedsResolution) and len(result.candidates) == 2, f"got {result!r}")
    check("shared alias says several match", isinstance(result, NeedsResolution) and "equally well" in result.reason)

    # A name the entity answers to — part of its name — with nothing that disagrees, is them:
    # "Robert" is his first name, and he is the only person in this world it can mean.
    result = Person.find(name="Robert")
    check("a bare first name with one candidate is them",
          not isinstance(result, NeedsResolution) and names(result.matches) == ["Robert Wolfe"], f"got {result!r}")

    # A name that merely resembles is not a name they answer to: a misspelling still asks,
    # because the same leniency would swallow "William Chen" into "Wilma Chen".
    result = Person.find(name="Ada Lovelase")
    check("a misspelling still asks", isinstance(result, NeedsResolution), f"got {result!r}")
    check("and says nothing matches exactly",
          isinstance(result, NeedsResolution) and "merely resemble" in result.reason)

    # Something that disagrees brings the question back: then the world really doesn't know.
    result = Person.get(name="Robert", email="someone.else@example.com")
    check("a value that disagrees makes it a question again", isinstance(result, NeedsResolution), f"got {result!r}")

    # --- match and resemblance are kept apart ---
    result = Person.find(name="Ann")
    check("one certain match wins", not isinstance(result, NeedsResolution) and names(result.matches) == ["Anna Sullivan"],
          f"got {result!r}")
    check("resemblances are set aside, not dropped",
          not isinstance(result, NeedsResolution) and names(result.similar) == ["Anna Peterson"])
    check("iterating still yields everything",
          not isinstance(result, NeedsResolution) and len(result) == 2)

    # --- nobody at all ---
    result = Person.find(name="Zoe")
    check("no candidates is an empty result, not a question",
          not isinstance(result, NeedsResolution) and not result.matched and len(result) == 0, f"got {result!r}")

    # --- ordinary attributes filter ---
    check("filters by an ordinary attribute", names(Person.find(city="London").matches) == ["Ada Lovelace"])
    check("filters by several attributes",
          all(v.remote and v.status == "not_applied" for v in Vacancy.find(remote=True, status="not_applied").matches))
    check("a filter that matches nothing yields nothing", len(Vacancy.find(status="withdrawn")) == 0)

    # A list attribute is satisfied by containing the value. Comparing the whole list to one
    # value matches nothing, and an empty result reads as "there are none" — confidently wrong.
    check("filters by membership of a list attribute",
          sorted(names(Person.find(aliases="Annie").matches)) == ["Anna Peterson", "Anna Sullivan"],
          str(names(Person.find(aliases="Annie").matches)))
    check("and a value that's in no list matches nothing", len(Person.find(aliases="Zed")) == 0)

    # --- things are found by the whole of a name they answer to ---
    check("a thing's alias matches", names(Thing.find(name="Data Works").matches) == ["DataWorks"])
    check("a thing's short form matches", names(Thing.find(name="DW").matches) == ["DataWorks"])
    # Not by part of one. "Data" is inside "Data Works", and matched that way "Berkeley" inside
    # "University of California, Berkeley" once cost a measured world twelve names. A person is
    # called by part of their name; a thing is not.
    check("a thing is not found by part of a name it answers to",
          names(Thing.find(name="Data").matches) == [], str(names(Thing.find(name="Data").matches)))

    # --- searching is not working with anything ---
    ada = Person.find(email="ada@example.com").matches[0]
    before = ada.accessed_at
    Person.find(name="Alan Turing")
    Person.find(city="London")
    check("a search leaves access times alone",
          Person.find(email="ada@example.com").matches[0].accessed_at == before)

    # --- equal relevance is broken by who was dealt with most recently ---
    remote = Vacancy.find(remote=True).matches
    world._determined(remote[-1])
    check("ties go to the most recently handled",
          Vacancy.find(remote=True).matches[0].id == remote[-1].id)

    # --- a title is how a name is said, not part of it: "Dr. Rao" is Arun Rao ---
    check("a name given with a title still resembles the person",
          matching.similarity("Dr. Rao", "Arun Rao") >= matching.PLAUSIBLE,
          str(matching.similarity("Dr. Rao", "Arun Rao")))

    # --- a merely similar name must not stop a new person from being recorded ---
    # "Wilma Chen" blocked "William Chen" from ever entering the world: new() returned a
    # question, nobody answered it, and the person simply wasn't there.
    made = Person.new(name="William Chen", email="william.chen@stripe.com")
    check("a name that merely resembles doesn't block a new record",
          not isinstance(made, NeedsResolution) and made.name == "William Chen", f"got {made!r}")
    # Settling who the task is about is a search: it hands back who could be meant and the
    # host, who has the conversation, reads them. "William" is a name William Chen answers to.
    could_be = Person.identify(name="William")
    check("settling who the task is about hands back the candidates to read, the one it names first",
          [p.name for p in could_be][:1] == ["William Chen"], str(could_be))
    check("and what merely resembles is there too, for the host to rule out",
          "Wilma Chen" in [p.name for p in could_be], str(could_be))
    made = Person.identify(name="Hokusai")
    check("and a name nobody here has is recorded rather than handed back empty",
          [p.name for p in made] == ["Hokusai"], str(made))
    check("while a search narrowed until nothing is left makes nothing — the name is here, "
          "the narrowing was too tight",
          Person.identify(name="William", city="Reykjavik") == [])
    # The same write outside that, mid-recording, takes what it is given: a run is not stopped
    # over a resemblance, and what turns out to be one thing is merged over the record later.
    written = Person.new(name="William", email="other.william@example.com")
    check("a write takes the name it is given rather than asking",
          not isinstance(written, NeedsResolution), f"got {written!r}")

    # --- an unsettled question reads like an unsettled result ---
    # Host code checks a result the same way every time; when the question raised AttributeError
    # on .matched the run was rolled back and the question came back from scratch, four times.
    asked = Person.find(name="Annie")
    check("a question answers .matched with False", asked.matched is False)
    check("its candidates are there as .similar",
          sorted(names(asked.similar)) == ["Anna Peterson", "Anna Sullivan"], str(names(asked.similar)))
    check("and it doesn't read as nothing at all", bool(asked) is True and list(asked) == [])

    # --- when there is no answer, say what was probably meant (docs/architecture.md) ---
    def refusal(action):
        try:
            action()
            return ""
        except (TypeError, ValueError, AttributeError) as exc:
            return str(exc)

    from terraweaver import ontology

    ada = Person.get(email="ada@example.com")
    # One close word and no other: answer the question they meant, and say what was read as
    # what. A refusal here costs the host a turn to learn something the world already knew.
    with ontology.record_changes() as spoke:
        found = Thing.find(full_name="TechCorp")
    check("a near-miss attribute answers the question it meant",
          found.matches and found.matches[0].name == "TechCorp", str(found))
    check("and the caveat is said out loud",
          any("'full_name' taken as 'name'" in line for line in spoke.assumed), str(spoke.assumed))

    with ontology.record_changes() as written:
        ada.add("descrptions", "keeps bees at the weekend")
    check("a near-miss slot is written where it was meant",
          "keeps bees at the weekend" in (ada.descriptions or []), str(ada.descriptions))
    check("with the caveat", any("taken as 'descriptions'" in line for line in written.assumed))

    check("the same question twice reads the same way",
          ontology.did_you_mean("full_name", ["name", "aliases"])
          == ontology.did_you_mean("full_name", ["name", "aliases"]) == "name")
    check("and nothing close enough is refused rather than guessed at",
          ontology.did_you_mean("zzzz", ["name", "aliases"]) is None)
    nothing_close = refusal(lambda: Thing.find(zzzz="x"))
    check("a refusal still names what the class does have",
          "no attribute 'zzzz'" in nothing_close and "did you mean" not in nothing_close,
          nothing_close or "(no refusal)")

    # --- a result with exactly one match answers as that one, and says so ---
    with ontology.record_changes() as one_match:
        got = Person.find(name="Ada Lovelace")
        check("a search result with one match reads as that one", got.name == "Ada Lovelace",
              str(got))
        check("through .matches as well", got.matches.email == "ada@example.com")
    check("and says where the answer came from",
          any("read from the one match" in line for line in one_match.assumed), str(one_match.assumed))

    several = Person.find(name="Annie")
    told = ""
    try:
        several.similar.name
    except AttributeError as exc:
        told = str(exc)
    check("with several it refuses and says which one to name",
          "one of them" in told and "result.similar[0]" in told, told or "(no refusal)")

    # --- .main is the one it found, or says why it can't be ---
    def why_not(action):
        try:
            action()
            return ""
        except AttributeError as exc:
            return str(exc)

    check("one match: .main is that one", Person.find(name="Ada Lovelace").main.email
          == "ada@example.com")
    crowded = why_not(lambda: Person.find(name="Anna").main)
    check("several: it says the search wasn't unambiguous and what would narrow it",
          "didn't settle" in crowded or "wasn't unambiguous" in crowded, crowded or "(no refusal)")
    check("and points at where to look", "similar" in crowded or "result.matches" in crowded, crowded)
    empty = why_not(lambda: Person.find(name="Nobody At All").main)
    check("none: it says nothing matched rather than serving the closest",
          "nothing in the world matches" in empty, empty or "(no refusal)")
    check("and names all three ways on: ask differently, or record it as new",
          "needs changing" in empty and "Person.new(...)" in empty, empty)

    # --- two more near misses, both seen costing a live host a statement ---
    dated = classes["Event"].new(title="Meetup", start_time=date(2026, 9, 24))
    check("a date where a datetime is wanted is that day's midnight",
          dated.start_time.hour == 0 and dated.start_time.day == 24, str(dated.start_time))
    # A class that called its name `title` calls it `name` like everything else, and the old
    # word still reads it.
    job = Vacancy.find(title="Backend engineer").matches[0]
    check("a title is the name", job.name == "Backend engineer" and job.title == "Backend engineer",
          f"{job.name!r} {job.title!r}")
    misread = ""
    try:
        job.statu
    except AttributeError as exc:
        misread = str(exc)
    check("reading an attribute that isn't there says which one was meant",
          "did you mean" in misread, misread or "(no refusal)")

    # --- the small accommodations, each one seen costing a live host a statement ---
    base.word(rt, "works_at", "a person working for an employer", "many-to-one",
              "a person who works", "their employer")
    ivo = Person.new(name="Ivo Sand", email="ivo@sand.example")
    link = ivo.set_works_at(Thing.get(name="TechCorp"))
    check("a relation says what kind of link it is", link.kind == "works_at", str(link.kind))
    check("and whether its period has run out", link.expired is False)
    listing = ""
    try:
        Person.find(name="Anna", limit=1)
    except TypeError as exc:
        listing = str(exc)
    check("find says it identifies rather than lists, instead of ignoring limit=",
          "Person.all(limit=...)" in listing, listing or "(accepted silently)")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all find tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
