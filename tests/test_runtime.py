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

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all runtime tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
