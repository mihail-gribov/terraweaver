"""Every line of code the world shows a host has to run in the world it shows it to.

A guide goes stale silently. Twice in one day this world told a host that an unknown word would
make a type for it, after it had stopped doing that — and both times the host did as it was
told and the facts went somewhere else. Words cannot be checked by reading them; the examples
can be checked by running them.

Run: .venv/bin/python tests/test_the_guide_runs.py
"""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import authoring, describe, ontology
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# A line the guide shows as something to type. Anything with a comment marker, a placeholder or
# an ellipsis is prose about code rather than code, and is not run.
_CODE = re.compile(r"^\s{4,}([a-zA-Z_][\w.]*\s*=\s*)?[a-zA-Z_][\w.]*\([^)]*\)?\s*$")
_NOT_CODE = ("…", "...", "<", "#", "|", "**", "=None", "=False", "=True")
# A signature is not an example: `Class.all(limit=50)` and `entity.describe(text, …)` name a
# shape, and the names in them stand for whatever the host has. Only lines that name something
# real are run.
_A_SHAPE = ("Class.", "entity.", "q.", "rel.", "relation.", "needs.", "text", "attrs",
            "relate(",      # shown bare, as `a.relate(b, …)` with the receiver left to the host
            )


_IN_TICKS = re.compile(r"`([a-zA-Z_][\w.]*\([^`]*\))`")


def lines_of(text: str) -> list[str]:
    """Every line the guide offers as something to type — indented, or quoted in the prose."""
    got = []
    candidates = [line.strip() for line in text.splitlines() if _CODE.match(line)]
    candidates += [hit.group(1) for hit in _IN_TICKS.finditer(text)]
    for said in candidates:
        if any(mark in said for mark in _NOT_CODE) or said.startswith(_A_SHAPE):
            continue
        if said.count("(") != said.count(")"):
            continue
        got.append(said)
    return got


def main() -> int:
    from terraweaver.ontology import load_specs

    here = Path(__file__).resolve().parent.parent / "ontology" / "core"
    specs = load_specs(here)
    shown = {
        "HOST_GUIDE": describe.HOST_GUIDE,
        "COMMON_MEMBERS": describe.COMMON_MEMBERS,
        "catalogue": describe.catalogue(specs),
        "describe_for_prompt": describe.describe_for_prompt(specs),
    }
    try:
        from experiments.base_run import PRIMER, RECORD
        shown["PRIMER"] = PRIMER
        shown["RECORD"] = RECORD
    except Exception:  # noqa: BLE001 - the experiment is not part of the world
        pass

    work = Path(tempfile.mkdtemp(prefix="tw-guide-"))
    rt = WorldRuntime(str(work / "w.db"), fixture="job_search", rebuild=True)
    authoring.install(rt.world, work / "grown")
    rt.start_task("k", "run the lines this world shows a host, as a host would", "recording")
    # What the examples talk about, bound so a line about `anna` has an `anna`.
    rt.run('anna = Person.new(full_name="Anna Reid")\n'
           'london = Thing.ensure(name="London", nature="place")\n'
           'b = Thing.ensure(name="B Two", nature="object")\n'
           'a = anna\nx = london\ny = b\nentity = anna\n'
           'kevin = Person.new(full_name="Kevin Chen")\n'
           'darren = Person.new(full_name="Darren Liu")\n'
           'b04 = Organization.new(name="B04")\ncompany = Organization.new(name="Company")\n'
           'michael = world.owner\nnina = Person.new(full_name="Nina Patel")\n'
           'greg = Person.new(full_name="Greg Hunt")\nmaria = Person.new(full_name="Maria Vos")\n'
           'cloudnine = Organization.new(name="CloudNine")\n'
           'dataworks = Organization.new(name="DataWorks Two")\n'
           'thing = Thing.ensure(name="pesapallo", nature="abstraction")\n'
           'born = anna.relate(london, "kin", label="mother")\n'
           'linda = Person.new(full_name="Linda Zhao")\n'
           # The primer's own cast, bound the way the primer's first lines bind it: its
           # examples are written for a host that has already settled who it is talking about,
           # so they are checked in that context and not in an empty one.
           'paris = Thing.identify(name="Paris")[0]\n'
           'france = Thing.identify(name="France")[0]\n'
           'acme = Organization.identify(name="Acme")[0]\n'
           'kyd = Person.identify(full_name="Thomas Kyd")[0]\n'
           'boris = Person.identify(full_name="Boris Weber")[0]', "k")

    total = broke = 0
    for where, text in shown.items():
        for line in lines_of(text):
            if line.startswith(("print(", "world.pin(", "world.unpin(", "reset_session",
                                "finish_task", "start_task")):
                continue
            total += 1
            got = rt.run(line, "k")
            if not got["ok"]:
                why = (got.get("error") or "").splitlines()[-1][:96]
                # A line that raises because the world refuses what it is for is fine; a line
                # that raises because the world no longer has what it names is not.
                if any(w in why for w in ("AttributeError", "NameError", "TypeError",
                                          "no relation type", "is not a class")):
                    broke += 1
                    check(f"{where}: {line[:56]}", False, why)
    check(f"every line the world shows runs in it ({total} lines tried)", broke == 0,
          f"{broke} of {total} named something the world no longer has")

    print("\n" + (f"{len(failures)} failed: " + ", ".join(f[:40] for f in failures) if failures
                  else "all guide lines ran"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
