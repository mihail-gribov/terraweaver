"""Tests for how the world keeps state — the failures here are the silent kind.

Nothing in this file needs a model. It covers the cases where the world can look fine and
be wrong: a change reverted by a stale copy, a half-linked relationship, a fact that never
reached storage.

Run: python3 tests/test_world_state.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.resolution import run_skill

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def fresh_world():
    """A base world with what these checks talk about, told the way a host tells it.

    An address and a city are attributes it grows; an employer is a word for a link, one at a
    time for the person and any number for the employer.
    """
    from datetime import datetime, timedelta

    rt = base.world(None)
    base.attribute(rt, "Person", "email", "The address this person reads their mail at.", type="email")
    base.attribute(rt, "Person", "city", "The city this person lives in.")
    base.attribute(rt, "Person", "phone", "The number this person answers.", type="phone")
    base.word(rt, "works_at", "a person working for an employer", "many-to-one",
              "a person who works", "their employer")
    classes = rt.world.classes
    Person, Thing, Event = classes["Person"], classes["Thing"], classes["Event"]
    techcorp, dataworks = Thing.new(name="TechCorp"), Thing.new(name="DataWorks")
    Thing.new(name="CloudNine")
    Person.new(name="Ada Lovelace", email="ada@example.com", city="London").set_works_at(techcorp)
    Person.new(name="Anna Sullivan", aliases=["Annie"], email="anna.sullivan@example.com", city="Leeds")
    Person.new(name="Anna Peterson", aliases=["Annie"], city="York")
    soon = datetime.now().replace(microsecond=0)
    Event.new(title="Interview at DataWorks", about=dataworks, start_time=soon + timedelta(days=3))
    Event.new(title="Call with TechCorp", about=techcorp, start_time=soon - timedelta(days=3))
    return classes, rt.world.store, rt.world


def main() -> int:
    classes, store, world = fresh_world()
    Person, Thing = classes["Person"], classes["Thing"]

    # --- one row is one object ---
    first = Person.find(email="ada@example.com").matches[0]
    second = Person.find(email="ada@example.com").matches[0]
    check("the same row loads as the same object", first is second)

    # A settled change must survive an older reference to the same entity being saved again.
    # This is how a resolved contradiction used to revert itself: whoever saved last won.
    needs = world.ensure(Person, email="ada@example.com", city="Berlin")
    run_skill(needs, lambda question, options: 0, world)
    store.save_graph(first)  # an earlier reference, saved after the change
    check("a settled change isn't overwritten by an older reference",
          Person.find(email="ada@example.com").matches[0].city == "Berlin")

    # --- a link holds on both sides ---
    classes, store, world = fresh_world()
    Person, Thing = classes["Person"], classes["Thing"]
    steve = Person.new(name="Steve", email="steve@acme.com")
    acme = Thing.new(name="Acme")
    steve.set_works_at(acme)
    check("linking one side links the other", [p.name for p in acme.works_at_of] == ["Steve"],
          str(acme.works_at_of))
    steve.set_works_at(acme)
    check("linking again doesn't list them twice", [p.name for p in acme.works_at_of] == ["Steve"],
          str(acme.works_at_of))
    check("and it survives storage", Person.get(email="steve@acme.com").works_at.name == "Acme")

    # --- an assignment is the host's statement: it goes through, and the old value is kept ---
    classes, store, world = fresh_world()
    Person, Thing = classes["Person"], classes["Thing"]
    ada = Person.find(email="ada@example.com").matches[0]
    ada.city = "Paris"
    check("an assignment goes through without a question", Person.get(email="ada@example.com").city == "Paris")
    past = ada.history("city")
    check("the old value stays in the history",
          [p.value for p in past] == ["London", "Paris"] and past[0].until is not None and past[1].until is None,
          str([(p.value, p.until) for p in past]))
    ada.city = "London"

    # --- a disagreement while identifying is a question, with "a different one" among the answers ---
    needs = world.ensure(Person, name="Ada Lovelace", email="ada@example.com", city="Paris")
    check("ensure with a conflicting value asks", getattr(needs, "skill", None) == "resolve_contradiction")
    check("and offers that it's a different person", len(getattr(needs, "options", [])) == 3)
    check("the world is untouched until the user decides",
          Person.find(email="ada@example.com").matches[0].city == "London")
    other = world.settle(needs, new=True)
    check("answering 'a different one' creates a second person and leaves the first alone",
          other is not ada and other.city == "Paris" and ada.city == "London")

    # --- printing an entity can't blow up ---
    # The world is a graph with cycles (event -> company -> the people linked to it -> ...).
    # Recursing through them in repr exhausted the stack the moment the model gained another
    # link, and it surfaced as "the agent is flaky" rather than as our bug.
    classes, store, world = fresh_world()
    Event, Person = classes["Event"], classes["Person"]
    try:
        text = repr(Event.all(limit=None))
        blew_up = False
    except RecursionError:
        text, blew_up = "", True
    check("printing a cyclic graph doesn't recurse", not blew_up)
    check("references appear as labels, not expansions", "<Thing " in text, text[:120])
    check("and the text stays readable", len(repr(Person.find(email="ada@example.com").matches[0])) < 400)

    classes, store, world = fresh_world()
    Person, Thing = classes["Person"], classes["Thing"]
    ada = Person.find(email="ada@example.com").matches[0]

    # --- a word the class doesn't have is taken, not lost ---
    # It used to be accepted and then dropped on save — a write that looked fine and never
    # happened. Refusing it stops the block instead; a world that grows takes the word, with its
    # type guessed from the value, and asks what it means at the close.
    ada.favourite_colour = "green"
    check("an attribute the class doesn't have is taken into the class",
          any(a["name"] == "favourite_colour" for a in type(ada)._spec["attributes"]))
    check("and what was written with it is kept",
          Person.get(email="ada@example.com").favourite_colour == "green")
    techcorp = Thing.get(name="TechCorp")
    try:
        techcorp.works_at_of = []
        derived_refused = False
    except TypeError:
        derived_refused = True
    check("the reading side of a link can't be assigned", derived_refused)
    dataworks = Thing.get(name="DataWorks")
    ada.set_works_at(dataworks)
    check("changing jobs moves a person between the employers' lists",
          ada not in techcorp.works_at_of and ada in dataworks.works_at_of,
          str([techcorp.works_at_of, dataworks.works_at_of]))

    # --- an unrelated write is left alone ---
    ada.phone = "+7 900 000-00-00"
    check("a non-conflicting write goes through", ada.phone == "+7 900 000-00-00")

    # --- a subgraph is stored whole or not at all ---
    # An event about a new company touches both; if the second one can't be written, the
    # first must not stay behind pointing at nothing.
    from datetime import datetime
    classes, store, world = fresh_world()
    Thing, Event = classes["Thing"], classes["Event"]
    events_before = len(store.load_all("Event", classes))
    things_before = len(store.load_all("Thing", classes))
    initech = Thing(name="Initech")
    meeting = Event(title="Meeting at Initech", about=initech, start_time=datetime(2026, 10, 2, 10, 0))
    # A set can't be encoded, so the graph fails midway. It goes in past the attribute door
    # on purpose: what is under test is the save, not the check that would have caught it.
    object.__setattr__(initech, "tags", {"unserializable"})
    failed = False
    try:
        store.save_graph(meeting)
    except TypeError:
        failed = True
    check("a failing graph save raises", failed)
    check("and leaves no part of the graph stored",
          len(store.load_all("Event", classes)) == events_before
          and len(store.load_all("Thing", classes)) == things_before)
    check("and gives back the ids it handed out", initech.id is None and meeting.id is None)
    object.__setattr__(initech, "tags", [])
    store.save_graph(meeting)
    check("the same graph saves once fixed",
          Event.find(title="Meeting at Initech").matches[0].about.name == "Initech")

    # A transaction spanning several graphs — one agent script's changes — is one unit too.
    classes, store, world = fresh_world()
    Person = classes["Person"]
    before = len(store.load_all("Person", classes))
    try:
        with store.transaction():
            store.save_graph(Person(name="Dave", email="dave@example.com"))
            raise RuntimeError("the script failed after its first write")
    except RuntimeError:
        pass
    check("an aborted transaction undoes writes that already happened inside it",
          len(store.load_all("Person", classes)) == before)

    # --- dated remarks hold what the attributes have no place for ---
    from datetime import date, timedelta
    classes, store, world = fresh_world()
    Person = classes["Person"]
    ada = Person.find(email="ada@example.com").matches[0]
    ada.describe("allergic to nuts")
    # A day in the future of whenever this runs, not a date somebody wrote down once. These come
    # back newest first by the day the thing happened, falling back to the day it was recorded —
    # so a `when` that has since *become* today sorts behind a remark recorded at 02:21 today, and
    # the order flips. Written as 2026-10-01, this test passed for months and began failing on
    # 2026-10-01 (docs/now.md, flickers).
    ada.describe("might move to Berlin", when=date.today() + timedelta(days=30), tentative=True)
    texts = [c.text for c in ada.described()]
    check("remarks come back newest first", texts == ["might move to Berlin", "allergic to nuts"], str(texts))
    check("a tentative remark says so", ada.described(contains="Berlin")[0].tentative)
    ada.described(contains="nuts")[0].forget()
    check("a forgotten remark is gone", [c.text for c in ada.described()] == ["might move to Berlin"])
    try:
        with store.transaction():
            ada.describe("never kept")
            raise RuntimeError("the run failed after commenting")
    except RuntimeError:
        pass
    check("a remark from a failed run isn't kept", not ada.described(contains="never kept"))
    # --- remarks go stale, into history rather than away ---
    from datetime import timedelta
    ada.describe("lived in Moscow", when=date(2020, 1, 1), until=date(2025, 6, 1))
    ada.describe("allergic to nuts", permanent=True)
    ada.describe("likes coffee")
    current = {c.text for c in ada.described()}
    check("an expired remark drops out of ordinary reads", "lived in Moscow" not in current, str(current))
    check("and stays in the history",
          any(c.text == "lived in Moscow" and c.expired for c in ada.described(include_expired=True)))
    check("a permanent remark has no end", ada.described(contains="nuts")[0].until is None)
    check("an unsaid end gets the default", ada.described(contains="coffee")[0].until is not None)
    coffee = ada.described(contains="coffee")[0]
    coffee.keep(ttl=timedelta(days=-1))
    check("the host can change how long a remark holds", not ada.described(contains="coffee"))

    # --- a record's period: ended things become history, never disappear ---
    from terraweaver.conditions import after, before, between, now
    Thing, Event = classes["Thing"], classes["Event"]
    closed = Thing.ensure(name="Staff SRE opening", ttl=timedelta(days=-1))
    check("an ended record drops out of ordinary reads",
          "Staff SRE opening" not in [t.display_name() for t in Thing.all(limit=None)])
    check("and stays reachable as history",
          "Staff SRE opening" in [t.name for t in Thing.find(name="Staff SRE opening", history=True)])
    check("identity is timeless: ensure finds the ended one instead of duplicating it",
          Thing.ensure(name="Staff SRE opening") is closed)

    # --- time ranges in find compare safely whatever the time zone ---
    upcoming, past = Event.find(start_time=after(now())), Event.find(start_time=before(now()))
    check("upcoming and past events split the calendar",
          len(upcoming) + len(past) == len(Event.all(limit=None)) and upcoming and past)
    week = Event.find(start_time=between(date.today(), date.today() + timedelta(days=7)))
    check("a date as the end of a range includes that day", all(e in upcoming for e in week))

    # --- the host says whether it means an existing entity or a new one ---
    from terraweaver.world import NotInWorld
    check("get picks out the one meant, using context",
          Person.get(name="Annie", city="Leeds").name == "Anna Sullivan")
    try:
        Person.get(name="Pete Ivanson")
        missing_raises = False
    except NotInWorld:
        missing_raises = True
    check("get never creates: someone absent is a loud error", missing_raises)
    check("and a name only sharing a part with someone doesn't resemble them",
          missing_raises and not Person.find(name="Pete Ivanson", history=True))
    petr = Person.new(name="Pete Ivanson", email="pete@x.org")
    check("new creates", isinstance(petr, Person) and petr.id is not None)
    twin = Person.new(name="Pete Ivanson", email="pete@x.org")
    check("the same address is the same person, without asking", twin is petr)
    second = Person.new(name="Pete Ivanson")
    check("but a write with nothing to go on records rather than asking, and is merged later",
          isinstance(second, Person) and second is not petr)

    # --- a question in the middle of a batch holds its link instead of killing the run ---
    held = Person.get(name="Pete Ivanson")           # two of them now, nothing to tell them apart
    acme = Thing.ensure(name="Held Links Ltd")
    held.set_works_at(acme)                               # would have raised and discarded it all
    held.tag("conference")
    held.describe("met at the conference")
    alongside = Person.new(name="Quinn Ivers", email="quinn@x.org")
    check("the rest of the batch survives a question", isinstance(alongside, Person))
    settled = world.settle(held, petr)
    check("and everything held is done once the question is answered",
          any(r.other(settled) is acme for r in settled.relations("works_at"))
          and "conference" in (settled.tags or [])
          and any("conference" in c.text for c in settled.described()),
          str([settled.tags, [r.display_name() for r in settled.relations("works_at")]]))
    reading = None
    try:
        held.email
    except AttributeError as exc:
        reading = str(exc)
    check("reading a question is still refused — there is no honest value to give",
          reading is not None and "a question has no" in reading, str(reading))

    # --- a name already taken under another class is said, not decided ---
    from terraweaver import ontology as _o

    Event.new(title="Rugby", start_time=datetime(2026, 10, 3, 15, 0))
    with _o.record_changes() as across:
        Thing.new(name="Rugby")
    # A question now, not a hint. The hint was right and nobody read it: in a 455-fact run the
    # world noticed all twenty-three duplicate names this way and every one still went in, so
    # a later telling superseded nothing because it landed on a different entity.
    check("a name already used under another class is asked about",
          any("has the name of something already here" in line for line in across.questions),
          str(across.questions))
    with _o.record_changes() as apart:
        Thing.new(name="Quietwood Ltd")
    check("and an unused name is left alone",
          not any("already here" in line for line in apart.questions), str(apart.questions))

    # --- who the user meant by a name is remembered ---
    annie = Person.find(name="Annie")
    sullivan = Person.get(email="anna.sullivan@example.com")
    world.settle(annie, sullivan)
    check("once settled, the name picks that person", Person.get(name="Annie") is sullivan)
    check("and ensure by that name doesn't call the nickname a contradiction",
          Person.ensure(name="Annie", phone="555") is sullivan)
    world.remember_choice(annie, None)  # what answering "someone new" to that question records
    check("someone new under the name makes it a question again",
          getattr(Person.find(name="Annie"), "skill", None) == "resolve_ambiguity")

    # --- a list attribute that only grows is not a contradiction ---
    tv = Thing.new(name="Living room TV")
    tv.aliases = ["the TV"]
    tv.aliases = tv.aliases + ["the telly"]
    check("appending to a list goes through", len(tv.aliases) == 2, str(tv.aliases))
    tv.aliases = [tv.aliases[1]]
    check("dropping an item goes through, and the fuller list is in the history",
          len(tv.history("aliases")[-2].value) == 2 and len(tv.aliases) == 1,
          str([h.value for h in tv.history("aliases")]))

    store.clear_all()
    check("a rebuilt world starts without old remarks",
          not store.conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0])

    # --- what was written comes back whole, in a process that did not write it ---
    import tempfile
    from terraweaver import open_world

    path = Path(tempfile.mkdtemp()) / "reopened.db"
    first = open_world(str(path))
    wrote = first.run(
        'e = Event.new(title="Rent", start_time=datetime(2026, 10, 1), until=date(2027, 1, 1))\n'
        'e.tag("bills")', "host")
    assert not wrote["error"], wrote["error"]
    del first
    again = open_world(str(path))
    back = again.run('print([(e.title, e.valid_until) for e in Event.all(limit=None, any_time=True)])',
                     "host")
    # Filling an attribute can load a reference, whose queries used to cut the load short — and
    # what a class keeps last in its table went missing: the title, and the period with it.
    check("a title survives being read back by another process",
          "Rent" in (back["output"] or ""), str(back["output"] or back["error"]))
    check("and so does the period, which is what made this dangerous",
          "2027" in (back["output"] or ""), str(back["output"] or back["error"]))
    # And the reading must not have changed what is stored. Checking only what came back hid
    # this for hours: a read that saved a half-filled entity returned the right answer from
    # memory while writing nulls over the row behind it. So read it once more, from scratch.
    del again
    third = open_world(str(path))
    once_more = third.run(
        'print([(e.title, e.valid_until) for e in Event.all(limit=None, any_time=True)])', "host")
    check("and reading a world leaves it exactly as it was",
          "Rent" in (once_more["output"] or "") and "2027" in (once_more["output"] or ""),
          str(once_more["output"] or once_more["error"]))

    # A link that lost an end joins nobody, and it is kept out of every read in one place rather
    # than at each reader. Measured 2026-09-30: 20 of 898 links in one world had lost an end, and
    # each could end a whole pass — two readers were mended one at a time before it was clear that
    # mending readers is endless.
    classes, store, world = fresh_world()
    Thing = classes["Thing"]
    a, b = Thing(name="Harare"), Thing(name="France")
    store.save_graph(a)
    store.save_graph(b)
    link = world.relate(a, b, "related", description="Harare is the capital of France")
    whole = len(world.all("Related", limit=None, history=True))
    from terraweaver import ontology as _ont

    with _ont.trusted_writes():
        link.object = None
    store.save_graph(link)
    left = world.all("Related", limit=None, history=True)
    check("a link that lost an end is not in the answer",
          len(left) == whole - 1, f"{len(left)} of {whole}")
    check("and reading the class still works at all", isinstance(left, list))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all world-state tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
