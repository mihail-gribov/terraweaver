"""Tests for the findings of docs/code-review-2026-09-30.md, one test per finding.

Every high finding in that review sat on a path no test touched, which is why each of them
survived a hundred runs. The fixes go in with a test here, named by the finding, so the next
sweep over these seams has something that fails when it is undone.

Run: .venv/bin/python tests/test_review_fixes.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class StubEngineer:
    """An engineer shaped like `outside.Open`: it answers `.json` and `.say`, it is not callable."""

    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def json(self, system: str, asked: str):
        self.asked.append(asked)
        return self.answer

    def say(self, system: str, asked: str) -> str:
        self.asked.append(asked)
        return str(self.answer)


def finding_3_4_1_the_engineer_is_not_a_function() -> None:
    """`look_at_types` must reach an engineer that answers `.json`, not call it as a function."""
    from terraweaver import inspector

    rt = base.world()
    base.word(rt, "wrote", "who wrote what", cardinality="many-to-many",
              subject_is="", object_is="")
    person = rt.world.new("Person", name="Ann")
    book = rt.world.new("Thing", name="a book")
    rt.world.relate(person, book, "wrote")

    engineer = StubEngineer({"subject_is": "writer", "object_is": "written",
                             "clear": True, "clear_name": "wrote"})
    rt.world.engineer = engineer
    out = inspector.look_at_types(rt.world)

    read = rt.world.store.conn.execute(
        "SELECT count(*) FROM type_checks WHERE looked_at IS NOT NULL").fetchone()[0]
    check("3.4.1 the engineer is asked at all", bool(engineer.asked),
          f"nothing was asked of it; look_at_types said {out}")
    check("3.4.1 what it said is written down", read > 0, f"{read} types marked read")
    check("3.4.1 the ends it named are on the type",
          (rt.world.classes["Wrote"]._spec.get("relation") or {}).get("roles") is not None,
          "the roles were not filled in")


class StubPicker:
    """A picker that answers nothing: the look finds no word, the check has nothing to judge."""

    def choose(self, state, question, options):
        raise RuntimeError("this picker does not answer")

    def ask(self, state, questions):
        return {}


class SilentEngineer:
    """It writes a line that runs and joins nothing — the case the trace calls "gave up"."""

    def __init__(self):
        self.goes = 0

    def say(self, system: str, asked: str) -> str:
        self.goes += 1
        return "x = 1"


def finding_3_4_2_a_link_that_was_already_there_is_not_this_readings_work() -> None:
    """A typed link standing before the reading must not be counted as what the reading wrote."""
    from terraweaver import formalise
    from terraweaver.formalise import write

    rt = base.world()
    base.word(rt, "mayor_of", "who is the mayor of what", cardinality="one-to-one",
              subject_is="mayor", object_is="city")
    person = rt.world.new("Person", name="Anne Hidalgo")
    city = rt.world.new("Thing", name="Paris")
    standing = rt.world.relate(person, city, "mayor_of")

    bare = rt.world.relate(person, city, "related",
                           description="Anne Hidalgo was born in Paris")
    check("3.4.2 typed_between sees it without the exclusion",
          len(write.typed_between(rt.world, person, city)) == 1)
    check("3.4.2 and not with it",
          write.typed_between(rt.world, person, city, apart_from={standing.id}) == [])

    engineer, picker = SilentEngineer(), StubPicker()
    trace = formalise.formalise_one(rt, bare, engineer, picker)
    again = rt.world.store.load(bare.id, rt.world.classes) or bare
    check("3.4.2 the reading does not claim the standing link", trace.get("went") == "gave up",
          f"it said {trace.get('went')!r}, typed {trace.get('typed')}")
    check("3.4.2 the bare link holding the real words is still standing",
          getattr(again, "valid_until", None) is None,
          "it was ended, and the words went with it")
    check("3.4.2 what was already there is in the trace", trace.get("was_typed") == 1,
          f"was_typed={trace.get('was_typed')}")


def finding_2_3_only_the_transaction_commits() -> None:
    """A statement that wrote tags and then raised must leave nothing — the host's own promise."""
    rt = base.world()

    def people() -> int:
        return rt.world.store.conn.execute(
            "SELECT count(*) FROM instances WHERE class_name = 'Person'").fetchone()[0]

    was = people()
    got = rt.run('x = [Person.new(name="Ann", tags=["friend"]), 1/0]', "host")
    check("2.3 the run says it failed", not got.get("ok"), str(got)[:160])
    check("2.3 and nothing it wrote is there", people() == was,
          "Ann survived a statement that raised, because a tags write committed under her")

    plain = rt.run('y = [Person.new(name="Bob"), 1/0]', "host")
    check("2.3 the case that always worked still works", not plain.get("ok") and people() == was)

    # And outside a transaction a commit is still a commit, or nothing would ever be durable.
    kept = rt.run('z = Person.new(name="Cleo")', "host")
    check("2.3 an ordinary write is still committed", kept.get("ok") and people() == was + 1,
          f"{people()} people, was {was}")


def finding_3_1_3_the_later_statement_wins_under_a_moved_clock() -> None:
    """Twelve corrections in one moment: the image must show the last, not the seventh.

    Under `set_now` — the replay mode the record was built for — every statement in a run carries
    the same `last_said`, and the tie was broken by the *string* id, where `facts_p:10` sorts
    before `facts_p:9`. Measured before the fix: the twelfth correction showed as the eighth.
    """
    import sqlite3

    from terraweaver import assembly, timeutil
    from terraweaver.facts import Facts

    timeutil.set_now(datetime(2020, 1, 1, 12, 0, 0))
    try:
        facts = Facts(sqlite3.connect(":memory:"))
        facts.state("p1", "name", "Ada", source="agent")
        for n in range(12):
            facts.state("p1", "city", f"city {n}", source="agent")
        shown = [image.values.get("city") for image in assembly.assemble(facts).values()]
        check("3.1.3 the last correction of the moment is the one that stands",
              shown == ["city 11"], f"the image shows {shown}")
    finally:
        timeutil.set_now(None)


def finding_3_1_2_one_subject_rebuilt_keeps_its_repeats() -> None:
    """A tags write must not wipe that entity's repeat rules — `rebuild_for` deleted them."""
    from terraweaver import periods

    rt = base.world()
    ada = rt.world.new("Person", name="Ada")
    ada.repeat(every="week", tag="on-call")
    before = len(periods.cycles(rt.world, ada.id))
    periods.rebuild_for(rt.world, ada.id)
    after = periods.cycles(rt.world, ada.id)
    check("3.1.2 the repeat rule was there", before == 1, f"{before} cycles before")
    check("3.1.2 and it survives a one-subject rebuild", len(after) == 1,
          f"{len(after)} cycles after rebuild_for")


def finding_3_2_2_one_question_per_thing_not_per_pair() -> None:
    """Ten employees of one organisation must open one question about it, not nine."""
    rt = base.world()
    base.word(rt, "works_at", "who works where", cardinality="many-to-one",
              subject_is="employee", object_is="employer")
    firm = rt.world.new("Thing", name="DataWorks")
    for n in range(10):
        rt.world.relate(rt.world.new("Person", name=f"P{n}"), firm, "works_at")
    asked = [q for q in rt.world.questions.open_() if q.kind == "one_works_at_per_object"]
    check("3.2.2 one question about the organisation", len(asked) == 1,
          f"{len(asked)} questions: {[q.text[:40] for q in asked]}")


def finding_3_2_1_a_clean_handover_is_not_two_at_once() -> None:
    """One link ending the moment the next begins is a handover, not a broken rule."""
    from terraweaver import properties

    rt = base.world()
    base.word(rt, "mayor_of", "who is the mayor of what", cardinality="many-to-many",
              subject_is="mayor", object_is="city")
    city = rt.world.new("Thing", name="Paris")
    first = rt.world.relate(rt.world.new("Person", name="A"), city, "mayor_of",
                            starts=datetime(2010, 1, 1), until=datetime(2020, 1, 1))
    second = rt.world.relate(rt.world.new("Person", name="B"), city, "mayor_of",
                             starts=datetime(2020, 1, 1))
    check("3.2.1 a handover is one at a time", properties._at_once([first, second]) == 1,
          f"_at_once said {properties._at_once([first, second])}")


def finding_3_3_1_and_3_3_2_the_variable_tools() -> None:
    """`set_variable` must work at all, and no variable may take a name the world binds."""
    from terraweaver.variables import VariableError

    rt = base.world()
    rt.run('ada = Person.new(name="Ada")', "host")
    got = rt.set_variable("host", "ada", 'Person.find(name="Ada").matches[0]',
                          "the person this task is about")
    check("3.3.1 set_variable works", got.get("ok"), f"{got.get('error')}")
    check("3.3.1 and the name is there", "ada" in rt.variables.names(),
          f"names: {sorted(rt.variables.names())}")

    for taken in ("agent", "user", "world", "Person"):
        try:
            rt.variables.pin(taken, 5, "shadowing something the world binds", keep=True)
            check(f"3.3.2 {taken!r} cannot be pinned", False, "it was allowed")
        except VariableError:
            check(f"3.3.2 {taken!r} cannot be pinned", True)


def finding_3_3_3_a_task_that_cannot_close_is_still_dropped() -> None:
    """Opening a task over one that cannot close must drop the old one, not keep it open."""
    rt = base.world()
    rt.run('ada = Person.new(name="Ada")', "host")     # a recording task with a bare name
    first = rt.sessions["host"].task_id
    rt.start_task("host", "record what the user said about somebody else entirely", "recording")
    was = rt.store.load(first, rt.classes)
    check("3.3.3 the old task is closed", getattr(was, "closed_as", None) == "abandoned",
          f"closed_as={getattr(was, 'closed_as', None)!r}")
    check("3.3.3 and the new task is not the old one",
          rt.sessions["host"].task_id not in (None, first))
    check("3.3.3 nothing the old task touched came with it",
          not rt.sessions["host"].touched, f"touched: {rt.sessions['host'].touched}")


def finding_3_3_4_one_sessions_modules_are_its_own() -> None:
    """`math.sqrt = 7` in one session must not be `7` in the next."""
    rt = base.world()
    rt.run("math.sqrt = 7", "one")
    got = rt.run("out = math.sqrt(9)\nprint(out)", "two")
    check("3.3.4 the other session's math is untouched",
          got.get("ok") and "3.0" in (got.get("output") or ""),
          f"ok={got.get('ok')} output={got.get('output')!r} error={got.get('error')!r}")


def finding_3_3_7_the_echo_says_what_actually_ran() -> None:
    """A statement that raises does not end the block, so the echo must not say it did."""
    from terraweaver.runtime import format_result

    rt = base.world()
    got = rt.run('a = Person.new(name="One")\nb = 1/0\nc = Person.new(name="Two")',
                 "host")
    shown = format_result(got)
    made = rt.world.store.conn.execute(
        "SELECT count(*) FROM instances WHERE class_name = 'Person'").fetchone()[0]
    check("3.3.7 both people the block made are in the world", made == 3, f"{made} people")
    check("3.3.7 the error does not claim the rest never ran",
          "never ran" not in (got.get("error") or ""), got.get("error"))
    check("3.3.7 and the echo gives the lines that ran back as code",
          'c = Person.new(name="Two")' in shown
          and '# c = Person.new(name="Two")' not in shown, shown[:400])

    # A line that is not code at all is not a line anything reached or failed on. Marked as
    # "never reached" it said so of a comment above a line that had just run.
    commented = format_result(rt.run(
        '# record the people\na = Person.new(name="Three")\n\n# and one that fails\n'
        'b = 1/0\nc = Person.new(name="Four")\nd = 1/0\ne = 1/0\n'
        'f = Person.new(name="Five")', "host"))
    check("3.3.7 a comment is handed back as written",
          "# record the people" in commented
          and "(never reached) # record the people" not in commented, commented[:500])
    check("3.3.7 and a statement nothing reached says so",
          '# (never reached) f = Person.new(name="Five")' in commented, commented[:600])


def finding_3_1_6_a_separation_holds_through_a_third_party() -> None:
    """Told a and c are different: a rule match between b and c may not join them anyway."""
    import sqlite3

    from terraweaver import assembly
    from terraweaver.facts import Facts, reference

    def groups(separated: bool):
        facts = Facts(sqlite3.connect(":memory:"))
        facts.state("a", "name", "Ann Lee", source="user")
        facts.state("b", "name", "Anna Sullivan", source="user")
        facts.state("c", "name", "Anna Sullivan", source="user")
        facts.state("a", assembly.SAME_AS, reference("b"), source="user")
        if separated:
            facts.state("a", assembly.NOT_SAME_AS, reference("c"), source="user")
        return sorted(sorted(image.subjects) for image in assembly.assemble(facts).values())

    check("3.1.6 without a separation the rule joins all three",
          groups(False) == [["a", "b", "c"]], str(groups(False)))
    check("3.1.6 and the separation keeps them apart",
          groups(True) == [["a", "b"], ["c"]], str(groups(True)))


def a_placing_is_stated_so_it_survives_a_rebuild() -> None:
    """The names pass places a thing under a class; the record has to say so, or a rebuild undoes it.

    Not from the review — found on 2026-09-30 while checking the review's fixes on a real run.
    `Chang'an` had been placed under `City`, the record held no `is_a`, and `world.rebuild()` read
    it back as the `Thing` it came in as. And whose placing it is is kept with it: the world's own
    goes in under `world`, so it ranks below what the world was told and comes off in one move.
    """
    from terraweaver import ontology

    rt = base.world()
    rt.world.extras["define"](
        "City", "a place where many people live together, with its own government", "name",
        [{"name": "population", "description": "how many people live there now", "type": "int"}],
        parent="Thing", source="world")
    thing = rt.world.new("Thing", name="Chang'an")
    with ontology.stating("world"):
        placed = thing.become("City")
    said = [one for one in rt.world.facts.about(placed.subject_id) if one.slot == "is_a"]
    check("a placing is in the record", [one.value for one in said] == ["City"], str(said))
    check("and it is the world's own", [one.source for one in said] == ["world"], str(said))

    rt.world.rebuild()
    again = rt.world.store.load(placed.id, rt.world.classes)
    check("and it survives a rebuild", type(again).__name__ == "City",
          f"it came back a {type(again).__name__}")
    check("with its name", again.display_name() == "Chang'an", repr(again.display_name()))


def the_names_pass_changes_the_class_and_nothing_else() -> None:
    """Placing a bare name moves it under a class; its name, values and links are not the pass's.

    Measured 2026-10-02 on a 455-fact world (var/run10): before the names pass 1 fact was lost to
    a name missing from its image, after it 31. The pass asked the engineer for code that filled
    the thing in and ran it, and what that code wrote came back as `Person` rows null in every
    column but a backwards `authored_by`. Earlier, on a gate, the same code renamed the position
    "center" to "Lisa Leslie". What the pass alone can say is what kind of thing this is — so
    that is all it says, over everything known about the thing.
    """
    from terraweaver import portraits

    class Jev:
        def __init__(self):
            self.states = []

        def choose(self, state, question, options):
            self.states.append(state)
            return {portraits.NEW_ONE: 1.0}

    class Engineer:
        def __init__(self):
            self.asked = []

        def json(self, system, asked):
            self.asked.append(asked)
            # What the old pass would have run, and the new one must not.
            return {"class": {"name": "City", "brief": "a city or town",
                              "description": "A place where many people live together.",
                              "attributes": []},
                    "code": 'it.name = "Amy Winehouse"\nit.describe("written by the reading")'}

    rt = base.world()
    camden = rt.world.new("Thing", name="Camden Town")
    camden.describe("A district of north London")
    portraits.comes_in(rt.world, camden)
    amy = rt.world.new("Person", name="Amy Winehouse")
    rt.world.relate(amy, camden, "related", label="died in", description="Amy Winehouse died in Camden Town")
    jev, engineer = Jev(), Engineer()
    tally = portraits.formalise(rt.world, engineer, jev=jev)
    rt._hand_back_what_moved(tally.pop("moved", []))

    check("the walk was shown the links, not only the account",
          any("died in" in state for state in jev.states), jev.states[-1][-300:] if jev.states else "")
    check("and so was the engineer describing the class",
          bool(engineer.asked) and "died in" in engineer.asked[0])
    again = rt.world.store.load(camden.id, rt.world.classes)
    check("the thing is placed", type(again).__name__ == "City", type(again).__name__)
    check("with its name", again.display_name() == "Camden Town", repr(again.display_name()))
    check("and nothing the engineer wrote as code was run",
          not any("written by the reading" in str(d) for d in (again.descriptions or [])),
          str(again.descriptions))
    check("its link is the one the host wrote, and only that",
          [link.display_name() for link in again.relations()]
          == [link.display_name() for link in amy.relations()]
          and len(amy.relations()) == 1,
          str([link.display_name() for link in again.relations()]))


def a_row_that_will_not_load_costs_only_that_row() -> None:
    """A refusal on one stored value must not cost the image, and must not leave a shell behind.

    Not from the review — found 2026-10-01 by `experiments/why_it_failed.py` on a 455-fact world:
    21 entities held a name in the record and nothing in the image, and it was 29 of the 105 facts
    that world did not hold. The identity map registers an object before its values are filled,
    because a cyclic reference has to find it there; a fill that raised left the half-built object
    in the map, and from then on `Person.get(name=…)` answered `NotInWorld` about something
    the record plainly held, while the next `save` wrote null over every value it had.
    """
    from terraweaver import store as store_module

    rt = base.world()
    kyd = rt.world.new("Person", name="Thomas Kyd")
    kyd.describe("English dramatist")
    held = kyd.id
    rt.world.store._identity.clear()

    real = store_module.Store._fill

    def one_bad_row(self, obj, attr_name, decoded, classes, memo):
        if attr_name == "descriptions":
            raise ValueError("this row will not read")
        return real(self, obj, attr_name, decoded, classes, memo)

    store_module.Store._fill = one_bad_row
    try:
        loaded = rt.world.store.load(held, rt.world.classes)
    finally:
        store_module.Store._fill = real

    check("the load keeps everything else", getattr(loaded, "name", None) == "Thomas Kyd",
          repr(getattr(loaded, "name", None)))
    check("and the one row that would not read is the one thing missing",
          getattr(loaded, "descriptions", None) in (None, []),
          repr(getattr(loaded, "descriptions", None)))

    found = rt.world.get("Person", name="Thomas Kyd")
    check("the world still knows it is there", getattr(found, "name", None) == "Thomas Kyd",
          repr(found))
    rt.world.save(found)
    row = dict(rt.world.store.conn.execute(
        "SELECT attr, value FROM Person WHERE instance_id = ? AND attr = 'name'", (held,)))
    check("and saving it does not write null over the name", row.get("name") == '"Thomas Kyd"',
          str(row))


def a_lookup_sees_the_classes_beneath_it() -> None:
    """A kind of a thing is a thing — when something is looked *for*. A listing stays exact.

    Found 2026-10-01 by `experiments/why_it_failed.py`: six of ten duplicate-end facts in a
    455-fact world were a bare `Thing` the world had made beside the right one under a class it
    had grown. The names pass places things under grown classes, and from that moment
    `Thing.get(name="Canada")` answered `NotInWorld` — so the honest move left to a host or an
    engineer was to make a second Canada.

    Listings stay exact on purpose: `[i.name for i in Thing.all()]` is a line a host writes all
    the time and a Person is a kind of Thing with no `name`, so an inclusive listing turns it into
    an AttributeError that costs the rest of the block.
    """
    from terraweaver import ontology

    rt = base.world()
    rt.world.extras["define"](
        "Country", "a sovereign state with its own government and borders", "name",
        [{"name": "population", "description": "how many people live there now", "type": "int"}],
        parent="Thing", source="world")
    thing = rt.world.new("Thing", name="Canada")
    with ontology.stating("world"):
        thing.become("Country")

    found = rt.world.get("Thing", name="Canada")
    check("a lookup on the parent finds the kind", type(found).__name__ == "Country", repr(found))
    check("and so does find", bool(rt.world.find("Thing", name="Canada").matched),
          repr(rt.world.find("Thing", name="Canada")))
    check("the class and what is under it", "Country" in rt.world.kinds_of("Thing")
          and rt.world.kinds_of("Country") == ["Country"], str(rt.world.kinds_of("Thing")))
    check("a Task is not listed under Event, being the world's own",
          "Task" not in rt.world.kinds_of("Event"), str(rt.world.kinds_of("Event")))

    # Everything is called by its `name`, so a listing can be inclusive too and the host's own
    # idiom runs over a Person as over a Country.
    listed = rt.run('print([i.name for i in Thing.all(limit=None)])', "host")
    check("a listing reads the kinds, and the host's own idiom still runs",
          listed.get("ok") and "Canada" in (listed.get("output") or ""),
          str(listed.get("output") or listed.get("error"))[:160])
    exact = rt.run('print(Thing.all(limit=None, kinds=False))', "host")
    check("and an exact one says what is a kind of it rather than answering nothing",
          any("kind of it" in one for one in (exact.get("hints") or [])),
          str(exact.get("hints"))[:160])


def an_image_never_goes_to_storage_without_the_name_its_record_holds() -> None:
    """Whatever path hands storage a nameless object, the name in the record is put back.

    Two worlds on 2026-10-01 held images with `null` for the name while the record held it. One
    cause was found and closed; the other survived five faithful reproductions. So the door they
    all come through is guarded, and both shapes seen are checked here: a full row that lost only
    its name on being placed under a class, and a shell saved with nothing in it.
    """
    from terraweaver import ontology

    rt = base.world()
    rt.world.extras["define"]("City", "a place where many people live together, with its own government",
                              "name", [], parent="Thing", source="world")
    berkeley = rt.world.new("Thing", name="Berkeley", nature="place")
    with ontology.trusted_writes(), ontology.not_recording():
        object.__setattr__(berkeley, "name", None)
    with ontology.stating("world"):
        berkeley.become("City")
    row = dict(rt.world.store.conn.execute(
        "SELECT attr, value FROM City WHERE instance_id = ? AND attr = 'name'", (berkeley.id,)))
    check("a placing does not write a nameless image", row.get("name") == '"Berkeley"', str(row))

    kyd = rt.world.new("Person", name="Thomas Kyd")
    with ontology.trusted_writes(), ontology.not_recording():
        object.__setattr__(kyd, "name", None)
    rt.world.save(kyd)
    row = dict(rt.world.store.conn.execute(
        "SELECT attr, value FROM Person WHERE instance_id = ? AND attr = 'name'", (kyd.id,)))
    check("nor does a save", row.get("name") == '"Thomas Kyd"', str(row))

    rt.world.new("Person", name="Ada")
    rt.run('Person.get(name="Ada").name = "Ada Lovelace"', "host")
    check("and a host's own rename still goes through",
          rt.world.get("Person", name="Ada Lovelace").name == "Ada Lovelace")


def the_later_telling_stands_whichever_order_it_is_read_in() -> None:
    """Two one-at-a-time facts, said a day apart, typed in either order: the later one stands.

    Found 2026-10-01: 27 of 105 missing facts in a 455-fact world. The reading is resumable, so
    "wide receiver" (said first) was typed after "cornerback" (said second) and ended it — the
    world held the fact the user had corrected. It took three changes and one revert to settle:
    the reading types each fact as of when it was said, `created_at` is on the world's clock (it
    was on the wall's, so "when did this begin" was 2026 against a boundary in 2020), a link is
    not ended before it began, and the older telling arriving second is closed where the newer
    one began instead of being left open beside it.
    """
    from terraweaver import formalise, timeutil

    class Picker:
        def choose(self, state, question, options):
            raise RuntimeError("this picker does not answer")

        def ask(self, state, questions):
            return {}

    class Engineer:
        def say(self, system, asked):
            return "a.set_plays_position(b)"

    for order in ("as told", "reversed"):
        rt = base.world()
        base.word(rt, "plays_position", "which position somebody plays", cardinality="many-to-one",
                  subject_is="player", object_is="position")
        ward = rt.world.new("Person", name="Hines Ward")
        for name in ("wide receiver", "cornerback"):
            rt.world.new("Thing", name=name)
        with timeutil.as_of(datetime(2020, 1, 1)):
            first = rt.world.relate(ward, rt.world.get("Thing", name="wide receiver"), "related",
                                    description="Hines Ward plays the position of wide receiver")
        with timeutil.as_of(datetime(2020, 1, 2)):
            second = rt.world.relate(ward, rt.world.get("Thing", name="cornerback"), "related",
                                     description="Hines Ward plays the position of cornerback")
        for link in ((first, second) if order == "as told" else (second, first)):
            with timeutil.as_of(formalise.when_said(rt.world, link)):
                formalise.formalise_one(rt, link, Engineer(), Picker())
        links = [one for name, cls in rt.world.classes.items()
                 if (cls._spec.get("relation") or {}).get("kind") == "plays_position"
                 for one in rt.world.all(name, limit=None, history=True)]
        standing = [one.object.display_name() for one in links if one.valid_until is None]
        before = [one for one in links if one.object.display_name() == "wide receiver"]
        check(f"read {order}, the later telling stands", standing == ["cornerback"], str(standing))
        check(f"read {order}, the earlier one held until the later began",
              bool(before) and timeutil.as_datetime(before[0].valid_until) == datetime(2020, 1, 2),
              str([(one.valid_from, one.valid_until) for one in before]))


def a_hand_over_compares_like_with_like() -> None:
    """Which of two tellings is the later one, decided on one axis at a time.

    Found 2026-10-02 in a 455-fact world: "Gennady Rozhdestvensky died in Moscow" told first with
    no date, "…died in United States of America" told second with `starts=` the day — and the
    second, the gold, was closed as the *older* one, because the hand-over set a date the fact held
    from (2020) against the moment the other was told (2026). Two axes, one comparison.
    """
    from terraweaver import timeutil

    def world_with_died_in():
        rt = base.world()
        base.word(rt, "died_in", "where somebody died", cardinality="many-to-one",
                  subject_is="person", object_is="place")
        who = rt.world.new("Person", name="Gennady Rozhdestvensky")
        for place in ("Moscow", "United States of America"):
            rt.world.new("Thing", name=place)
        return rt, who

    def standing(rt):
        return [one.object.display_name() for name, cls in rt.world.classes.items()
                if (cls._spec.get("relation") or {}).get("kind") == "died_in"
                for one in rt.world.all(name, limit=None) if one.valid_until is None]

    # undated first, dated second — told in that order: the second stands
    rt, who = world_with_died_in()
    with timeutil.as_of(datetime(2026, 10, 2, 2, 21)):
        rt.world.relate(who, rt.world.get("Thing", name="Moscow"), "died_in")
    with timeutil.as_of(datetime(2026, 10, 2, 2, 40)):
        rt.world.relate(who, rt.world.get("Thing", name="United States of America"), "died_in",
                        starts=datetime(2020, 1, 19))
    check("undated then dated: the later telling stands",
          standing(rt) == ["United States of America"], str(standing(rt)))

    # dated first, undated second — told in that order: the second stands
    rt, who = world_with_died_in()
    with timeutil.as_of(datetime(2026, 10, 2, 2, 21)):
        rt.world.relate(who, rt.world.get("Thing", name="Moscow"), "died_in",
                        starts=datetime(2020, 1, 19))
    with timeutil.as_of(datetime(2026, 10, 2, 2, 40)):
        rt.world.relate(who, rt.world.get("Thing", name="United States of America"), "died_in")
    check("dated then undated: the later telling stands",
          standing(rt) == ["United States of America"], str(standing(rt)))

    # both dated, the second told with an EARLIER date: by the dates, the first is the later fact
    rt, who = world_with_died_in()
    with timeutil.as_of(datetime(2026, 10, 2, 2, 21)):
        rt.world.relate(who, rt.world.get("Thing", name="Moscow"), "died_in",
                        starts=datetime(2020, 3, 1))
    with timeutil.as_of(datetime(2026, 10, 2, 2, 40)):
        rt.world.relate(who, rt.world.get("Thing", name="United States of America"), "died_in",
                        starts=datetime(2020, 1, 1))
    check("both dated: the dates decide, not the order they were told in",
          standing(rt) == ["Moscow"], str(standing(rt)))


def the_names_pass_writes_as_of_when_the_words_were_said() -> None:
    """A link drawn out of an old account must not overrule a correction told after it.

    Found 2026-10-02: the names pass read "Nobuhiro Watsuki — famous for Rurouni Kenshin" (said at
    the first telling) and wrote `it.famous_for = …` *now*, which by the order of tellings ended
    "The Fairly OddParents" — the user's correction, and the gold answer.
    """
    import json

    from terraweaver import portraits, timeutil

    class Jev:
        def choose(self, state, question, options):
            return {}

        def ask(self, state, questions):
            return {}

    class Engineer:
        def json(self, system, asked):
            return {"class": None, "code": 'it.set_famous_for(Thing.get(name="Rurouni Kenshin"))'}

        def say(self, system, asked):
            return json.dumps(self.json(system, asked))

    rt = base.world()
    base.word(rt, "famous_for", "what somebody is famous for", cardinality="many-to-one",
              subject_is="the famous one", object_is="what they are famous for")
    for name in ("Rurouni Kenshin", "The Fairly OddParents"):
        rt.world.new("Thing", name=name)
    with timeutil.as_of(datetime(2026, 10, 2, 1, 58)):
        watsuki = rt.world.new("Person", name="Nobuhiro Watsuki")
        watsuki.describe("Manga artist, famous for Rurouni Kenshin")
        portraits.comes_in(rt.world, watsuki)
        rt.world.relate(watsuki, rt.world.get("Thing", name="Rurouni Kenshin"), "famous_for")
    with timeutil.as_of(datetime(2026, 10, 2, 2, 20)):
        rt.world.relate(watsuki, rt.world.get("Thing", name="The Fairly OddParents"), "famous_for")
    portraits.formalise(rt.world, Engineer(), jev=Jev())
    now = [one.object.display_name()
           for one in rt.world.get("Person", name="Nobuhiro Watsuki").relations("famous_for")]
    check("the correction still stands after the names pass", now == ["The Fairly OddParents"], str(now))


def everything_is_called_by_its_name() -> None:
    """A person, an event, a class a host defines: what each is called is its `name`.

    Decided 2026-10-02. A person had `full_name` and an event `title`: the host wrote
    `Thing.identify(full_name=...)` and `Person.get(name=...)` and was refused, a placing from Thing
    to Person had to carry the name from one word to another, and a listing over the kinds of
    Thing broke on the first Person. A world written before that is brought over on opening.
    """
    from terraweaver import matching, open_world

    rt = base.world()
    define = rt.world.extras["define"]
    book = define("Book", "a written work published as a volume")
    check("a class defined with nothing said about its identity is known by its name",
          [a["name"] for a in book._spec["attributes"]][0] == "name"
          and matching.NAME_KEYS.get("Book") == "name", str(book._spec["attributes"]))
    film = define("Film", "a motion picture made to be shown", "title")
    check("a title is the name", "title" not in [a["name"] for a in film._spec["attributes"]]
          and film(title="Alien").name == "Alien")
    paper = define("Paper", "a published scientific article", "doi")
    names = [a["name"] for a in paper._spec["attributes"]]
    check("another key is its own attribute beside the name, and tells two apart on its own",
          names[0] == "name" and "doi" in names and matching.STRONG_KEYS.get("Paper") == ["doi"],
          f"{names} {matching.STRONG_KEYS.get('Paper')}")

    ann = rt.world.new("Person", name="Ann Lee")
    check("the old word still reads and writes the name",
          ann.full_name == "Ann Lee" and rt.world.get("Person", full_name="Ann Lee").id == ann.id)

    # --- a world written while a person had a full_name ---
    old = base.world(kept=True)
    kyd = old.world.new("Person", name="Thomas Kyd")
    conn = old.world.store.conn
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'facts_%'").fetchall():
        conn.execute(f'UPDATE "{table}" SET slot = \'full_name\' WHERE slot = \'name\' AND subject = ?',
                     (kyd.id,))
    conn.execute("UPDATE Person SET attr = 'full_name' WHERE attr = 'name' AND instance_id = ?",
                 (kyd.id,))
    conn.commit()
    path = conn.execute("PRAGMA database_list").fetchone()[2]
    conn.close()
    again = open_world(path)
    back = again.world.store.load(kyd.id, again.world.classes)
    check("a world written with full_name opens with the name where it belongs",
          back is not None and back.name == "Thomas Kyd",
          repr(getattr(back, "name", None)))
    check("in the record as well", any(one.slot == "name" and one.value == "Thomas Kyd"
                                       for one in again.world.facts.about(kyd.id)),
          str([(one.slot, one.value) for one in again.world.facts.about(kyd.id)]))


def several_under_one_word_are_said_in_the_order_they_were_told() -> None:
    """Two tellings standing under one word: the read says which came last, and ends nothing.

    Found 2026-10-03 on var/run10: "Klapisch citizen_of France", then "… of Malaysia", under a word
    that holds several; and "Microsoft ceo_of Satya Nadella" written the other way round beside
    "Steve Jobs ceo_of Microsoft". The host was handed both and chose by what it knew of the world.
    """
    from terraweaver import ontology, timeutil

    rt = base.world()
    base.word(rt, "citizen_of", "a person being a citizen of a country", "many-to-many",
              subject_is="the citizen", object_is="the country")
    base.word(rt, "ceo_of", "a person running a company as its chief executive", "many-to-one",
              subject_is="the chief executive", object_is="the company")
    w = rt.world
    klapisch = w.new("Person", name="Cédric Klapisch")
    france, malaysia = w.new("Thing", name="France"), w.new("Thing", name="Malaysia")
    microsoft = w.new("Thing", name="Microsoft")
    nadella, jobs = w.new("Person", name="Satya Nadella"), w.new("Person", name="Steve Jobs")
    with timeutil.as_of(datetime(2020, 1, 3)):
        w.relate(klapisch, france, "citizen_of")
        w.relate(microsoft, nadella, "ceo_of")            # the other way round
    with timeutil.as_of(datetime(2020, 1, 9)):
        w.relate(klapisch, malaysia, "citizen_of")
        w.relate(jobs, microsoft, "ceo_of")

    with ontology.record_changes() as heard:
        both = klapisch.related("citizen_of")
    check("both still stand", {x.display_name() for x in both} == {"France", "Malaysia"},
          str([x.display_name() for x in both]))
    said = " ".join(heard.hints)
    check("and the read says which was told last",
          "the last told is" in said and said.index("Malaysia") < said.index("France"), said[:300])

    with ontology.record_changes() as heard:
        microsoft.related("ceo")
    said = " ".join(heard.hints)
    check("a telling written the other way round is named beside it",
          "the other way round" in said and "Satya Nadella" in said and "Steve Jobs" in said,
          said[:300])
    check("the later one first", "Steve Jobs" in said and said.index("Steve Jobs") < said.index("Satya"),
          said[:300])


def a_statement_that_never_ran_keeps_the_task_open() -> None:
    """A write that failed is owed until it runs; the close says which, in the host's own words.

    Measured 2026-10-03 on var/run11: 18 of 22 facts never recorded were on lines of a block that
    failed there, and the host's continuation printed them as recorded instead of writing them.
    """
    rt = base.world()
    rt.run('anna = Thing.new(name="Anna")\n'
           'berlin = Thing.new(name="Berlin")\n'
           'anna.relate(berln, "Anna lives in Berlin")\n'
           'anna.describe("a friend from school")', "k")
    first = rt.finish_task("k")
    check("the close names the statement that never ran",
          "Not closed" in first and 'anna.relate(berln, "Anna lives in Berlin")' in first,
          str(first)[:300])
    check("and not the ones that did", 'anna.describe("a friend' not in first, str(first)[:300])

    rt.run('berln = berlin\nanna.relate(berln, "Anna lives in Berlin")\n'
           'berlin.describe("the city Anna lives in")', "k")
    closed = rt.finish_task("k")
    check("running the same statement settles it", "Not closed" not in str(closed)
          and "never ran" not in str(closed), str(closed)[:300])

    # Said again in other words — another call, the other way round, a name for a variable —
    # is the fact recorded: what it named has been written about since, all of it.
    rt.start_task("k3", "record a fact the long way round", "recording")
    rt.run('anna = Thing.get(name="Anna")\nworld.relate(anna, "Berlin", "lives_in")', "k3")
    rt.run('berlin = Thing.get(name="Berlin")\n'
           'berlin.relate(anna, "Berlin is where Anna lives")', "k3")
    other_words = rt.finish_task("k3")
    check("a fact said again in other words is not owed",
          "never ran" not in str(other_words) and "Not closed" not in str(other_words),
          str(other_words)[:300])

    rt.start_task("k2", "record another fact", "recording")
    rt.run('anna = Thing.get(name="Anna")\nanna.relate(munich, "Anna works in Munich")\n'
           'paris = Thing.new(name="Paris")\nparis.describe("the city Anna studied in")\n'
           'anna.relate(paris, "Anna studied in Paris")', "k2")
    rt.finish_task("k2")
    rt.run('print("Anna works in Munich — recorded")', "k2")
    again = rt.finish_task("k2")
    check("printing it does not, and the second close passes with it said",
          "Not closed" not in str(again) and "never ran" in str(again)
          and "Munich" in str(again), str(again)[:400])


def a_thing_made_by_hand_is_in_the_record_as_well_as_the_image() -> None:
    """A thing built with its constructor and passed as a link's far end is stated, not only shown.

    Measured 2026-10-03: three things in a 125-fact world existed as images and nowhere in the
    record, six links pointing at them; a rebuild from the record cut those links off at the end.
    """
    rt = base.world()
    rt.run('nietzsche = Person.new(name="Friedrich Nietzsche")\n'
           'book = Thing(name="The Birth of Tragedy")\n'
           'nietzsche.relate(book, "Nietzsche wrote The Birth of Tragedy")', "k")
    book = rt.world.find("Thing", name="The Birth of Tragedy").matches[0]
    check("the far end is in the record", any(one.slot == "name" for one in rt.world.facts.about(book.id)),
          str([(one.slot, one.value) for one in rt.world.facts.about(book.id)]))
    rt.world.rebuild()
    again = rt.world.get("Person", name="Friedrich Nietzsche")
    check("and the link survives a rebuild, both ends on it",
          [link.other(again).display_name() for link in again.relations()] == ["The Birth of Tragedy"],
          str([link.display_name() for link in again.relations()]))


def what_a_run_changed_is_shown_as_the_record_says_it() -> None:
    """At the end of a run, the image of what it changed is the record's reading, not the object's.

    Rule 4 of docs/architecture.md. A door that changes an object without saying it — the shell a
    failed load left, which nulled 31 names in a 455-fact world — must not reach the image.
    """
    from terraweaver import ontology

    rt = base.world()
    rt.run('kyd = Person.new(name="Thomas Kyd")\nkyd.describe("an English playwright")', "k")
    kyd = rt.world.get("Person", name="Thomas Kyd")
    with ontology.trusted_writes(), ontology.not_recording():
        kyd.name = None                       # a door that says nothing
    rt.run('kyd.describe("born in London")', "k")
    row = rt.world.store.conn.execute(
        "SELECT value FROM Person WHERE instance_id = ? AND attr = 'name'", (kyd.id,)).fetchone()
    check("the image holds the name the record holds", row and row[0] == '"Thomas Kyd"', str(row))
    check("and so does the object the host is holding", kyd.name == "Thomas Kyd", repr(kyd.name))
    check("with both descriptions", set(kyd.descriptions or []) == {"an English playwright",
                                                                     "born in London"},
          str(kyd.descriptions))


def main() -> None:
    what_a_run_changed_is_shown_as_the_record_says_it()
    a_thing_made_by_hand_is_in_the_record_as_well_as_the_image()
    a_statement_that_never_ran_keeps_the_task_open()
    several_under_one_word_are_said_in_the_order_they_were_told()
    everything_is_called_by_its_name()
    the_names_pass_writes_as_of_when_the_words_were_said()
    a_hand_over_compares_like_with_like()
    the_later_telling_stands_whichever_order_it_is_read_in()
    an_image_never_goes_to_storage_without_the_name_its_record_holds()
    a_lookup_sees_the_classes_beneath_it()
    a_row_that_will_not_load_costs_only_that_row()
    the_names_pass_changes_the_class_and_nothing_else()
    a_placing_is_stated_so_it_survives_a_rebuild()
    finding_3_1_6_a_separation_holds_through_a_third_party()
    finding_3_3_7_the_echo_says_what_actually_ran()
    finding_3_3_3_a_task_that_cannot_close_is_still_dropped()
    finding_3_3_4_one_sessions_modules_are_its_own()
    finding_3_3_1_and_3_3_2_the_variable_tools()
    finding_3_2_1_a_clean_handover_is_not_two_at_once()
    finding_3_2_2_one_question_per_thing_not_per_pair()
    finding_3_1_2_one_subject_rebuilt_keeps_its_repeats()
    finding_3_1_3_the_later_statement_wins_under_a_moved_clock()
    finding_2_3_only_the_transaction_commits()
    finding_3_4_1_the_engineer_is_not_a_function()
    finding_3_4_2_a_link_that_was_already_there_is_not_this_readings_work()
    print()
    if failures:
        print(f"{len(failures)} failed: " + ", ".join(failures))
        sys.exit(1)
    print("all passed")


if __name__ == "__main__":
    main()
