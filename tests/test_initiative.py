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

from terraweaver import open_world  # noqa: E402

from terraweaver import authoring, initiative
from terraweaver.runtime import WorldRuntime

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def world_with_authoring():
    work = Path(tempfile.mkdtemp(prefix="tw-init-"))
    rt = open_world(str(work / "w.db"))
    authoring.install(rt.world, work / "grown")
    rt.start_task("k", "record where people were born and where they worked", "recording")
    return rt


def landed_in(rt, word: str) -> str:
    """Where a word with no type of its own lands, at the layer that decides it.

    Not through `p.relate(x, word)` any more: a word this world has no type for is words the user
    said, whatever its shape, and it goes in as a link carrying them for the reading to type at
    the close. So the host never sends a bare word here, and what these switches govern is the
    layer underneath — the one the reading itself calls when it has a word and needs a type.
    """
    from terraweaver import relations

    p = rt.world.classes["Person"].new(full_name=f"P {word}")
    x = rt.world.classes["Thing"].new(name=f"X {word}")
    try:
        return type(relations.relate(rt.world, p, x, word, {}, {})).__name__
    except ValueError:
        return "refused"


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
    from terraweaver import relations as _relations

    p = rt.world.classes["Person"].new(full_name="Q")
    y = rt.world.classes["Thing"].new(name="Y")
    said = ""
    try:
        _relations.relate(rt.world, p, y, "collects_stamps_for", {}, {})
    except ValueError as refused_with:
        said = str(refused_with)
    check("and the refusal dictates the define_relation to write",
          'world.define_relation("collects_stamps_for"' in said, said[:160])

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
