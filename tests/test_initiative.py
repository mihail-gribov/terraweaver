"""Tests for what the world does on its own — off by default, and what each switch changes.

The switches exist because each of these, on real material, turned a fact into a different fact
while every count said the run was clean. Kept behind a flag rather than deleted so the failure
can be reproduced on demand, which is what these tests do.

Run: .venv/bin/python tests/test_initiative.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import authoring, initiative
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def world_with_authoring():
    work = Path(tempfile.mkdtemp(prefix="tw-init-"))
    rt = WorldRuntime(str(work / "w.db"), fixture="job_search", rebuild=True)
    authoring.install(rt.world, work / "grown")
    rt.start_task("k", "record where people were born and where they worked", "recording")
    return rt


def landed_in(rt, word: str) -> str:
    result = rt.run(f'p = Person.new(full_name="P {word}")\nx = Thing.ensure(name="X {word}")\n'
                    f'print(type(p.relate(x, "{word}")).__name__)', "k")
    return (result["output"] or "").strip() or "refused"


def main() -> int:
    check("every switch is off in the file as committed",
          not any([initiative.MAKES_TYPES, initiative.REROUTES_BY_LABEL, initiative.LEARNS_NAMES,
                   initiative.MERGES_MEANING, initiative.TAKES_NEAR_WORD]))

    # --- a near word is not the word that was said ---
    # "worked_in_city" scores 0.769 against "born_in_city" on a shared "_in_city" that carries
    # no meaning at all. A recorder wrote it correctly four times and the world rewrote it four
    # times; nobody could see it in the counts.
    for flag, expected, what in ((False, "refused", "is refused so the agent defines it"),
                                 (True, "BornInCity", "is read as the nearest word")):
        initiative.TAKES_NEAR_WORD = flag
        rt = world_with_authoring()
        rt.run('world.define_relation("born_in_city", "where somebody was born",\n'
               '    nature="related_to", cardinality="many-to-one")', "k")
        got = landed_in(rt, "worked_in_city")
        check(f"TAKES_NEAR_WORD={flag}: an unknown word {what}", got == expected, got)
    initiative.TAKES_NEAR_WORD = False

    # --- an unknown word makes a type, or does not ---
    rt = world_with_authoring()
    refusal = landed_in(rt, "collects_stamps_for")
    check("MAKES_TYPES off: an unknown word is refused", refusal == "refused", refusal)
    said = rt.run('p = Person.new(full_name="Q")\nx = Thing.ensure(name="Y")\n'
                  'p.relate(x, "collects_stamps_for")', "k")
    check("and the refusal dictates the define_relation to write",
          "world.define_relation(\"collects_stamps_for\"" in str(said.get("error")),
          str(said.get("error"))[:160])

    initiative.MAKES_TYPES = True
    rt = world_with_authoring()
    made = landed_in(rt, "collects_stamps_for")
    check("MAKES_TYPES on: the world makes one", made == "CollectsStampsFor", made)
    initiative.MAKES_TYPES = False

    print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
                  else "all initiative tests passed"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
