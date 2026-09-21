"""Tests for relations: instances linking two entities, and what the world checks about them.

Run: .venv/bin/python tests/test_relations.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.store import Store
from terraweaver.world import World
from worlds.job_search import build

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def refused(action) -> str | None:
    try:
        action()
    except (ValueError, TypeError) as exc:
        return str(exc)
    return None


def main() -> int:
    classes = build_classes(load_specs(ONTOLOGY_DIR), IMPLS)
    store = Store(":memory:")
    build(classes, store)
    world = World(store, classes)
    Person, Organization = classes["Person"], classes["Organization"]
    owner = world.owner

    # --- the fixture's links are relations now ---
    ada = Person.get(email="ada@example.com")
    techcorp = Organization.get(name="TechCorp")
    check("organization reads the primary membership", ada.organization is techcorp)
    check("job_title reads its role", ada.job_title == "Staff Engineer")
    check("employees read the memberships", ada in techcorp.employees)
    bob = Person.get(email="robert@example.com")
    check("a relationship to the owner reads from relations", bob.relationship == "former manager", str(bob.relationship))
    check("a recruiter is a Service to the owner",
          Person.get(email="anna.peterson@example.com").relationship == "recruiter")

    # --- symmetric: seen from both ends ---
    darren = Person.new(full_name="Darren Liu", email="darren@example.com")
    kevin = Person.new(full_name="Kevin Liu", email="kevin.liu@example.com")
    kevin.relate(darren, "kin", label="older brother")
    check("a symmetric relation is seen from both ends",
          darren.related("kin") == [kevin] and kevin.related("kin") == [darren])
    again = kevin.relate(darren, "kin", label="older brother")
    check("relating again updates, doesn't duplicate", len(darren.relations("kin")) == 1 and again is darren.relations("kin")[0])
    darren.relate(kevin, "kin", label="younger brother")
    tie = darren.relations("kin")[0]
    check("each side of a symmetric relation keeps its own label",
          tie.label == "older brother" and tie.label_reverse == "younger brother", f"{tie.label} / {tie.label_reverse}")
    check("a relation can't link something to itself", refused(lambda: kevin.relate(kevin, "social")) is not None)

    # --- one at a time: overlapping periods, not "now" ---
    naomi = Person.new(full_name="Naomi Park", email="naomi@example.com")
    lena = Person.new(full_name="Lena Ross", email="lena@example.com")
    first = darren.relate(naomi, "partner", label="girlfriend", starts=date(2024, 9, 1))
    check("a second current partner is refused", refused(lambda: darren.relate(lena, "partner")) is not None)
    first.keep(until=date(2026, 1, 1))
    check("after the first one ended, a new one goes through",
          refused(lambda: darren.relate(lena, "partner", starts=date(2026, 3, 1))) is None)
    check("and the ended one is history", darren.related("partner") == [lena]
          and naomi in darren.related("partner", history=True))

    # --- direction, reverse names, chains ---
    company = Organization.new(name="Meridian Corp")
    b04 = Organization.new(name="Supply Chain Operations", aliases=["B04"])
    b04.relate(company, "part_of", label="department")
    chen = Person.new(full_name="Kevin Chen", email="kchen@meridian.example")
    job = chen.relate(b04, "membership", title="vendor logistics lead", starts=date(2026, 1, 15))
    linda = Person.new(full_name="Linda Zhao", email="lzhao@meridian.example")
    linda.relate(b04, "authority", label="manager")
    check("read from the object's end by the reverse name", b04.related("members") == [chen])
    check("a membership extends along part_of", chen.related("membership") == [b04, company],
          str(chen.related("membership")))
    check("who manages the department", b04.related("managed_by") == [linda])
    check("a cycle of parts is refused", refused(lambda: company.relate(b04, "part_of")) is not None)
    check("a second current manager of the same department is refused",
          refused(lambda: chen.relate(b04, "authority")) is not None)
    check("an endpoint of the wrong class is refused", refused(lambda: b04.relate(chen, "kin")) is not None)

    # --- a relation is an instance: attributes, history, comments ---
    job.title = "team lead"
    check("a relation's attribute keeps its history", [p.value for p in job.history("title")] == ["vendor logistics lead", "team lead"])
    job.describe("moved from Procurement")
    check("a relation takes comments", bool(job.described(contains="Procurement")))

    # --- organization assignment moves the primary membership ---
    ada.organization = Organization.get(name="DataWorks")
    check("a new job closes the old one", techcorp not in ada.related("membership")
          and techcorp in ada.related("membership", history=True))
    check("and the job history comes from memberships",
          [p.value.name for p in ada.history("organization")] == ["TechCorp", "DataWorks"])

    # --- construction with relation-backed fields ---
    priya = Person.new(full_name="Priya Shah", email="priya@example.com",
                       organization=Organization.get(name="GreenGrid"), job_title="Data Engineer",
                       relationship="friend")
    check("organization, job title and relationship given at creation become relations",
          priya.organization.name == "GreenGrid" and priya.job_title == "Data Engineer" and priya.relationship == "friend")

    # --- the free type ---
    godfather = Person.new(full_name="Victor Hale", email="victor@example.com")
    check("Related needs a label and a description", refused(lambda: godfather.relate(priya, "related")) is not None)
    check("with them it goes through", refused(lambda: godfather.relate(
        priya, "related", label="godfather", description="Priya's godfather")) is None)

    # --- roles: limits, inverses, chains ---
    maria = Person.new(full_name="Maria Gribova", email="maria@example.com")
    mom = maria.relate(owner, "kin", label="mom")
    check("a label is matched to a role", mom.role == "mother" and mom.role_of(owner) == "child")
    olga = Person.new(full_name="Olga Petrova", email="olga.p@example.com")
    second = refused(lambda: olga.relate(owner, "kin", label="mother"))
    check("a second mother is refused, naming the alternative", second is not None and "stepmother" in second, str(second))
    check("a stepmother goes through", refused(lambda: olga.relate(owner, "kin", label="stepmother")) is None)
    sister = Person.new(full_name="Olga Gribova", email="olga@example.com")
    owner.relate(sister, "kin", label="brother")
    mark = Person.new(full_name="Mark Stone", email="mark@example.com")
    mark.relate(sister, "partner", label="husband")
    check("a chain is named", (owner.how_related(mark) or "").startswith("Mark Stone is Michael's sibling in law"),
          str(owner.how_related(mark)))
    meridian = Organization.get(name="Meridian Corp")
    ceo = Person.new(full_name="Ruth Adler", email="ruth@meridian.example")
    ceo.relate(meridian, "membership", role="Chief Executive Officer")
    check("a free-text role becomes the title, and the role is found in it",
          ceo.relations("membership")[0].title == "Chief Executive Officer" and ceo.relations("membership")[0].role == "ceo")
    other = Person.new(full_name="Sam Cole", email="sam@meridian.example")
    check("a second current CEO is refused", refused(lambda: other.relate(meridian, "membership", title="CEO")) is not None)
    check("founders can be many", refused(lambda: other.relate(meridian, "membership", title="co-founder")) is None
          and refused(lambda: ceo.relate(meridian, "membership", label="founder")) is None)
    check("a relation reads as a sentence", mom.display_name() == "Maria Gribova is Michael's mom (kin)", mom.display_name())
    check("its period reads under the names it's written with", job.starts is not None and job.until is None)

    # --- new() asks about someone the name merely resembles ---
    maybe = Person.new(full_name="Darren", email="d@example.org")
    check("new() with a resembling name asks instead of creating", getattr(maybe, "skill", None) == "resolve_ambiguity")

    # --- find compares entities by identity, not name ---
    twin = Organization.new(name="Meridian Corp (Boston)")
    check("find by a referenced entity matches that record only",
          [p.full_name for p in Person.find(organization=b04).main] == ["Kevin Chen"])

    # --- the end you didn't ask from has a name ---
    served = owner.relations("served_by")
    check("a relation read from one end knows the other",
          served and served[0].counterpart is not owner, str(served[:1]))
    loose = refused(lambda: served[0].related("service"))
    check("and asking it for 'the related one' points at that name",
          loose is not None and "counterpart" in (loose or ""), str(loose))

    # --- asked the wrong way round, answered the right way round, with the correction said ---
    from terraweaver import ontology

    right = owner.relations("served_by")
    with ontology.record_changes() as noted:
        wrong_way = owner.relations("service")
    check("the end with nothing on it answers from the end that has it",
          [r.id for r in wrong_way] == [r.id for r in right], str(wrong_way))
    hint = " ".join(noted.hints)
    check("and the wording is corrected, not left silent",
          "served_by" in hint and "other way" in hint, hint or "(no hint)")
    check("what comes back is usable from the end that was asked",
          wrong_way and wrong_way[0].counterpart is not owner)
    with ontology.record_changes() as quiet:
        owner.relations("served_by")
    check("nothing is corrected when the question was right to begin with",
          not any("other way" in h for h in quiet.hints), str(quiet.hints))
    with ontology.record_changes() as neither:
        check("and an end with nothing on either side is still empty",
              Person.new(full_name="Nobody Atall").relations("service") == [])
    check("with nothing to correct", not any("other way" in h for h in neither.hints))
    reads = [r.display_name() for r in right]
    check("a relation to the owner reads as English", not any("you's" in r for r in reads),
          str(reads[:2]))

    # --- a handover that leaves a day with nobody in the post ---
    with ontology.record_changes() as handover:
        leaving = Person.new(full_name="Otto Vane")
        old_post = leaving.relate(owner, "service", label="gardener")
        old_post.keep(until=date(2026, 9, 30))
        Person.new(full_name="Vera Lund").relate(owner, "service", label="gardener",
                                                 starts=date(2026, 10, 1))
    said = " ".join(handover.hints)
    check("a gap between two spells of one post is pointed out",
          "leaving no gardener in between" in said and "2026-10-01" in said, said or "(no hint)")
    with ontology.record_changes() as clean:
        Person.new(full_name="Wim Toll").relate(owner, "service", label="plumber",
                                                starts=date(2026, 10, 1))
    check("and nothing is said when there was nobody in the post before",
          not any("in between" in line for line in clean.hints), str(clean.hints))

    with ontology.record_changes() as ended_today:
        gone = Person.new(full_name="Nils Board")
        post = gone.relate(owner, "service", label="tutor")
        Person.new(full_name="Ida Board").relate(owner, "service", label="tutor",
                                                 starts=date(2026, 10, 1))
        post.expire()
    check("ending the old one today when the new starts later is pointed out too",
          any("leaving no tutor in between" in line for line in ended_today.hints),
          str(ended_today.hints))

    # --- a link that runs against every other of its label, where no type check can see it ---
    with ontology.record_changes() as flipped:
        vet = Person.new(full_name="Hugo Salt")
        vet.relate(owner, "service", label="vet")
        pet_person = Person.new(full_name="Mila Salt")
        owner.relate(pet_person, "service", label="vet")  # the wrong way round; both are people
    check("a reversed link is caught by the world's own data",
          any("goes the other way" in line for line in flipped.hints), str(flipped.hints))
    with ontology.record_changes() as first_of_its_kind:
        Person.new(full_name="Cleo Salt").relate(owner, "service", label="chiropractor")
    check("and the first link of a label is not second-guessed",
          not any("goes the other way" in line for line in first_of_its_kind.hints),
          str(first_of_its_kind.hints))

    # --- a move announced ahead of time is refused with the date, not with "expire it" ---
    holder = Person.new(full_name="Rita Vale")
    north = Organization.new(name="Northwind Freight")
    south = Organization.new(name="Southwind Freight")
    holder.relate(north, "membership", title="lead", primary=True)
    clash = refused(lambda: holder.relate(south, "membership", title="lead", primary=True,
                                          starts=date(2027, 3, 1)))
    check("a link that starts later is refused with the date that makes room",
          clash is not None and "keep(until=2027-03-01)" in clash, str(clash))
    check("and not with advice that would end it today", clash is not None and ".expire()" not in clash)

    # --- a question at either end holds the link rather than discarding the run ---
    unsettled = Organization.new(name="TechCorp")            # a twin exists, so this is a question
    linked = Person.new(full_name="Vera Holt", email="vera@holt.example")
    linked.relate(unsettled, "membership", title="director", primary=True)
    alongside = Person.new(full_name="Wes Holt", email="wes@holt.example")
    check("the rest of the block survives a question at the far end", isinstance(alongside, Person))
    settled = world.settle(unsettled, Organization.get(name="TechCorp"))
    made = [r.display_name() for r in Person.get(email="vera@holt.example").relations("membership")]
    check("and the held link is made pointing the way it was written",
          any("Vera Holt is TechCorp's" in line for line in made), str(made))

    # --- an unanswered question is not an entity to link, so the link waits for the answer ---
    asked = Person.new(full_name="Darren")  # resembles Darren Liu: a question, not a person
    with ontology.record_changes() as waiting:
        owner.relate(asked, "social", label="friend")
    check("linking to an unsettled question is held, not refused",
          any("held until that is settled" in line for line in waiting.hints), str(waiting.hints))
    friend = world.settle(asked, Person.get(full_name="Darren Liu"))
    check("and is made, the way it was written, once the question is answered",
          any(r.other(friend) is owner for r in friend.relations("social")),
          str([r.display_name() for r in friend.relations("social")]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all relation tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
