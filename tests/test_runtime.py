"""Tests for the host runtime: runs, rollbacks and what survives between them.

Run: .venv/bin/python tests/test_runtime.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import initiative

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def seeded(task: str | None = None):
    """A base world with the people the name checks talk about: two Annas "Annie" could be."""
    rt = base.world(task, kept=True)
    rt.run('Person.new(full_name="Ada Lovelace")\n'
           'Person.new(full_name="Anna Sullivan")\n'
           'Person.new(full_name="Anna Peterson")', "seed")
    return rt


def main() -> int:
    # --- a settled value survives a rollback that happened between the question and the answer ---
    # Seen with a real host: the question was kept in a variable, a later run failed and was rolled
    # back, then settling applied the answer to an orphaned copy while another stale copy was saved
    # over it — the old value came back.
    rt = seeded()
    base.attribute(rt, "Person", "city", "The city this person lives in.")
    base.attribute(rt, "Person", "phone", "The number this person answers.", type="phone")
    rt.run('ada = Person.get(full_name="Ada Lovelace")\nada.city = "London"', "host")
    rt.run('q = Person.ensure(full_name="Ada Lovelace", city="Paris")\n'
           'ada = Person.get(full_name="Ada Lovelace")', "host")
    failed = rt.run('ada.phone = "123"\nraise RuntimeError("the host made a mistake")', "host")
    check("the failing run is rolled back", not failed["ok"])
    settled = rt.run('world.settle(q, "Paris")', "host")
    check("settling afterwards goes through", settled["ok"], str(settled["error"]))
    after = rt.run('print(Person.get(full_name="Ada Lovelace").city)', "check")
    check("and the settled value is what the world holds", after["output"].strip() == "Paris", after["output"])

    # --- a run stops where it breaks and keeps what it had already done ---
    # All-or-nothing was the rule here until the measurements turned against it: a fifth to a
    # quarter of every pool's runs ended discarded, most over a typo far from anything that
    # mattered, and the heavy work before it was re-run for nothing.
    rt = seeded()
    rt.run('i = Thing.new(name="Leftover")\nraise RuntimeError("boom")', "host")
    left = rt.run('print(len([i for i in Thing.all(limit=None) if i.name == "Leftover"]))', "check")
    check("what a completed statement wrote is kept when a later one fails",
          left["output"].strip() == "1", left["output"])

    # --- the export is plain JSON, dates included ---
    rt = seeded()
    rt.run('Person.get(full_name="Ada Lovelace").describe("met at a conference", when=date(2026, 9, 1))', "host")
    import json
    try:
        json.dumps(rt.export())
        exported = True
    except TypeError:
        exported = False
    check("the export serializes comments with plain dates", exported)

    # --- a failed run says what it threw away ---
    # Seen with a real host: a run created a job, printed it, then failed on the next line. The
    # host read its own print as success and re-sent only the failing line — the job was gone.
    rt = seeded()
    rt.world.extras["define_relation"](
        "works_at", "a person working for an employer", cardinality="many-to-one",
        subject_is="a person who works", object_is="their employer",
        attributes=[{"name": "kind", "type": "str",
                     "description": "What sort of work it is — employment, a contract, a placement."}])
    base.word(rt, "dentist_of", "a dentist and the person they treat", "one-to-many",
              "a dentist", "a patient")
    base.word(rt, "landlord_of", "a landlord and the person who rents from them", "one-to-many",
              "a landlord", "a tenant")
    rt.run('Thing.new(name="FinEdge")', "host")
    from terraweaver.runtime import format_result
    broken = rt.run('mark = Person.new(full_name="Mark Stone")\n'
                    'mark.set_works_at(Thing.get(name="FinEdge"))\n'
                    'raise RuntimeError("later line fails")', "host")
    shown = format_result(broken)
    check("the failure says where it stopped and that what came before is kept",
          "before this one are done and kept" in shown, shown)
    kept = rt.run('print(len([p for p in Person.all(limit=None) if p.full_name == "Mark Stone"]))', "host")
    check("the person the first statement made is in the world",
          kept["output"].strip() == "1", str(kept["output"] or kept["error"]))
    still = rt.run('org = Thing.get(name="FinEdge")\n'
                   'note = "for later"\n'
                   'raise RuntimeError("stop")', "host")
    cut = rt.run('a = 1\nb = 2\nraise RuntimeError("stop")\nc = 3\nd = 4', "host")
    check("the failure names the line it broke on, with its text",
          'line 3: raise RuntimeError("stop")' in cut["error"], cut["error"])
    # Four lines of five ran: a statement that raises does not end the block, so what the error
    # says about the rest has to be what happened. "2 after it never ran" was the old wording and
    # it was false — the host read it and sent those lines again.
    check("and says how many lines ran and are in the world",
          "4 line(s) elsewhere in the block ran" in cut["error"]
          and "never ran" not in cut["error"], cut["error"])

    shown_still = format_result(still)
    check("and a failed run hands the block back as it stands",
          "# --- what the world did with this block, line by line ---" in shown_still
          and "# !! raise RuntimeError" in shown_still, shown_still)
    check("with the lines that ran given back as code, not commented",
          'note = "for later"' in shown_still and '# note = "for later"' not in shown_still,
          shown_still)
    undone = rt.run('print(len([p for p in Person.all(limit=None) if p.full_name == "Never Made"]))', "host")
    check("and the statement that raised left nothing of its own", undone["output"].strip() == "0",
          undone["output"])

    # --- a relation's own attribute may be called kind ---
    ok = rt.run('rita = Person.new(full_name="Rita Sandoval")\n'
                'm = rita.set_works_at(Thing.get(name="FinEdge"), kind="employment")\n'
                'print(m.kind)', "host")
    check("relate takes kind= as the relation's attribute", ok["output"].strip() == "employment",
          str(ok["error"]) or ok["output"])

    # --- periods compare with plain dates ---
    dates = rt.run('r = Person.new(full_name="Nina Patel").set_dentist_of(user, '
                   'starts=date(2026, 10, 1))\n'
                   'print(r.starts >= date(2026, 9, 1), r.starts == date(2026, 10, 1), r.starts < today())', "host")
    check("a period bound compares with a date instead of raising",
          dates["output"].strip() == "True True False", str(dates["error"]) or dates["output"])

    # --- a remark on an entity is visible when the entity is printed ---
    marked = rt.run('greg = Person.new(full_name="Greg Hunt")\n'
                    'rel = greg.set_landlord_of(user)\n'
                    'rel.describe("rent is $2,100 a month", permanent=True)\n'
                    'print(rel)', "host")
    check("printing an entity shows it carries remarks", "1 remark" in marked["output"], marked["output"])

    # --- the answer to "which one?" arrives as what the host does next ---
    # Remembering which entity a name meant is the world acting on its own, so it is off by
    # default and this block turns it on for what it checks.
    initiative.LEARNS_NAMES = True
    choice = seeded()
    choice.run('annie = Person.find(full_name="Annie")', "one")
    told = choice.run('anna = Person.get(full_name="Anna Sullivan"); print(anna.full_name)', "one")
    check("working with one of the candidates settles the name",
          any("Anna Sullivan" in line for line in told["assumed"]), str(told["assumed"]))
    later = choice.run('again = Person.find(full_name="Annie"); print(again.matches[0].full_name)', "two")
    check("and a later conversation does not ask again",
          "Anna Sullivan" in (later["output"] or ""), str(later["output"] or later["error"]))

    waiting = seeded()
    waiting.run('annie = Person.get(full_name="Annie")\n'
                'annie.tag("conference")\n'
                'kept = Person.new(full_name="Zoya Ren")', "one")
    check("a question in a batch does not take the rest of it down",
          "Zoya" in (waiting.run('print(Person.get(full_name="Zoya Ren").full_name)', "two")["output"] or ""))
    nagged = waiting.run('print("something else")', "one")
    check("and what is waiting on the answer is said again every run",
          any("waiting on the answer" in q for q in nagged["questions"]), str(nagged["questions"]))

    listing = seeded()
    listing.run('needs = Person.get(full_name="Annie")', "one")
    showed = listing.run('annies = Person.find(full_name="Annie")\n'
                         'for annie in annies.candidates:\n    print(annie.full_name)', "one")
    check("listing the candidates for the user teaches nothing, even a run later",
          showed["assumed"] == [], str(showed["assumed"]))
    picked = listing.run('chosen = Person.get(full_name="Anna Sullivan")\nprint(chosen.full_name)', "one")
    check("and picking one of them is still the answer, said once",
          len([a for a in picked["assumed"] if "Anna Sullivan" in a]) == 1, str(picked["assumed"]))

    loop = seeded()
    asking = loop.run('annie = Person.find(full_name="Annie")\n'
                      'for p in annie.similar[:3]:\n    print(p.full_name)', "one")
    check("printing the candidates settles nothing, whatever a loop leaves bound",
          asking["assumed"] == [], str(asking["assumed"]))
    over_similar = loop.run('for person in annie.similar:\n    print(person.full_name)', "one")
    check("and neither does looping over them a run later",
          over_similar["assumed"] == [], str(over_similar["assumed"]))
    answering = loop.run('anna = Person.get(full_name="Anna Sullivan")\nprint(anna.full_name)', "one")
    check("and the run after it does settle it",
          any("Anna Sullivan" in line for line in answering["assumed"]), str(answering["assumed"]))

    kept = seeded()
    kept.run('annie = Person.find(full_name="Annie")', "one")
    by_find = kept.run('anna = Person.find(full_name="Anna Sullivan")\nprint(anna.matches[0].full_name)', "one")
    check("keeping one of them from a find settles it too",
          any("Anna Sullivan" in line for line in by_find["assumed"]), str(by_find["assumed"]))

    two = seeded()
    two.run('annie = Person.find(full_name="Annie")', "one")
    ambiguous = two.run('pair = [p for p in Person.all(limit=None) if "Anna" in p.full_name]\nprint(len(pair))', "one")
    check("holding both of them settles nothing", ambiguous["assumed"] == [], str(ambiguous["assumed"]))

    broke = seeded()
    broke.run('annie = Person.find(full_name="Annie")', "one")
    failed = broke.run('anna = Person.get(full_name="Anna Sullivan")\nprint(anna.no_such_thing)', "one")
    check("a run that breaks later still leaves the answer standing",
          failed["error"] is not None and any("Anna Sullivan" in line for line in failed["assumed"]),
          str(failed["assumed"]))
    check("and the next conversation goes with it",
          "Anna Sullivan" in (broke.run('print(Person.find(full_name="Annie").matches[0].full_name)',
                                        "two")["output"] or ""))

    apart = seeded()
    apart.run('annie = Person.find(full_name="Annie")', "one")
    unrelated = apart.run('print(Person.get(full_name="Ada Lovelace").full_name)', "one")
    check("someone who was never a candidate settles nothing", unrelated["assumed"] == [],
          str(unrelated["assumed"]))
    check("so the question is still open",
          "False" in (apart.run('print(Person.find(full_name="Annie").matched)', "two")["output"] or ""))
    initiative.LEARNS_NAMES = False

    # A wrong first argument at a class door is answered by the world, not by Python. Measured
    # on the FactConsolidation slice: `world.identify({"name": ...})` raised `'dict' object has
    # no attribute '__name__'`, the recorder lost the turn and wrote untyped prose thereafter.
    doors = base.world()
    for door in ("identify", "new"):
        said = str(doors.run(f'world.{door}({{"name": "Fatah"}})', "doors")["error"] or "")
        check(f"a dict at the class door says what to write instead — world.{door}",
              "__name__" not in said and "name='Fatah'" in said and "Thing" in said, said[:200])
    held = doors.run('p = Person.new(full_name="Ada")\nworld.identify(p)', "doors")
    check("and something already held is told to answer for itself",
          "__name__" not in str(held["error"] or "") and "it.describe" in str(held["error"] or ""),
          str(held["error"])[:200])
    check("while the class itself still goes through",
          "Ada" in (doors.run('print(world.identify(Person, full_name="Ada"))', "doors")["output"] or ""))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all runtime tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
