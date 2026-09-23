"""Every way a later telling meets an earlier one, in one place.

These behaviours were fixed one at a time over a day, and fixing one silently undid another
twice: the invented end date was removed in the morning and left the correction announcing
itself and doing nothing, which was found in the evening by reading a world rather than by any
test. They are pinned together here so that the next change to any of them has to face all of
them at once.

Run: .venv/bin/python tests/test_superseding.py
"""
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import authoring
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def world(**types):
    """A world with the types this case needs, and a task open to record into."""
    work = Path(tempfile.mkdtemp(prefix="tw-sup-"))
    rt = WorldRuntime(str(work / "w.db"), fixture="job_search", rebuild=True)
    made = authoring.install(rt.world, work / "grown")
    for kind, over_time in types.items():
        made.define_relation(kind, f"what {kind.replace('_', ' ')} means here, for the test",
                             nature="related_to", cardinality="many-to-one", over_time=over_time)
    rt.start_task("k", "record what the user said, more than once about one thing", "recording")
    return rt


def ran(rt, code):
    got = rt.run(code, "k")
    return (got["output"] or "").strip(), got


def main() -> int:
    # --- a correction: one value and no more, and no date is invented ---
    rt = world(hq_in=False)
    out, _ = ran(rt, 'org = Thing.ensure(name="Acme Corp", nature="agent")\n'
                     'org.relate(Thing.ensure(name="Dublin", nature="place"), "hq_in")\n'
                     'org.relate(Thing.ensure(name="Tallinn", nature="place"), "hq_in")\n'
                     'print([t.display_name() for t in org.related("hq_in")])\n'
                     'print([t.display_name() for t in org.related("hq_in", any_time=True)])\n'
                     'print([l.until for l in org.relations("hq_in", any_time=True)])')
    holds, ever, ends = out.splitlines() if out.count("\n") == 2 else ("", "", "")
    check("a correction leaves the later one holding", holds == "['Tallinn']", holds)
    check("and the earlier one still in the record", "Dublin" in ever and "Tallinn" in ever, ever)
    check("and invents no end date for it", ends.count("None") == 2, ends)

    # --- a handover: one at a time, and the new one's start is where the last ends ---
    rt = world(chairs=True)
    out, _ = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                     'Person.new(full_name="Yasser Arafat").relate(org, "chairs", starts=date(1969, 2, 3))\n'
                     'Person.new(full_name="Mahmoud Abbas").relate(org, "chairs", starts=date(2004, 11, 11))\n'
                     'for l in sorted(org.relations("chairs_of", any_time=True), key=lambda x: x.starts):\n'
                     '    print(f"{l.subject.display_name()} {l.starts.date()} -> {l.until.date() if l.until else None}")')
    check("a handover ends the first where the second begins",
          "Yasser Arafat 1969-02-03 -> 2004-11-11" in out, out.replace("\n", " | "))
    check("and the second one is open", "Mahmoud Abbas 2004-11-11 -> None" in out, out.replace("\n", " | "))

    # --- what the nature decides ---
    rt = world()
    _, got = ran(rt, 'a = Person.new(full_name="A One")\nb = Organization.new(name="B Two")\n'
                     'a.relate(b, "authority", label="manager")')
    check("a related_to link that changes will not be made without a start",
          not got["ok"] and "when it began is part of the fact" in str(got.get("error")),
          str(got.get("error"))[:80])
    _, got = ran(rt, 'dept = Organization.new(name="Newsroom")\ndept.relate(b, "part_of")')
    check("a part_of link needs no start", got["ok"], str(got.get("error"))[:80])

    # --- a date given earlier than the standing one is a conflict, not a handover ---
    rt = world(chairs=True)
    _, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                     'Person.new(full_name="Later").relate(org, "chairs", starts=date(2024, 1, 1))\n'
                     'Person.new(full_name="Earlier").relate(org, "chairs", starts=date(2020, 1, 1))')
    check("a start before the standing one is refused", not got["ok"], str(got.get("error"))[:70])

    # --- the same moment, taken once, is a handover and not an overlap ---
    rt = world(chairs=True)
    out, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\nt = now()\n'
                       'Person.new(full_name="First").relate(org, "chairs", starts=t)\n'
                       'Person.new(full_name="Second").relate(org, "chairs", starts=t)\n'
                       'print([p.display_name() for p in org.related("chairs_of")])')
    check("one moment passed to both hands over", out == "['Second']", out or str(got.get("error"))[:70])

    # --- the other shape: the subject changes, and the world can only count ---
    rt = world(led_by=False)
    out, got = ran(rt, 'org = Thing.ensure(name="Fatah", nature="agent")\n'
                       'Person.new(full_name="One").relate(org, "led_by")\n'
                       'Person.new(full_name="Two").relate(org, "led_by")\n'
                       'print(len(org.related("led_by_of")))')
    check("two subjects on one object both stand, since nothing said otherwise", out == "2", out)
    check("and the world asks about it once, naming the fix",
          any("one_per_object" in q for q in (got.get("questions") or [])),
          str(got.get("questions"))[:110])
    out, _ = ran(rt, 'led_by.one_per_object = True\n'
                     'Person.new(full_name="Three").relate(org, "led_by")\n'
                     'print([p.display_name() for p in org.related("led_by_of")])')
    check("and once it is said, the later one supersedes", out == "['Three']", out)

    print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
                  else "all superseding tests passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
