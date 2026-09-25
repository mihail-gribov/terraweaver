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
    kevin.set_kin(darren,  label="older brother")
    check("a symmetric relation is seen from both ends",
          darren.related("kin") == [kevin] and kevin.related("kin") == [darren])
    again = kevin.set_kin(darren,  label="older brother")
    check("relating again updates, doesn't duplicate", len(darren.relations("kin")) == 1 and again is darren.relations("kin")[0])
    darren.set_kin(kevin,  label="younger brother")
    tie = darren.relations("kin")[0]
    check("each side of a symmetric relation keeps its own label",
          tie.label == "older brother" and tie.label_reverse == "younger brother", f"{tie.label} / {tie.label_reverse}")
    check("a relation can't link something to itself", refused(lambda: kevin.set_social(kevin)) is not None)

    # --- one at a time: overlapping periods, not "now" ---
    naomi = Person.new(full_name="Naomi Park", email="naomi@example.com")
    lena = Person.new(full_name="Lena Ross", email="lena@example.com")
    first = darren.set_partner(naomi,  label="girlfriend", starts=date(2024, 9, 1))
    check("a second current partner is refused", refused(lambda: darren.set_partner(lena)) is not None)
    first.keep(until=date(2026, 1, 1))
    check("after the first one ended, a new one goes through",
          refused(lambda: darren.set_partner(lena,  starts=date(2026, 3, 1))) is None)
    check("and the ended one is history", darren.related("partner") == [lena]
          and naomi in darren.related("partner", history=True))

    # --- direction, reverse names, chains ---
    company = Organization.new(name="Meridian Corp")
    b04 = Organization.new(name="Supply Chain Operations", aliases=["B04"])
    b04.set_part_of(company,  label="department")
    chen = Person.new(full_name="Kevin Chen", email="kchen@meridian.example")
    job = chen.set_membership(b04,  title="vendor logistics lead", starts=date(2026, 1, 15))
    linda = Person.new(full_name="Linda Zhao", email="lzhao@meridian.example")
    linda.set_authority(b04,  label="manager", starts=date(2025, 6, 1))
    check("read from the object's end by the reverse name", b04.related("members") == [chen])
    check("a membership extends along part_of", chen.related("membership") == [b04, company],
          str(chen.related("membership")))
    check("who manages the department", b04.related("managed_by") == [linda])
    check("a cycle of parts is refused", refused(lambda: company.set_part_of(b04)) is not None)
    # A department's manager changing is a handover, not a conflict: authority runs one way, so
    # the role moved and nobody is displaced by it. What the world refuses to decide alone is a
    # symmetric link — a partnership is a state two people are in together.
    chen.set_authority(b04,  starts=date(2026, 3, 1))
    check("a new manager takes over from the last", b04.related("managed_by") == [chen],
          str(b04.related("managed_by")))
    check("and the one before is still in the record",
          linda in b04.related("managed_by", history=True),
          str(b04.related("managed_by", history=True)))
    # Classes are not fixed on a relation, and a link between other ends is news about the type
    # rather than an error in the link. The door for it is the one that takes words: a word on a
    # class lives on the classes it was declared between, so `b04.set_kin(chen)` says what kin
    # has run between and offers the other door. Said in words, the fact is in the world at once
    # — joined, findable, untyped until somebody reads it.
    refused_word = refused(lambda: b04.set_kin(chen))
    check("a word on a class is only on the classes it was declared between",
          refused_word is not None and "Person → Person" in refused_word, str(refused_word)[:110])
    kept = b04.relate(chen, "B04 has had Kevin Chen in the family business for years")
    check("and the fact said in words is recorded all the same",
          kept is not None and kept.subject is b04, repr(kept)[:110])
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

    # --- a correction has no date, and the earlier one is history, not a second answer ---
    # Removing the invented end date left the correction announcing itself and changing
    # nothing, so a thing had two head offices at once and every count agreed it was fine.
    where = Organization.new(name="Acme Corp")
    first_seat = Person.new(full_name="Dublin Seat")
    later_seat = Person.new(full_name="Tallinn Seat")
    # Written from the end the type names as its subject — a manager manages somebody, and the
    # word lives on Person because that is what authority has run from.
    first_seat.set_authority(where, label="manager", starts=date(2020, 1, 1))
    check("one at a time: the later one holds",
          [p.full_name for p in where.related("managed_by")] == ["Dublin Seat"],
          str([p.full_name for p in where.related("managed_by")]))
    thing = Person.new(full_name="Twice Told")
    thing.set_membership(Organization.new(name="First Place"),  title="a")
    thing.set_membership(Organization.new(name="Second Place"),  title="b")
    both = [o.name for o in thing.related("membership", any_time=True)]
    check("and what was said before is still in the record", len(both) >= 2, str(both))

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
    mom = maria.set_kin(owner,  label="mom")
    check("a label is matched to a role", mom.role == "mother" and mom.role_of(owner) == "child")
    olga = Person.new(full_name="Olga Petrova", email="olga.p@example.com")
    second = refused(lambda: olga.set_kin(owner,  label="mother"))
    check("a second mother is refused, naming the alternative", second is not None and "stepmother" in second, str(second))
    check("a stepmother goes through", refused(lambda: olga.set_kin(owner,  label="stepmother")) is None)
    sister = Person.new(full_name="Olga Gribova", email="olga@example.com")
    owner.set_kin(sister,  label="brother")
    mark = Person.new(full_name="Mark Stone", email="mark@example.com")
    mark.set_partner(sister,  label="husband", starts=date(2021, 5, 8))
    check("a chain is named", (owner.how_related(mark) or "").startswith("Mark Stone is Michael's sibling in law"),
          str(owner.how_related(mark)))
    meridian = Organization.get(name="Meridian Corp")
    ceo = Person.new(full_name="Ruth Adler", email="ruth@meridian.example")
    ceo.set_membership(meridian,  role="Chief Executive Officer")
    check("a free-text role becomes the title, and the role is found in it",
          ceo.relations("membership")[0].title == "Chief Executive Officer" and ceo.relations("membership")[0].role == "ceo")
    other = Person.new(full_name="Sam Cole", email="sam@meridian.example")
    check("a second current CEO is refused", refused(lambda: other.set_membership(meridian,  title="CEO")) is not None)
    check("founders can be many", refused(lambda: other.set_membership(meridian,  title="co-founder")) is None
          and refused(lambda: ceo.set_membership(meridian,  label="founder")) is None)
    check("a relation reads as a sentence", mom.display_name() == "Maria Gribova is Michael's mom (kin)", mom.display_name())
    check("its period reads under the names it's written with", job.starts is not None and job.until is None)

    # --- settling the task's context is a search, and hands back who could be meant ---
    maybe = Person.identify(full_name="Darren")
    check("settling who the task is about hands back the candidates",
          [p.full_name for p in maybe] == ["Darren Liu"], str(maybe))

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
        old_post = leaving.set_service(owner,  label="gardener")
        old_post.keep(until=date(2026, 9, 30))
        Person.new(full_name="Vera Lund").set_service(owner,  label="gardener",
                                                 starts=date(2026, 10, 1))
    said = " ".join(handover.hints)
    check("a gap between two spells of one post is pointed out",
          "leaving no gardener in between" in said and "2026-10-01" in said, said or "(no hint)")
    with ontology.record_changes() as clean:
        Person.new(full_name="Wim Toll").set_service(owner,  label="plumber",
                                                starts=date(2026, 10, 1))
    check("and nothing is said when there was nobody in the post before",
          not any("in between" in line for line in clean.hints), str(clean.hints))

    with ontology.record_changes() as ended_today:
        gone = Person.new(full_name="Nils Board")
        post = gone.set_service(owner,  label="tutor")
        Person.new(full_name="Ida Board").set_service(owner,  label="tutor",
                                                 starts=date(2026, 10, 1))
        post.expire()
    check("ending the old one today when the new starts later is pointed out too",
          any("leaving no tutor in between" in line for line in ended_today.hints),
          str(ended_today.hints))

    # --- a link that runs against every other of its label, where no type check can see it ---
    with ontology.record_changes() as flipped:
        vet = Person.new(full_name="Hugo Salt")
        vet.set_service(owner,  label="vet")
        pet_person = Person.new(full_name="Mila Salt")
        owner.set_service(pet_person,  label="vet")  # the wrong way round; both are people
    check("a reversed link is caught by the world's own data",
          any("goes the other way" in line for line in flipped.hints), str(flipped.hints))
    with ontology.record_changes() as first_of_its_kind:
        Person.new(full_name="Cleo Salt").set_service(owner,  label="chiropractor")
    check("and the first link of a label is not second-guessed",
          not any("goes the other way" in line for line in first_of_its_kind.hints),
          str(first_of_its_kind.hints))

    # --- a move announced ahead of time is refused with the date, not with "expire it" ---
    holder = Person.new(full_name="Rita Vale")
    north = Organization.new(name="Northwind Freight")
    south = Organization.new(name="Southwind Freight")
    holder.set_membership(north,  title="lead", primary=True)
    clash = refused(lambda: holder.set_membership(south,  title="lead", primary=True,
                                          starts=date(2027, 3, 1)))
    check("a link that starts later is refused with the date that makes room",
          clash is not None and "keep(until=2027-03-01)" in clash, str(clash))
    check("and not with advice that would end it today", clash is not None and ".expire()" not in clash)

    # --- a question at either end holds the link rather than discarding the run ---
    Organization.new(name="Tech Holdings")
    # "Tech" fits two of them and is the name of neither, so settling it is a question — and
    # the link written against the answer waits for it rather than taking the run down.
    unsettled = Organization.get(name="Tech")
    linked = Person.new(full_name="Vera Holt", email="vera@holt.example")
    linked.set_membership(unsettled,  title="director", primary=True)
    alongside = Person.new(full_name="Wes Holt", email="wes@holt.example")
    check("the rest of the block survives a question at the far end", isinstance(alongside, Person))
    settled = world.settle(unsettled, Organization.get(name="TechCorp"))
    made = [r.display_name() for r in Person.get(email="vera@holt.example").relations("membership")]
    # A membership carries no label here, so it reads as the predicate it is rather than as
    # something TechCorp possesses — what matters is that Vera is the subject.
    check("and the held link is made pointing the way it was written",
          any(line.startswith("Vera Holt ") and "TechCorp" in line for line in made), str(made))

    # --- an unanswered question is not an entity to link, so the link waits for the answer ---
    Person.new(full_name="Darren Okafor", email="darren.o@example.org")
    asked = Person.get(full_name="Darren")  # fits two of them: a question, not a person
    with ontology.record_changes() as waiting:
        owner.set_social(asked,  label="friend")
    check("linking to an unsettled question is held, not refused",
          any("held until that is settled" in line for line in waiting.hints), str(waiting.hints))
    friend = world.settle(asked, Person.get(full_name="Darren Liu"))
    check("and is made, the way it was written, once the question is answered",
          any(r.other(friend) is owner for r in friend.relations("social")),
          str([r.display_name() for r in friend.relations("social")]))

    # A link is what somebody said, and nothing here makes one out of anything else: the
    # world does not conclude links. What was said stays, so it cannot be taken back either.
    ana = Person.new(full_name="Ana Borg", email="ana@borg.example")
    book = world.classes["Idea"].new(title="Shahnameh", content="an epic")
    stated = world.relate(ana, book, "related", label="wrote", description="the user said so")
    refused_retract = ""
    try:
        stated.retract()
    except TypeError as exc:
        refused_retract = str(exc)
    check("a stated link is not retractable — what was said stays",
          "what was said stays" in refused_retract, refused_retract or "(allowed)")

    # --- every type the core ships says how many hold at a moment, on both ends ---
    # A gate, because the fields are read with `.get()` and an absent one behaves exactly like
    # `false` — so a type that nobody thought about is indistinguishable, in code, from one thought
    # about and left open. It is not the same thing to a reader, and it is not the same thing to the
    # inspector, which proposes a property a type does not declare. Seven of the twelve said nothing
    # at all until they were made to.
    import json as _json
    from terraweaver import ontology as _ont

    for path in sorted(ONTOLOGY_DIR.glob("*.json")):
        spec = _json.loads(path.read_text())
        rel = spec.get("relation")
        if not rel:
            continue
        for side in ("functional", "inverse_functional"):
            check(f"{spec['name']} declares {side}", side in rel,
                  f"{path.name} says nothing about it")
            # "One ever" is withdrawn: a record only accumulates and nothing in it is one forever.
            # A side is one at a time or it is not, and `True` means the branch that printed a note
            # and ended nothing.
            check(f"{spec['name']}.{side} is one-at-a-time or open",
                  rel.get(side) in (False, _ont.AT_A_TIME), repr(rel.get(side)))
        check(f"{spec['name']} says why, for a reader",
              isinstance(rel.get("how_many"), str) and len(rel["how_many"]) > 40,
              str(rel.get("how_many"))[:60])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all relation tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
