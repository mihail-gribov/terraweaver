"""Tests for how the world keeps state — the failures here are the silent kind.

Nothing in this file needs a model. It covers the cases where the world can look fine and
be wrong: a change reverted by a stale copy, a half-linked relationship, a fact that never
reached storage.

Run: python3 tests/test_world_state.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.resolution import ResolutionRequired, run_skill
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
    classes = build_classes(load_specs(ONTOLOGY_DIR), IMPLS)
    store = Store(":memory:")
    build(classes, store)
    return classes, store, World(store, classes)


def main() -> int:
    classes, store, world = fresh_world()
    Person, Organization = classes["Person"], classes["Organization"]

    # --- one row is one object ---
    first = Person.find(email="ada@example.com").main[0]
    second = Person.find(email="ada@example.com").main[0]
    check("the same row loads as the same object", first is second)

    # A settled change must survive an older reference to the same entity being saved again.
    # This is how a resolved contradiction used to revert itself: whoever saved last won.
    dataworks = Organization.find(name="DataWorks").main[0]
    needs = world.ensure(Person, email="ada@example.com", organization=dataworks)
    run_skill(needs, lambda question, options: 0, world)
    store.save_graph(first)  # an earlier reference, saved after the change
    check("a settled change isn't overwritten by an older reference",
          Person.find(email="ada@example.com").main[0].organization.name == "DataWorks")

    # --- relationships hold on both sides ---
    classes, store, world = fresh_world()
    Person, Organization = classes["Person"], classes["Organization"]
    bob = Person(full_name="Steve", email="steve@acme.com")
    acme = Organization(name="Acme")
    bob.organization = acme
    bob.save()
    stored_acme = Organization.find(name="Acme").main[0]
    check("linking one side links the other", [p.full_name for p in stored_acme.employees] == ["Steve"])
    acme.add_contact(bob)
    check("linking again through a method doesn't list them twice", [p.full_name for p in acme.employees] == ["Steve"])
    check("and it survives storage", Person.find(email="steve@acme.com").main[0].organization.name == "Acme")

    # --- a fact reaches storage even when the return value is thrown away ---
    classes, store, world = fresh_world()
    Person = classes["Person"]
    ada = Person.find(email="ada@example.com").main[0]
    before = len(store.load_all("Preference", classes))
    ada.add_fact(predicate="likes", value="chess")  # return deliberately discarded
    ada.save()
    facts = store.load_all("Preference", classes)
    check("a discarded fact still gets stored", len(facts) == before + 1)
    check("and it points at the right person",
          any(f.value == "chess" and f.subject.full_name == "Ada Lovelace" for f in facts))

    # --- a contradicting write can't slip past ---
    classes, store, world = fresh_world()
    Person, Organization = classes["Person"], classes["Organization"]
    ada = Person.find(email="ada@example.com").main[0]
    dataworks = Organization.find(name="DataWorks").main[0]
    refused = False
    try:
        ada.organization = dataworks
    except ResolutionRequired:
        refused = True
    check("a contradicting attribute write is refused", refused)
    check("and it names the skill that settles it",
          world.pending is not None and world.pending.skill == "resolve_contradiction")
    check("the world is untouched until the user decides",
          Person.find(email="ada@example.com").main[0].organization.name == "TechCorp")

    # --- printing an entity can't blow up ---
    # The world is a graph with cycles (person -> company -> employees -> person). Recursing
    # through them in repr exhausted the stack the moment the model gained another link, and
    # it surfaced as "the agent is flaky" rather than as our bug.
    classes, store, world = fresh_world()
    Event, Person = classes["Event"], classes["Person"]
    try:
        text = repr(Event.all(limit=None))
        blew_up = False
    except RecursionError:
        text, blew_up = "", True
    check("printing a cyclic graph doesn't recurse", not blew_up)
    check("references appear as labels, not expansions", "<Vacancy " in text or "<Organization " in text, text[:120])
    check("and the text stays readable", len(repr(Person.find(email="ada@example.com").main[0])) < 400)

    classes, store, world = fresh_world()
    Person, Organization = classes["Person"], classes["Organization"]
    ada = Person.find(email="ada@example.com").main[0]

    # --- an unrelated write is left alone ---
    ada.phone = "+7 900 000-00-00"
    check("a non-conflicting write goes through", ada.phone == "+7 900 000-00-00")

    # --- a subgraph is stored whole or not at all ---
    # Linking a new person to a new company touches both; if the second one can't be written,
    # the first must not stay behind as a half-link.
    classes, store, world = fresh_world()
    Person, Organization = classes["Person"], classes["Organization"]
    people_before = len(store.load_all("Person", classes))
    orgs_before = len(store.load_all("Organization", classes))
    carol = Person(full_name="Carol", email="carol@initech.com")
    initech = Organization(name="Initech")
    carol.organization = initech
    initech.notes = {"unserializable"}  # a set can't be encoded, so the graph fails midway
    failed = False
    try:
        store.save_graph(carol)
    except TypeError:
        failed = True
    check("a failing graph save raises", failed)
    check("and leaves no part of the graph stored",
          len(store.load_all("Person", classes)) == people_before
          and len(store.load_all("Organization", classes)) == orgs_before)
    check("and gives back the ids it handed out", carol.id is None and initech.id is None)
    initech.notes = None
    store.save_graph(carol)
    check("the same graph saves once fixed",
          Person.find(email="carol@initech.com").main[0].organization.name == "Initech")

    # A transaction spanning several graphs — one agent script's changes — is one unit too.
    classes, store, world = fresh_world()
    Person = classes["Person"]
    before = len(store.load_all("Person", classes))
    try:
        with store.transaction():
            store.save_graph(Person(full_name="Dave", email="dave@example.com"))
            raise RuntimeError("the script failed after its first write")
    except RuntimeError:
        pass
    check("an aborted transaction undoes writes that already happened inside it",
          len(store.load_all("Person", classes)) == before)

    # --- dated remarks hold what the attributes have no place for ---
    from datetime import date
    classes, store, world = fresh_world()
    Person = classes["Person"]
    ada = Person.find(email="ada@example.com").main[0]
    ada.comment("allergic to nuts")
    ada.comment("might move to Berlin", when=date(2026, 10, 1), tentative=True)
    texts = [c.text for c in ada.comments()]
    check("remarks come back newest first", texts == ["might move to Berlin", "allergic to nuts"], str(texts))
    check("a tentative remark says so", ada.comments(contains="Berlin")[0].tentative)
    ada.comments(contains="nuts")[0].forget()
    check("a forgotten remark is gone", [c.text for c in ada.comments()] == ["might move to Berlin"])
    try:
        with store.transaction():
            ada.comment("never kept")
            raise RuntimeError("the run failed after commenting")
    except RuntimeError:
        pass
    check("a remark from a failed run isn't kept", not ada.comments(contains="never kept"))
    # --- remarks go stale, into history rather than away ---
    from datetime import timedelta
    ada.comment("lived in Moscow", when=date(2020, 1, 1), until=date(2025, 6, 1))
    ada.comment("allergic to nuts", permanent=True)
    ada.comment("likes coffee")
    current = {c.text for c in ada.comments()}
    check("an expired remark drops out of ordinary reads", "lived in Moscow" not in current, str(current))
    check("and stays in the history",
          any(c.text == "lived in Moscow" and c.expired for c in ada.comments(include_expired=True)))
    check("a permanent remark has no end", ada.comments(contains="nuts")[0].until is None)
    check("an unsaid end gets the default", ada.comments(contains="coffee")[0].until is not None)
    coffee = ada.comments(contains="coffee")[0]
    coffee.keep(ttl=timedelta(days=-1))
    check("the host can change how long a remark holds", not ada.comments(contains="coffee"))

    # --- a record's period: ended things become history, never disappear ---
    from terraweaver.conditions import after, before, between, now
    Vacancy, Organization, Event = classes["Vacancy"], classes["Organization"], classes["Event"]
    dataworks = Organization.find(name="DataWorks").main[0]
    closed = Vacancy.ensure(title="Staff SRE", organization=dataworks, ttl=timedelta(days=-1))
    check("an ended record drops out of ordinary reads",
          "Staff SRE" not in [v.title for v in Vacancy.find(organization=dataworks)])
    check("and stays reachable as history",
          "Staff SRE" in [v.title for v in Vacancy.find(organization=dataworks, history=True)])
    check("identity is timeless: ensure finds the ended one instead of duplicating it",
          Vacancy.ensure(title="Staff SRE", organization=dataworks) is closed)

    # --- time ranges in find compare safely whatever the time zone ---
    upcoming, past = Event.find(start_time=after(now())), Event.find(start_time=before(now()))
    check("upcoming and past events split the calendar",
          len(upcoming) + len(past) == len(Event.all(limit=None)) and upcoming and past)
    week = Event.find(start_time=between(date.today(), date.today() + timedelta(days=7)))
    check("a date as the end of a range includes that day", all(e in upcoming for e in week))

    # --- the host says whether it means an existing entity or a new one ---
    from terraweaver.world import NotInWorld
    cloudnine = Organization.get(name="CloudNine")
    check("get picks out the one meant, using context",
          Person.get(full_name="Annie", organization=cloudnine).full_name == "Anna Sullivan")
    try:
        Person.get(full_name="Pete Ivanson")
        missing_raises = False
    except NotInWorld:
        missing_raises = True
    check("get never creates: someone absent is a loud error", missing_raises)
    check("and a name only sharing a part with someone doesn't resemble them",
          missing_raises and not Person.find(full_name="Pete Ivanson", history=True))
    petr = Person.new(full_name="Pete Ivanson", email="pete@x.org")
    check("new creates", isinstance(petr, Person) and petr.id is not None)
    twin = Person.new(full_name="Pete Ivanson", email="pete@x.org")
    check("new asks before creating a twin", getattr(twin, "skill", None) == "resolve_ambiguity")
    check("settling the twin as the same one returns it", world.settle(twin, petr) is petr)

    # --- who the user meant by a name is remembered ---
    annie = Person.find(full_name="Annie")
    sullivan = Person.get(email="anna.sullivan@example.com")
    world.settle(annie, sullivan)
    check("once settled, the name picks that person", Person.get(full_name="Annie") is sullivan)
    check("and ensure by that name doesn't call the nickname a contradiction",
          Person.ensure(full_name="Annie", phone="555") is sullivan)
    world.remember_choice(annie, None)  # what answering "someone new" to that question records
    check("someone new under the name makes it a question again",
          getattr(Person.find(full_name="Annie"), "skill", None) == "resolve_ambiguity")

    # --- a list attribute that only grows is not a contradiction ---
    Project, Idea = classes["Project"], classes["Idea"]
    tv = Project.new(name="Living room TV")
    first = Idea.new(title="TV candidate: Samsung QN90D", content="Candidate.")
    tv.related_to = [first]
    tv.related_to = tv.related_to + [Idea.new(title="TV candidate: Sony Bravia 8", content="Candidate.")]
    check("appending to a list goes through", len(tv.related_to) == 2)
    refused = False
    try:
        tv.related_to = [tv.related_to[1]]
    except ResolutionRequired:
        refused = True
    check("dropping an item from it is still a question", refused)

    store.clear_all()
    check("a rebuilt world starts without old remarks",
          not store.conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all world-state tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
