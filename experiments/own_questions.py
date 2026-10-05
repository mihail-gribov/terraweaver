"""Questions of our own, one per fact a slice of the facts owes, for `benchmarks/reask.py --own`.

    .venv/bin/python experiments/own_questions.py --upto 125 > var/own125.json

The benchmark's hundred questions are spread over all 455 facts, so a check that writes the first
125 can be asked twelve of them and learns almost nothing about answering. These are asked about
exactly the facts written: every expectation among the first `--upto` that still stands after all
455 — nothing later replaces it — so the same questions are fair to a world that holds the 125 and
to one that holds everything. Each is the fact's own sentence with its last part left out, which
is where the answer sits in every FactConsolidation sentence; graded the benchmark's way, by the
gold appearing in the answer.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_expected import written_down  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))
import factconsolidation as fc  # noqa: E402


def corrections(upto: int) -> list[dict]:
    """A question for every correction among the first `upto` facts, asking for the latest telling.

    What the benchmark is about: of the 455 facts, 159 sentences are told again with another answer.
    A sentence is its words without the answer; grouped that way, a correction is the same words
    with a different end. Fair to a world holding all 455 as well, so a correction made after
    `upto` leaves the question out.
    """
    import collections

    frames = collections.defaultdict(list)
    for one in written_down(None):
        said = one["said"].rstrip(" .")
        gold = next((end for end in (one["object"], one["subject"])
                     if said.lower().endswith(str(end).lower())), None)
        if gold:
            frames[said[: len(said) - len(gold)]].append((one["fact"], gold))
    out = []
    for start, tellings in frames.items():
        inside = sorted(t for t in tellings if t[0] <= upto)
        if len({g.lower() for _, g in inside}) < 2:
            continue
        number, last = inside[-1]
        if any(n > upto and g.lower() != last.lower() for n, g in tellings):
            continue
        out.append({"id": f"fix_{number}", "fact": number,
                    "told": [n for n, _ in inside],
                    "question": f'Complete this from what is recorded, as it stands now: "{start}___."',
                    "gold": [last]})
    return sorted(out, key=lambda one: one["fact"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upto", type=int, default=125)
    parser.add_argument("--corrections", action="store_true",
                        help="only what was corrected: a sentence told twice or more among the "
                             "first --upto with different answers, asked for the last of them")
    args = parser.parse_args()
    if args.corrections:
        json.dump(corrections(args.upto), sys.stdout, indent=1, ensure_ascii=False)
        return 0

    facts = fc.load("sh", "6k").facts
    out = []
    for one in written_down(None):
        if one["fact"] > args.upto or one.get("superseded"):
            continue
        said = one["said"].rstrip(" .")
        gold = next((end for end in (one["object"], one["subject"])
                     if said.lower().endswith(str(end).lower())), None)
        if gold is None:
            continue
        start = said[: len(said) - len(gold)]
        # Replaced later, by the sentence and not by the expectation's key: "The chairperson of
        # Fatah is Mahmoud Abbas" is keyed on the chairperson, so "… is Moshe Kahlon" at fact 233
        # was not seen to replace it, and 17 of 64 questions asked for an answer the slice had
        # since corrected (measured 2026-10-04).
        if any(n > one["fact"] and later.startswith(start) and not later.rstrip(" .").endswith(gold)
               for n, later in enumerate(facts, 1)):
            continue
        blank = start + "___."
        out.append({"id": f"own_{one['fact']}", "fact": one["fact"],
                    "question": f'Complete this from what is recorded: "{blank}"',
                    "gold": [gold]})
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stderr, end=f"{len(out)} questions\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
