"""Tests for the host runtime: runs, rollbacks and what survives between them.

Run: .venv/bin/python tests/test_runtime.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import initiative
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    # --- a settled value survives a rollback that happened between the question and the answer ---
    # Seen with a real host: the question was kept in a variable, a later run failed and was rolled
    # back, then settling applied the answer to an orphaned copy while another stale copy was saved
    # over it — the old employer came back.
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.run('dw = Organization.get(name="DataWorks")\n'
           'q = Person.ensure(full_name="Ada Lovelace", organization=dw)\n'
           'ada = Person.get(email="ada@example.com")', "host")
    failed = rt.run('ada.phone = "123"\nraise RuntimeError("the host made a mistake")', "host")
    check("the failing run is rolled back", not failed["ok"])
    settled = rt.run('world.settle(q, dw)', "host")
    check("settling afterwards goes through", settled["ok"], str(settled["error"]))
    after = rt.run('print(Person.get(email="ada@example.com").organization.name)', "check")
    check("and the settled value is what the world holds", after["output"].strip() == "DataWorks", after["output"])

    # --- a run stops where it breaks and keeps what it had already done ---
    # All-or-nothing was the rule here until the measurements turned against it: a fifth to a
    # quarter of every pool's runs ended discarded, most over a typo far from anything that
    # mattered, and the heavy work before it was re-run for nothing.
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.run('i = Idea.new(title="Leftover", content="c")\nraise RuntimeError("boom")', "host")
    left = rt.run('print(len([i for i in Idea.all(limit=None) if i.title == "Leftover"]))', "check")
    check("what a completed statement wrote is kept when a later one fails",
          left["output"].strip() == "1", left["output"])

    # --- the export is plain JSON, dates included ---
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.run('Person.get(email="ada@example.com").describe("met at a conference", when=date(2026, 9, 1))', "host")
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
    rt = WorldRuntime(":memory:", fixture="job_search")
    from terraweaver.runtime import format_result
    broken = rt.run('mark = Person.new(full_name="Mark Stone")\n'
                    'mark.relate(Organization.get(name="FinEdge"), "membership", title="analyst")\n'
                    'raise RuntimeError("later line fails")', "host")
    shown = format_result(broken)
    check("the failure says where it stopped and that what came before is kept",
          "before this one are done and kept" in shown, shown)
    kept = rt.run('print(len([p for p in Person.all(limit=None) if p.full_name == "Mark Stone"]))', "host")
    check("the person the first statement made is in the world",
          kept["output"].strip() == "1", str(kept["output"] or kept["error"]))
    still = rt.run('org = Organization.get(name="FinEdge")\n'
                   'note = "for later"\n'
                   'raise RuntimeError("stop")', "host")
    cut = rt.run('a = 1\nb = 2\nraise RuntimeError("stop")\nc = 3\nd = 4', "host")
    check("the failure names the line it broke on, with its text",
          'line 3: raise RuntimeError("stop")' in cut["error"], cut["error"])
    check("and says how much is done and how much never ran",
          "2 line(s) before it are done" in cut["error"] and "2 after it never ran" in cut["error"],
          cut["error"])

    shown_still = format_result(still)
    check("and a failed run hands the block back as it stands",
          "# --- done and kept, do not send again ---" in shown_still
          and "# !! stopped here" in shown_still, shown_still)
    check("with what never ran commented out",
          "# note = \"for later\"" in shown_still or "# raise RuntimeError" in shown_still,
          shown_still)
    undone = rt.run('print(len([p for p in Person.all(limit=None) if p.full_name == "Never Made"]))', "host")
    check("and the statement that raised left nothing of its own", undone["output"].strip() == "0",
          undone["output"])

    # --- a relation's own attribute may be called kind ---
    ok = rt.run('rita = Person.new(full_name="Rita Sandoval")\n'
                'm = rita.relate(Organization.get(name="FinEdge"), "membership", kind="employment")\n'
                'print(m.kind)', "host")
    check("relate takes kind= as the relation's attribute", ok["output"].strip() == "employment",
          str(ok["error"]) or ok["output"])

    # --- periods compare with plain dates ---
    dates = rt.run('r = Person.new(full_name="Nina Patel").relate(owner, "service", label="dentist", '
                   'starts=date(2026, 10, 1))\n'
                   'print(r.starts >= date(2026, 9, 1), r.starts == date(2026, 10, 1), r.starts < today())', "host")
    check("a period bound compares with a date instead of raising",
          dates["output"].strip() == "True True False", str(dates["error"]) or dates["output"])

    # --- a remark on an entity is visible when the entity is printed ---
    marked = rt.run('greg = Person.new(full_name="Greg Hunt")\n'
                    'rel = greg.relate(owner, "service", label="landlord")\n'
                    'rel.describe("rent is $2,100 a month", permanent=True)\n'
                    'print(rel)', "host")
    check("printing an entity shows it carries remarks", "1 remark" in marked["output"], marked["output"])

    # --- the answer to "which one?" arrives as what the host does next ---
    # Remembering which entity a name meant is the world acting on its own, so it is off by
    # default and this block turns it on for what it checks.
    initiative.LEARNS_NAMES = True
    choice = WorldRuntime(str(Path(tempfile.mkdtemp()) / "choice.db"), fixture="job_search", rebuild=True)
    choice.run('annie = Person.find(full_name="Annie")', "one")
    told = choice.run('anna = Person.get(full_name="Anna Sullivan"); print(anna.full_name)', "one")
    check("working with one of the candidates settles the name",
          any("Anna Sullivan" in line for line in told["assumed"]), str(told["assumed"]))
    later = choice.run('again = Person.find(full_name="Annie"); print(again.matches[0].full_name)', "two")
    check("and a later conversation does not ask again",
          "Anna Sullivan" in (later["output"] or ""), str(later["output"] or later["error"]))

    waiting = WorldRuntime(str(Path(tempfile.mkdtemp()) / "waiting.db"), fixture="job_search", rebuild=True)
    waiting.run('barb = Person.new(full_name="Barb Liskov")\n'
                'barb.tag("conference")\n'
                'kept = Person.new(full_name="Zoya Ren", email="zoya@x.org")', "one")
    check("a question in a batch does not take the rest of it down",
          "Zoya" in (waiting.run('print(Person.get(email="zoya@x.org").full_name)', "two")["output"] or ""))
    nagged = waiting.run('print("something else")', "one")
    check("and what is waiting on the answer is said again every run",
          any("waiting on the answer" in q for q in nagged["questions"]), str(nagged["questions"]))

    listing = WorldRuntime(str(Path(tempfile.mkdtemp()) / "listing.db"), fixture="job_search", rebuild=True)
    listing.run('needs = Person.ensure(full_name="Annie")', "one")
    showed = listing.run('annies = Person.find(full_name="Annie")\n'
                         'for annie in annies.candidates:\n    print(annie.full_name)', "one")
    check("listing the candidates for the user teaches nothing, even a run later",
          showed["assumed"] == [], str(showed["assumed"]))
    picked = listing.run('chosen = Person.get(full_name="Anna Sullivan")\nprint(chosen.job_title)', "one")
    check("and picking one of them is still the answer, said once",
          len([a for a in picked["assumed"] if "Anna Sullivan" in a]) == 1, str(picked["assumed"]))

    loop = WorldRuntime(str(Path(tempfile.mkdtemp()) / "loop.db"), fixture="job_search", rebuild=True)
    asking = loop.run('annie = Person.find(full_name="Annie")\n'
                      'for p in annie.similar[:3]:\n    print(p.full_name)', "one")
    check("printing the candidates settles nothing, whatever a loop leaves bound",
          asking["assumed"] == [], str(asking["assumed"]))
    over_similar = loop.run('for person in annie.similar:\n    print(person.full_name)', "one")
    check("and neither does looping over them a run later",
          over_similar["assumed"] == [], str(over_similar["assumed"]))
    answering = loop.run('anna = Person.get(full_name="Anna Sullivan")\nprint(anna.job_title)', "one")
    check("and the run after it does settle it",
          any("Anna Sullivan" in line for line in answering["assumed"]), str(answering["assumed"]))

    kept = WorldRuntime(str(Path(tempfile.mkdtemp()) / "kept.db"), fixture="job_search", rebuild=True)
    kept.run('annie = Person.find(full_name="Annie")', "one")
    by_find = kept.run('anna = Person.find(full_name="Anna Sullivan")\nprint(anna.matches[0].job_title)', "one")
    check("keeping one of them from a find settles it too",
          any("Anna Sullivan" in line for line in by_find["assumed"]), str(by_find["assumed"]))

    two = WorldRuntime(str(Path(tempfile.mkdtemp()) / "two.db"), fixture="job_search", rebuild=True)
    two.run('annie = Person.find(full_name="Annie")', "one")
    ambiguous = two.run('pair = [p for p in Person.all(limit=None) if "Anna" in p.full_name]\nprint(len(pair))', "one")
    check("holding both of them settles nothing", ambiguous["assumed"] == [], str(ambiguous["assumed"]))

    broke = WorldRuntime(str(Path(tempfile.mkdtemp()) / "broke.db"), fixture="job_search", rebuild=True)
    broke.run('annie = Person.find(full_name="Annie")', "one")
    failed = broke.run('anna = Person.get(full_name="Anna Sullivan")\nprint(anna.organization.full_name)', "one")
    check("a run that breaks later still leaves the answer standing",
          failed["error"] is not None and any("Anna Sullivan" in line for line in failed["assumed"]),
          str(failed["assumed"]))
    check("and the next conversation goes with it",
          "Anna Sullivan" in (broke.run('print(Person.find(full_name="Annie").matches[0].full_name)',
                                        "two")["output"] or ""))

    apart = WorldRuntime(str(Path(tempfile.mkdtemp()) / "apart.db"), fixture="job_search", rebuild=True)
    apart.run('annie = Person.find(full_name="Annie")', "one")
    unrelated = apart.run('print(Person.get(email="ada@example.com").full_name)', "one")
    check("someone who was never a candidate settles nothing", unrelated["assumed"] == [],
          str(unrelated["assumed"]))
    check("so the question is still open",
          "False" in (apart.run('print(Person.find(full_name="Annie").matched)', "two")["output"] or ""))
    initiative.LEARNS_NAMES = False

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all runtime tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
