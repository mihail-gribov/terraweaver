"""Tests for relations: instances linking two entities, and what the world checks about them.

Run: .venv/bin/python tests/test_relations.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver import initiative
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
    # A department's manager changing is a handover, not a conflict: authority runs one way, so
    # the role moved and nobody is displaced by it. What the world refuses to decide alone is a
    # symmetric link — a partnership is a state two people are in together.
    chen.relate(b04, "authority")
    check("a new manager takes over from the last", b04.related("managed_by") == [chen],
          str(b04.related("managed_by")))
    check("and the one before is still in the record",
          linda in b04.related("managed_by", history=True),
          str(b04.related("managed_by", history=True)))
    # Classes are not fixed on a relation. What a type has run between so far describes it; a
    # link between other ends is news about the type, not an error in the link, so it is recorded
    # as asked and the world says what it noticed.
    kept = b04.relate(chen, "kin")
    check("an endpoint of another class is recorded all the same",
          type(kept).__name__ == "Kin" and kept.subject is b04, repr(kept))
    # Something the world does on its own, so the test says so: initiative.MAKES_TYPES is off
    # by default and the switch is turned on here and put back after.
    initiative.MAKES_TYPES = True
    # A word with no type behind it makes one, rather than being filed as a labelled link that
    # nobody ever comes back to name. The host's word stays the kind; the class is named the
    # way this world names classes, so the catalogue reads as one vocabulary.
    grown = type(b04.relate(chen, "keeps_bees_for"))
    check("and an unknown word makes the type it needs",
          grown.__name__ == "KeepsBeesFor" and grown._spec["relation"]["kind"] == "keeps_bees_for",
          f"{grown.__name__} / {grown._spec['relation']['kind']}")
    check("and the world says what it assumed about it",
          grown._spec["relation"]["nature"] == "related_to",
          str(grown._spec["relation"].get("nature")))
    initiative.MAKES_TYPES = False

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
          [p.full_name for p in Person.find(organization=b04).matches] == ["Kevin Chen"])

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

    # --- a link the world worked out is a conclusion, and can be dropped as a guess ---
    ana = Person.new(full_name="Ana Borg", email="ana@borg.example")
    ana.describe("famous for the Shahnameh")
    note = world.facts.about(ana.subject_id, "descriptions")[0]
    book = world.classes["Idea"].new(title="Shahnameh", content="an epic")
    guess = world.relate(ana, book, "related", label="famous for", description="from a note",
                         basis=[note])
    made = world.facts.about(guess.id)
    check("a derived link is written as the world's own conclusion",
          made and all(s.is_conclusion and s.source == "world" for s in made),
          str([(s.slot, s.source) for s in made]))
    check("and it knows what it rests on",
          all(note.id in (s.basis or []) for s in made), str([s.basis for s in made]))
    guess.retract("the note meant someone else")
    check("retracting a guess removes the link rather than ending it",
          not [r for r in ana.relations("related", any_time=True)],
          str([r.display_name() for r in ana.relations("related", any_time=True)]))
    check("and leaves what it was drawn from untouched",
          [s.value for s in world.facts.about(ana.subject_id, "descriptions")] == ["famous for the Shahnameh"])
    # --- a conclusion takes its place in time, and a later one closes an earlier one ---
    from datetime import date as _date

    moved = Person.new(full_name="Cedric Klapisch", email="cedric@x.example")
    moved.describe("citizen of France", when=_date(2026, 3, 1))
    moved.describe("citizen of Malaysia", when=_date(2026, 6, 1))
    told = sorted(world.facts.about(moved.subject_id, "descriptions"),
                  key=lambda s: s.valid_from or s.stated_at)
    fr = world.classes["Place"].new(name="France", city="Paris", category="other")
    my = world.classes["Place"].new(name="Malaysia", city="Kuala Lumpur", category="other")
    early = world.relate(moved, fr, "located", starts=told[0].valid_from, basis=[told[0]])
    check("a derived link holds from the moment of what it was drawn from",
          early.starts == _date(2026, 3, 1), str(early.starts))
    check("and its statements carry that moment, not now",
          all(s.valid_from is not None for s in world.facts.about(early.id)),
          str([(s.slot, s.valid_from) for s in world.facts.about(early.id)]))

    # --- what was said is read before what was worked out ---
    from datetime import date as _d

    stayed = Person.new(full_name="Ines Vale", email="ines@vale.example")
    here = world.classes["Place"].new(name="Porto", city="Porto", category="other")
    stayed.relate(here, "located", starts=_d(2026, 3, 1))          # the person said so
    stayed.describe("seems to have moved to Lisbon", when=_d(2026, 6, 1))
    guessed_from = [s for s in world.facts.about(stayed.subject_id, "descriptions")][0]
    there = world.classes["Place"].new(name="Lisbon", city="Lisbon", category="other")
    world.relate(stayed, there, "located", starts=guessed_from.valid_from, basis=[guessed_from])
    check("a link the world worked out is read after one the person stated, however new it is",
          [p.name for p in stayed.related("located")] == ["Porto", "Lisbon"],
          str([p.name for p in stayed.related("located")]))

    stated = world.relate(ana, book, "related", label="wrote", description="the user said so")
    refused_retract = ""
    try:
        stated.retract()
    except TypeError as exc:
        refused_retract = str(exc)
    check("a stated link is not retractable — what was said stays",
          "what was said stays" in refused_retract, refused_retract or "(allowed)")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all relation tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
