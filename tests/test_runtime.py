"""Tests for the host runtime: runs, rollbacks and what survives between them.

Run: .venv/bin/python tests/test_runtime.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

    # --- a run that fails leaves nothing behind, even objects it created ---
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.run('i = Idea.new(title="Leftover", content="c")\nraise RuntimeError("boom")', "host")
    rt.run('x = 1', "host")
    left = rt.run('print(len([i for i in Idea.all(limit=None) if i.title == "Leftover"]))', "check")
    check("an object from a failed run isn't saved by a later one", left["output"].strip() == "0", left["output"])

    # --- the export is plain JSON, dates included ---
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.run('Person.get(email="ada@example.com").comment("met at a conference", when=date(2026, 9, 1))', "host")
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
    check("the rollback names what was discarded", "Mark Stone" in shown, shown)
    check("and says the whole block has to be sent again", "send the whole block again" in shown, shown)
    gone = rt.run('print(len([p for p in Person.all(limit=None) if p.full_name == "Mark Stone"]))', "host")
    check("nothing from it was kept", gone["output"].strip() == "0", gone["output"])

    # --- a relation's own attribute may be called kind ---
    ok = rt.run('mark = Person.new(full_name="Mark Stone")\n'
                'm = mark.relate(Organization.get(name="FinEdge"), "membership", kind="employment")\n'
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
                    'rel.comment("rent is $2,100 a month", permanent=True)\n'
                    'print(rel)', "host")
    check("printing an entity shows it carries remarks", "1 remark" in marked["output"], marked["output"])

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all runtime tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
