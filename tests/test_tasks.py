"""Tests for tasks: the one boundary the world can see.

Run: .venv/bin/python tests/test_tasks.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import initiative
from terraweaver.runtime import WorldRuntime

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
    rt = WorldRuntime(":memory:", fixture="job_search")
    key = "host"
    # The doubts this checks are the ones the world raises when it invents a type from a word
    # it did not have, which it only does when told it may.
    initiative.MAKES_TYPES = True

    opened = rt.start_task(key, "record what the user said about Anna's job history", "recording")
    check("a task opens and says what it is", "record what the user said" in opened, opened[:80])
    check("and a vague statement is refused",
          refused(lambda: rt.start_task(key, "facts", "recording")) is not None)
    check("and so is a mode that is neither",
          refused(lambda: rt.start_task(key, "record the job history in full", "guessing")) is not None)

    # The world answers a recording; leaving the answer unwritten is what the boundary catches.
    result = rt.run('anna = Person.new(full_name="Anna Reid")\n'
                    'acme = Organization.new(name="Acme")\n'
                    'anna.relate(acme, "employed_by")', key)
    check("the world says what it assumed", bool(result.get("hints")), str(result.get("hints"))[:120])
    check("and raises it as a question that outlives the run", bool(result.get("questions")))

    # A name has to say how long it is kept: the world has no way to tell and won't pick.
    unsaid = rt.run('world.pin("acme", acme, "their employer")', key)
    check("pinning without saying how long is refused",
          "keep=False" in str(unsaid.get("error")), str(unsaid.get("error"))[:120])
    kept = rt.run('world.pin("acme", acme, "their employer", keep=False)', key)
    check("and goes in once it is said", kept["ok"], str(kept.get("error"))[:120])

    # A doubt raised while recording is part of the recording. The task does not close over it:
    # a batch raises one per fact, and an agent working through the batch reads each while it is
    # already writing the next, so the check has to be somewhere it cannot be walked past.
    refusal = rt.finish_task(key)
    check("a task will not close while its doubts are undecided",
          refusal.startswith("Not closed"), refusal[:90])
    check("and the refusal says how to settle them",
          "world.undecided()" in refusal and "for_the_user" in refusal, refusal[:200])
    still = rt.run('print(len(world.undecided()))', key)
    check("the doubts are still there after a refused close", still["output"].strip() == "1",
          still["output"])
    check("and every run says how many are standing", bool(still.get("undecided")))

    settled = rt.run('q = world.undecided()[0]\nq.for_the_user("only the user knows what they meant")', key)
    check("one it cannot settle is handed to the user", settled["ok"], str(settled.get("error"))[:120])

    rt.finish_task(key)      # the read-back the close asks for first

    # A name is a handle, not an account of anything. A task does not close over things it put
    # in the world and never said a word about — that line is the only description of them the
    # world did not write itself, and so the only one it can check its own structure against.
    bare = rt.finish_task(key)
    check("a task will not close over things it never described",
          bare.startswith("Not closed") and "name and nothing else" in bare, bare[:90])
    rt.run('for one in (anna, acme):\n    one.describe("mentioned while recording the job history")\n'
           'for link in anna.relations():\n    link.describe("as the user stated it")', key)
    left = rt.finish_task(key)
    check("and then it closes", not left.startswith("Not closed"), left[:90])

    # Read from the world and not through a host's code: the task record is the world's own,
    # and an agent has neither the need for it nor the name to reach it. Offered as one more
    # class it can make, it reads as somewhere to put things.
    done = rt.world.all("Task", limit=10, history=True)[0]
    check("the task is in the world afterwards, with how it closed",
          done.mode == "recording" and done.closed_as == "for_the_user",
          f"{done.mode} {done.runs} {done.closed_as}")
    check("and with what it touched", len(done.touched or []) > 0, str(done.touched))
    check("and the agent cannot reach it: the world's ledger is the world's",
          not rt.run("print(Task)", "looking on")["ok"])

    # Giving up is allowed, and it is on the record — an agent with no way out of the check
    # would answer the doubts at random, which is worse than saying it could not do the task.
    rt.start_task(key, "record the user's address from the message", "recording")
    rt.run('p = Person.new(full_name="Nobody Atall")\np.relate(Place.new(name="Somewhere"), "squats_at")\n'
           'p.describe("somebody the message mentioned")', key)
    gave_up = rt.finish_task(key, abandon="the message never said whose address it was")
    check("a task can be abandoned, with the reason kept",
          "abandoned" in gave_up.lower() and "never said" in gave_up, gave_up[:100])
    how = [t.closed_as for t in rt.world.all("Task", limit=10, history=True)]
    check("and it is recorded as abandoned", "abandoned" in how, str(how))

    # Nothing open about what it touched is what "done" means, and it is worked out, not said.
    rt.start_task(key, "look up which organizations are already known", "answering")
    rt.run('print(len(Organization.all(limit=5)))', key)
    clean = rt.finish_task(key)
    check("a task that leaves nothing open closes done",
          "nothing was left open" in clean.lower(), clean[:100])

    # --- a fact written as a description of one thing, when it is about two ---
    # Fourteen capitals went in this way in a 455-fact run, every one of them while no type for
    # them existed yet: `tokyo.describe("the capital of Japan")` passes every check the world
    # had — the thing is described, something was said, the task closes — and leaves the fact
    # where nothing can supersede it, count it or answer with it.
    rt = WorldRuntime(":memory:", fixture="job_search")
    rt.start_task(key, "record what the user said about cities and countries", "recording")
    rt.run('tokyo = Thing.ensure(name="Tokyo", nature="place")\n'
           'japan = Thing.ensure(name="Japan", nature="place")\n'
           'japan.describe("the country Tokyo is in")\n'
           'tokyo.describe("the capital of Japan")\n'
           'print("said")', key)
    held = rt.finish_task(key)
    check("a description naming another thing with no link between them stops the close",
          held is not None and "facts about two things" in held, str(held)[:110])
    check("and it says which two", "Tokyo" in (held or "") and "Japan" in (held or ""),
          str(held)[:140])

    rt.run('world.define_relation("capital_of", "the city that is a country\'s seat of '
           'government", nature="part_of", cardinality="one-to-one")\n'
           'print("defined")', key)
    rt._bind_classes(rt.session(key))
    rt.run('Thing.get(name="Tokyo").relate(Thing.get(name="Japan"), "capital_of")\n'
           'print("linked")', key)
    closed = rt.finish_task(key)
    check("and once the link is there it closes",
          closed is None or "facts about two things" not in closed, str(closed)[:110])

    initiative.MAKES_TYPES = False
    print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures else "all task tests passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
