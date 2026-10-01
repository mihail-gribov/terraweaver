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
    person = rt.world.new("Person", full_name="Ann")
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
    person = rt.world.new("Person", full_name="Anne Hidalgo")
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
    got = rt.run('x = [Person.new(full_name="Ann", tags=["friend"]), 1/0]', "host")
    check("2.3 the run says it failed", not got.get("ok"), str(got)[:160])
    check("2.3 and nothing it wrote is there", people() == was,
          "Ann survived a statement that raised, because a tags write committed under her")

    plain = rt.run('y = [Person.new(full_name="Bob"), 1/0]', "host")
    check("2.3 the case that always worked still works", not plain.get("ok") and people() == was)

    # And outside a transaction a commit is still a commit, or nothing would ever be durable.
    kept = rt.run('z = Person.new(full_name="Cleo")', "host")
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
        facts.state("p1", "full_name", "Ada", source="agent")
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
    ada = rt.world.new("Person", full_name="Ada")
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
        rt.world.relate(rt.world.new("Person", full_name=f"P{n}"), firm, "works_at")
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
    first = rt.world.relate(rt.world.new("Person", full_name="A"), city, "mayor_of",
                            starts=datetime(2010, 1, 1), until=datetime(2020, 1, 1))
    second = rt.world.relate(rt.world.new("Person", full_name="B"), city, "mayor_of",
                             starts=datetime(2020, 1, 1))
    check("3.2.1 a handover is one at a time", properties._at_once([first, second]) == 1,
          f"_at_once said {properties._at_once([first, second])}")


def finding_3_3_1_and_3_3_2_the_variable_tools() -> None:
    """`set_variable` must work at all, and no variable may take a name the world binds."""
    from terraweaver.variables import VariableError

    rt = base.world()
    rt.run('ada = Person.new(full_name="Ada")', "host")
    got = rt.set_variable("host", "ada", 'Person.find(full_name="Ada").matches[0]',
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
    rt.run('ada = Person.new(full_name="Ada")', "host")     # a recording task with a bare name
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
    got = rt.run('a = Person.new(full_name="One")\nb = 1/0\nc = Person.new(full_name="Two")',
                 "host")
    shown = format_result(got)
    made = rt.world.store.conn.execute(
        "SELECT count(*) FROM instances WHERE class_name = 'Person'").fetchone()[0]
    check("3.3.7 both people the block made are in the world", made == 3, f"{made} people")
    check("3.3.7 the error does not claim the rest never ran",
          "never ran" not in (got.get("error") or ""), got.get("error"))
    check("3.3.7 and the echo gives the lines that ran back as code",
          'c = Person.new(full_name="Two")' in shown
          and '# c = Person.new(full_name="Two")' not in shown, shown[:400])

    # A line that is not code at all is not a line anything reached or failed on. Marked as
    # "never reached" it said so of a comment above a line that had just run.
    commented = format_result(rt.run(
        '# record the people\na = Person.new(full_name="Three")\n\n# and one that fails\n'
        'b = 1/0\nc = Person.new(full_name="Four")\nd = 1/0\ne = 1/0\n'
        'f = Person.new(full_name="Five")', "host"))
    check("3.3.7 a comment is handed back as written",
          "# record the people" in commented
          and "(never reached) # record the people" not in commented, commented[:500])
    check("3.3.7 and a statement nothing reached says so",
          '# (never reached) f = Person.new(full_name="Five")' in commented, commented[:600])


def finding_3_1_6_a_separation_holds_through_a_third_party() -> None:
    """Told a and c are different: a rule match between b and c may not join them anyway."""
    import sqlite3

    from terraweaver import assembly
    from terraweaver.facts import Facts, reference

    def groups(separated: bool):
        facts = Facts(sqlite3.connect(":memory:"))
        facts.state("a", "full_name", "Ann Lee", source="user")
        facts.state("b", "full_name", "Anna Sullivan", source="user")
        facts.state("c", "full_name", "Anna Sullivan", source="user")
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


def a_reading_may_not_rename_the_thing_it_is_reading() -> None:
    """The world says what a thing is; which thing it is was settled before it was asked.

    Not from the review — found on 2026-09-30 on a gate of 25 facts. The engineer reading the
    position called "center" wrote `it.name = "Lisa Leslie"`, the name of the person who plays it,
    and the position was renamed: the fact "Lisa Leslie plays the position of center" then read as
    a fact the world had lost, and the world held two things called Lisa Leslie. The rule was in
    portraits.py's own docstring and nothing enforced it.
    """
    rt = base.world()
    position = rt.world.new("Thing", name="center")
    rt.world.new("Person", full_name="Lisa Leslie")

    renamed = rt._the_world_writes(position, 'it.name = "Lisa Leslie"')
    check("a reading cannot rename the thing", not renamed.get("ok"), str(renamed)[:160])
    again = rt.world.store.load(position.id, rt.world.classes)
    check("and the thing keeps its name", again.display_name() == "center",
          repr(again.display_name()))

    # The same name said again is not a change, and a reading that repeats it is not refused.
    same = rt._the_world_writes(position, 'it.name = "center"\nit.describe("a basketball position")')
    check("saying the same name again goes through", same.get("ok"), str(same.get("error"))[:160])

    # And outside a reading the name is the host's to correct, as it always was.
    position.name = "centre"
    rt.world.save(position)
    check("the host can still correct a name", position.name == "centre")


def a_row_that_will_not_load_costs_only_that_row() -> None:
    """A refusal on one stored value must not cost the image, and must not leave a shell behind.

    Not from the review — found 2026-10-01 by `experiments/why_it_failed.py` on a 455-fact world:
    21 entities held a name in the record and nothing in the image, and it was 29 of the 105 facts
    that world did not hold. The identity map registers an object before its values are filled,
    because a cyclic reference has to find it there; a fill that raised left the half-built object
    in the map, and from then on `Person.get(full_name=…)` answered `NotInWorld` about something
    the record plainly held, while the next `save` wrote null over every value it had.
    """
    from terraweaver import store as store_module

    rt = base.world()
    kyd = rt.world.new("Person", full_name="Thomas Kyd")
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

    check("the load keeps everything else", getattr(loaded, "full_name", None) == "Thomas Kyd",
          repr(getattr(loaded, "full_name", None)))
    check("and the one row that would not read is the one thing missing",
          getattr(loaded, "descriptions", None) in (None, []),
          repr(getattr(loaded, "descriptions", None)))

    found = rt.world.get("Person", full_name="Thomas Kyd")
    check("the world still knows it is there", getattr(found, "full_name", None) == "Thomas Kyd",
          repr(found))
    rt.world.save(found)
    row = dict(rt.world.store.conn.execute(
        "SELECT attr, value FROM Person WHERE instance_id = ? AND attr = 'full_name'", (held,)))
    check("and saving it does not write null over the name", row.get("full_name") == '"Thomas Kyd"',
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

    listed = rt.run('print([i.name for i in Thing.all(limit=None)])', "host")
    check("a listing is exact, so the host's own idiom still runs", listed.get("ok"),
          str(listed.get("error"))[:120])
    check("and the world says what is a kind of it rather than answering nothing",
          any("kind of it" in one for one in (listed.get("hints") or [])),
          str(listed.get("hints"))[:160])
    check("everything under it, for whoever asks",
          len(rt.world.all("Thing", limit=None, kinds=True)) >= 1)


def main() -> None:
    a_lookup_sees_the_classes_beneath_it()
    a_row_that_will_not_load_costs_only_that_row()
    a_reading_may_not_rename_the_thing_it_is_reading()
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
