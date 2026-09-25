"""The same six statements, said through the doors that take words instead of types.

`run.py` replays the code an ideal host writes when it must choose the relation type itself.
This replays the same facts said the other way — two things handed over and the statement in the
words it came in — and checks the world against the same expectations. What the host wrote by
hand there, the engineer reads here, at the close, from the words.

The point of measuring it against the same table is that nothing about the expectations moves:
the same links must hold, the same ones must stop holding. Where the two runs differ is the
only thing being asked about.

    .venv/bin/python experiments/story/new_doors.py
    .venv/bin/python experiments/story/new_doors.py --old    # the same table, the old door
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from terraweaver import authoring, ontology, outside   # noqa: E402
from terraweaver.runtime import WorldRuntime           # noqa: E402

from experiments.story.steps import STEPS              # noqa: E402

CORE = ROOT / "ontology" / "core"

# Who each statement is about, in the order the statement puts them. Taken from the ideal code
# rather than read out of the words: which two things a fact is about is the one thing this
# design never recovers from text, here as anywhere else.
ABOUT = [
    ("Person", "full_name", "Thomas Kyd", "Thing", "name", "London"),
    ("Person", "full_name", "Mahmoud Abbas", "Thing", "name", "Fatah"),
    ("Person", "full_name", "Amy Winehouse", "Thing", "name", "Camden Town"),
    ("Person", "full_name", "Hines Ward", "Thing", "name", "wide receiver"),
    ("Person", "full_name", "Thomas Kyd", "Thing", "name", "Leeds"),
    ("Person", "full_name", "Hines Ward", "Thing", "name", "cornerback"),
]


def said_in_words(step: dict, about: tuple) -> str:
    """The statement as a host says it through the sentence door: two things and the words."""
    a_class, a_key, a_name, b_class, b_key, b_name = about
    return (f'a = {a_class}.identify({a_key}="{a_name}")[0]\n'
            f'b = {b_class}.identify({b_key}="{b_name}")[0]\n'
            f'a.relate(b, {step["said"]!r})')


def holding(world) -> set:
    """(kind, from, to, holds) for every link — holds meaning the world reads it back.

    Not `valid_until`, which is only half of superseding. A type that holds one at a time hands
    over: the old link is given an end. A type that holds one value full stop is *corrected*:
    the statement is superseded and the row keeps standing, because what was said was said. Both
    rows are there afterwards and only one is the answer — so the question to ask is the one
    anybody asking this world would ask, which is what it reads back.
    """
    out = set()
    for name, cls in world.classes.items():
        if not cls._spec.get("relation") or cls._spec["relation"].get("free"):
            continue
        kind = cls._spec["relation"]["kind"]
        for link in world.all(name, limit=None, history=True):
            if link.subject is None or link.object is None:
                continue
            try:
                answered = [one.display_name() for one in link.subject.related(kind)]
            except Exception:  # noqa: BLE001 - a link the world cannot read is not an answer
                answered = []
            out.add((kind, link.subject.display_name(), link.object.display_name(),
                     link.object.display_name() in answered))
    return out


def key(nebius: bool = True) -> None:
    for env in (ROOT / ".env", Path(os.path.expanduser("~/Projects/ai-safity/.env"))):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            if line.startswith("NEBIUS_API_KEY") and not os.environ.get("NEBIUS_API_KEY"):
                os.environ["NEBIUS_API_KEY"] = line.split("=", 1)[1].strip().strip('"')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", action="store_true", help="the type-first door, for comparison")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    key()

    work = Path(tempfile.mkdtemp(prefix="tw-doors-"))
    runtime = WorldRuntime(str(work / "world.db"), fixture=None, selves=True,
                          specs=ontology.base_specs(CORE))
    authoring.install(runtime.world, work / "grown")
    if not args.old:
        runtime.world.engineer = outside.Nemotron(ttl=120)

    # One task per statement, because the reading happens when a task closes: a host that says
    # six things and closes once has the engineer read all six at the end, which is how it runs,
    # but then no step can be attributed to its own statement.
    refused = []
    for number, (step, about) in enumerate(zip(STEPS, ABOUT), 1):
        code = step["code"] if args.old else said_in_words(step, about)
        runtime.start_task(f"s{number}", f"record statement {number} of the story", "recording")
        got = runtime.run(code, f"s{number}")
        if not got["ok"]:
            refused.append((number, (got["error"] or "").splitlines()[-1][:110]))
        closed = runtime.finish_task(f"s{number}")
        if args.show:
            print(f"--- {number}. {step['said']}")
            for line in (closed or "").splitlines():
                if line.strip():
                    print("   ", line[:120])

    # Checked once, at the end, against every expectation the table holds: the reading is not
    # done where the statement is said, so a step's consequence cannot be looked for there.
    after = holding(runtime.world)
    hold = {(t, a, b) for t, a, b, holds in after if holds}
    over = {(t, a, b) for t, a, b, holds in after if not holds}
    want_hold, want_over = set(), set()
    for step in STEPS:
        want_hold |= {tuple(one) for one in step.get("gained", [])}
        want_over |= {tuple(one) for one in step.get("ended", [])}
    want_hold -= want_over

    # A step's gain may be gone by the end — step 1 puts Kyd in London and step 5 corrects it —
    # so what each step is checked for is what the table says should be true *after all six*:
    # the link it gained, unless a later step ended it, and the link it ended.
    wrong = 0
    for number, step in enumerate(STEPS, 1):
        gained = {tuple(one) for one in step.get("gained", [])}
        ended = {tuple(one) for one in step.get("ended", [])}
        must_hold, must_be_over = gained - want_over, ended | (gained & want_over)
        missing = (must_hold - hold) | (must_be_over - over)
        ok = not missing
        wrong += 0 if ok else 1
        later = " (corrected later — checked as ended)" if gained & want_over else ""
        print(f"{'ok  ' if ok else 'MISS'} {number:>2}. {step['said']}{later}")
        for link in sorted(missing):
            where = "still holds" if link in hold else "not in the world at all"
            print(f"        {link[0]}: {link[1]} → {link[2]}  ({where})")
    for number, why in refused:
        print(f"     {number} was refused as it was written: {why}")

    print("\n--- every link the world holds, as it reads them back")
    for kind, a, b, holds in sorted(after):
        print(f"    {'holds' if holds else 'over '}  {kind}: {a} → {b}")
    print("--- the sentences, and what was made of them")
    from terraweaver import sentences as _s
    for row in runtime.world.store.conn.execute(
            "SELECT words, read_as FROM sentences ORDER BY id").fetchall():
        import json as _j
        said = _j.loads(row[1]) if row[1] else {}
        print(f"    {row[0][:56]:58} use={said.get('use')} "
              f"subj={said.get('subject_is')} obj={said.get('object_is')} "
              f"ill={said.get('ill_typed')} refused={str(said.get('refused'))[:40]}")

    stray = hold - want_hold
    if stray:
        print(f"\n{len(stray)} link(s) nothing asked for:")
        for link in sorted(stray)[:12]:
            print(f"        {link[0]}: {link[1]} → {link[2]}")
    print(f"\n{len(STEPS) - wrong}/{len(STEPS)} statements landed as the table says"
          f" ({'type-first door' if args.old else 'said in words'}).")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
