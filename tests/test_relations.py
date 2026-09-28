"""Tests for relations: instances linking two entities, and what the world checks about them.

Every link here goes through a word the test declares the way a host does — `define_relation` with
a description, the two roles, and a cardinality. How many can hold at a moment is the only thing
that decides behaviour; the roles decide whether a word reads the same from both ends.

Run: .venv/bin/python tests/test_relations.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import initiative, ontology, relations  # noqa: E402

import base  # noqa: E402

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
    rt = base.world(None)
    world = rt.world
    base.attribute(rt, "Person", "email", "The address this person reads their mail at.", type="email")
    base.word(rt, "knows", "two people who know each other", "many-to-many",
              "an acquaintance", "an acquaintance")
    base.word(rt, "married_to", "two people married to each other", "one-to-one", "a spouse", "a spouse")
    base.word(rt, "works_at", "a person working for an employer", "many-to-one",
              "a person who works", "their employer")
    base.word(rt, "manages", "a person managing a team", "one-to-many",
              "the manager", "the team they manage")
    base.word(rt, "part_of", "a unit inside a larger one", "many-to-one", "the part", "the whole")
    Person, Thing, Event = world.classes["Person"], world.classes["Thing"], world.classes["Event"]
    owner = world.owner

    # --- the same role at both ends: seen from either ---
    darren = Person.new(full_name="Darren Liu", email="darren@example.com")
    kevin = Person.new(full_name="Kevin Liu", email="kevin.liu@example.com")
    kevin.set_knows(darren)
    check("a link with the same role at both ends is seen from both",
          darren.related("knows") == [kevin] and kevin.related("knows") == [darren])
    again = kevin.set_knows(darren)
    check("relating again doesn't duplicate",
          len(darren.relations("knows")) == 1 and again is darren.relations("knows")[0])
    darren.set_knows(kevin)
    check("nor does saying it from the other end", len(darren.relations("knows")) == 1)
    check("a link can't join something to itself", refused(lambda: kevin.set_knows(kevin)) is not None)

    # --- one at a time, and a state two people share is theirs to end ---
    naomi = Person.new(full_name="Naomi Park", email="naomi@example.com")
    lena = Person.new(full_name="Lena Ross", email="lena@example.com")
    first = darren.set_married_to(naomi, starts=date(2024, 9, 1))
    check("a second current spouse is refused rather than ending the first on its own",
          refused(lambda: darren.set_married_to(lena)) is not None)
    first.keep(until=date(2026, 1, 1))
    check("after the first one ended, a new one goes through",
          refused(lambda: darren.set_married_to(lena, starts=date(2026, 3, 1))) is None)
    check("and the ended one is history", darren.related("married_to") == [lena]
          and naomi in darren.related("married_to", history=True))

    # --- one way round: the role moves, nobody is displaced ---
    company = Thing.new(name="Meridian Corp")
    b04 = Thing.new(name="Supply Chain Operations", aliases=["B04"])
    b04.set_part_of(company)
    chen = Person.new(full_name="Kevin Chen", email="kchen@meridian.example")
    job = chen.set_works_at(b04, starts=date(2026, 1, 15))
    linda = Person.new(full_name="Linda Zhao", email="lzhao@meridian.example")
    linda.set_manages(b04, starts=date(2025, 6, 1))
    check("read from the object's end by the reverse name", b04.works_at_of == [chen], str(b04.works_at_of))
    check("one at the far end reads as that one", b04.manages_of is linda, str(b04.manages_of))
    chen.set_manages(b04, starts=date(2026, 3, 1))
    check("a new manager takes over from the last", b04.manages_of is chen, str(b04.manages_of))
    check("and the one before is still in the record",
          linda in b04.related("manages_of", history=True), str(b04.related("manages_of", history=True)))
    check("ending where the new one begins", linda.relations("manages", history=True)[0].valid_until
          == chen.relations("manages")[0].valid_from)

    # --- no date: the change happened before today, and the record says only that ---
    rita = Person.new(full_name="Rita Vale")
    north, south = Thing.new(name="Northwind Freight"), Thing.new(name="Southwind Freight")
    old = rita.set_works_at(north)
    new = rita.set_works_at(south)
    check("an undated link where one stood ends that one", old.valid_until is not None and rita.works_at is south)
    check("both bounds are one moment, said to be before it",
          old.valid_until == new.valid_from and old.until_is == new.from_is == "before",
          f"{old.valid_until} {old.until_is} / {new.valid_from} {new.from_is}")
    check("and what was said before is still in the record",
          sorted(o.name for o in rita.related("works_at", any_time=True))
          == ["Northwind Freight", "Southwind Freight"],
          str([o.name for o in rita.related("works_at", any_time=True)]))
    check("and the missing date is asked about",
          any(q.kind == "when_it_changed" for q in world.questions.open_(limit=50)))

    # --- a move announced ahead of time ends the old one where the new begins ---
    holder = Person.new(full_name="Ruth Adler")
    holder.set_works_at(north)
    ahead = holder.set_works_at(south, starts=date(2027, 3, 1))
    before = [r for r in holder.relations("works_at", history=True) if r.object is north][0]
    check("a link that starts later hands over at its start, not today",
          before.valid_until == ahead.valid_from and getattr(before, "until_is", None) != "before",
          f"{before.valid_until} {getattr(before, 'until_is', None)}")
    check("and until then the old one holds", holder.works_at is north, str(holder.works_at))

    # --- the far end is not checked against what the word was declared between ---
    # Classes on a word are watched, not enforced: a link between other ends is news about the
    # word rather than an error in the link.
    check("a word between other classes is taken", refused(lambda: b04.set_knows(chen)) is None)
    kept = b04.relate(chen, "B04 has had Kevin Chen in the family business for years")
    check("and a fact said in words is recorded all the same",
          kept is not None and kept.subject is b04, repr(kept)[:110])
    # Something the world does on its own, so the test says so: initiative.MAKES_TYPES is off by
    # default and the switch is turned on here and put back after. Called at the layer it governs:
    # through `relate` a word this world has no type for is words the user said, and typing them
    # is the reading's work at the close.
    initiative.MAKES_TYPES = True
    grown = type(relations.relate(world, b04, chen, "keeps_bees_for", {}, {}))
    check("and an unknown word makes the type it needs",
          grown.__name__ == "KeepsBeesFor" and grown._spec["relation"]["kind"] == "keeps_bees_for",
          f"{grown.__name__} / {grown._spec['relation']['kind']}")
    initiative.MAKES_TYPES = False

    # --- a relation is an instance: history and comments ---
    world.extras["define_relation"]("advises", "a person advising an organisation", cardinality="many-to-many",
                                    subject_is="the adviser", object_is="who they advise",
                                    attributes=[{"name": "role", "type": "str",
                                                 "description": "What the advice is about."}])
    advice = chen.set_advises(company)
    advice.role = "vendor logistics"
    advice.role = "procurement"
    check("a relation's attribute keeps its history",
          [p.value for p in advice.history("role")] == ["vendor logistics", "procurement"],
          str([p.value for p in advice.history("role")]))
    job.describe("moved from Procurement")
    check("a relation takes comments", bool(job.described(contains="Procurement")))
    check("its period reads under the names it's written with", job.starts is not None and job.until is None)

    # --- the free type ---
    godfather = Person.new(full_name="Victor Hale", email="victor@example.com")
    priya = Person.new(full_name="Priya Shah", email="priya@example.com")
    check("Related needs a label or a description", refused(lambda: godfather.relate(priya, "related")) is not None)
    check("with them it goes through", refused(lambda: godfather.relate(
        priya, "related", label="godfather", description="Priya's godfather")) is None)

    # --- settling the task's context is a search, and hands back who could be meant ---
    maybe = Person.identify(full_name="Darren")
    check("settling who the task is about hands back the candidates",
          [p.full_name for p in maybe] == ["Darren Liu"], str(maybe))

    # --- find compares entities by identity, not name ---
    Thing.new(name="Supply Chain Operations (Boston)")
    Event.new(title="Quarterly review", about=b04, start_time=date(2026, 10, 5))
    check("find by a referenced entity matches that record only",
          [e.title for e in Event.find(about=b04).matches] == ["Quarterly review"])

    # --- the end you didn't ask from has a name ---
    seen = b04.relations("works_at_of")
    check("a relation read from one end knows the other",
          seen and seen[0].counterpart is chen, str(seen[:1]))
    loose = refused(lambda: seen[0].related("works_at"))
    check("and asking it for 'the related one' points at that name",
          loose is not None and "counterpart" in loose, str(loose))

    # --- a question at either end holds the link rather than discarding the run ---
    Thing.new(name="Tech Holdings")
    Thing.new(name="TechCorp")
    # "Tech" fits two of them and is the name of neither, so settling it is a question — and
    # the link written against the answer waits for it rather than taking the run down.
    unsettled = Thing.get(name="Tech")
    linked = Person.new(full_name="Vera Holt", email="vera@holt.example")
    linked.set_works_at(unsettled)
    alongside = Person.new(full_name="Wes Holt", email="wes@holt.example")
    check("the rest of the block survives a question at the far end", isinstance(alongside, Person))
    world.settle(unsettled, Thing.get(name="TechCorp"))
    check("and the held link is made pointing the way it was written",
          Person.get(email="vera@holt.example").works_at.name == "TechCorp")

    # --- an unanswered question is not an entity to link, so the link waits for the answer ---
    Person.new(full_name="Darren Okafor", email="darren.o@example.org")
    asked = Person.get(full_name="Darren")  # fits two of them: a question, not a person
    with ontology.record_changes() as waiting:
        owner.set_knows(asked)
    check("linking to an unsettled question is held, not refused",
          any("held until that is settled" in line for line in waiting.hints), str(waiting.hints))
    friend = world.settle(asked, Person.get(full_name="Darren Liu"))
    check("and is made, the way it was written, once the question is answered",
          any(r.other(friend) is owner for r in friend.relations("knows")),
          str([r.display_name() for r in friend.relations("knows")]))

    # A link is what somebody said, and nothing here makes one out of anything else: the
    # world does not conclude links. What was said stays, so it cannot be taken back either.
    ana = Person.new(full_name="Ana Borg", email="ana@borg.example")
    stated = world.relate(ana, Thing.new(name="Shahnameh"), "related", label="wrote",
                          description="the user said so")
    refused_retract = ""
    try:
        stated.retract()
    except TypeError as exc:
        refused_retract = str(exc)
    check("a stated link is not retractable — what was said stays",
          "what was said stays" in refused_retract, refused_retract or "(allowed)")

    # --- every word says how many hold at a moment, on both ends ---
    # A gate, because the fields are read with `.get()` and an absent one behaves exactly like
    # `false` — a word nobody thought about is indistinguishable, in code, from one thought about
    # and left open. "One ever" is withdrawn: a side is one at a time or it is not.
    for name, cls in sorted(world.classes.items()):
        rel = cls._spec.get("relation")
        if not rel or name == "Related":
            continue
        for side in ("functional", "inverse_functional"):
            check(f"{name}.{side} is one-at-a-time or open",
                  rel.get(side) in (False, ontology.AT_A_TIME), repr(rel.get(side)))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    # A word said from an end the type has not been seen between: news about the word, not an error
    # in the link. The refusal that used to stand here said so in its own last clause — "the ends a
    # type names are what it has seen, not a rule about what it may see" — and then raised. Measured
    # 2026-09-28: it killed 24 readings of 54, and the advice it gave, say it in the words it came
    # in, is a circle when the reading is what is being told.
    rt = base.world()
    rt.run('world.define_relation("plays_position", "a player and the position they play",'
           ' nature="related_to", cardinality="many-to-many", subject_is="the player",'
           ' object_is="the position", subject="Person", object="Thing")', "w")
    from_a_new_end = rt.run('x = Thing.new(name="quarterback")\ny = Thing.new(name="American '
                            'football")\nprint(type(x.set_plays_position(y)).__name__)', "w")
    check("a word said from an end it has not been seen between is taken",
          "PlaysPosition" in (from_a_new_end.get("output") or ""),
          str(from_a_new_end.get("error") or from_a_new_end.get("output"))[:120])

    # The two arguments either way round. Both a host and the reading's engineer write the word
    # first, and the world used to answer "no relation type Thing(id=…)" — the entity printed where
    # the word should be, on the first line of a block, three goes in a row.
    rt = base.world()
    rt.run('a = Person.new(full_name="Coco")\nb = Thing.new(name="Chanel")', "w")
    said = rt.run('one = a.relate(b, "founded the house of")\n'
                  'two = a.relate("founded the house of", b)\nprint(one.id == two.id)', "w")
    check("the words and the thing are taken in either order",
          "True" in (said.get("output") or ""),
          str(said.get("error") or said.get("output"))[:120])

    print("all relation tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
