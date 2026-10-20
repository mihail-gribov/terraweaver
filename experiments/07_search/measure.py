"""Recall of each search channel, alone and fused, on a proto run's journal — no model calls.

    .venv/bin/python experiments/07_search/measure.py experiments/results/05_proto_code/<stamp>

For FactConsolidation (sh/6k, 100 questions) a question is found when any of the first k
entries carries a gold answer. The structure alone found all 100 in 3.6 texts on average; the
question here is what words and meaning add, and what fusing costs, at k = 3, 5, 10, 20.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "benchmarks")]

import factconsolidation as fc  # noqa: E402
from baseline import server as base  # noqa: E402
from proto import server  # noqa: E402
from proto.model import Structure  # noqa: E402
from proto.search import Search  # noqa: E402

KS = (3, 5, 10, 20)
SETS = [("structure",), ("words",), ("meaning",), ("words", "meaning"), ("structure", "words", "meaning")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--questions", type=int, default=100)
    args = parser.parse_args()

    base.facts = args.run / "facts.md"
    structure = Structure(args.run / "structure.jsonl", base._keep, server.held)
    held = {n: text for n, _, text in base._entries(base._memory())}
    search = Search(structure, lambda: held, args.run / "vectors.jsonl")
    questions = fc.load("sh", "6k").questions[:args.questions]

    rows, misses = {}, {}
    for channels in SETS:
        found = {k: 0 for k in KS}
        for q in questions:
            numbers = search.find(q.text, limit=max(KS), channels=channels)
            for k in KS:
                if any(fc.correct(held[n], q.gold) for n in numbers[:k]):
                    found[k] += 1
                elif k == 5:
                    misses.setdefault("+".join(channels), []).append(q.text)
        rows["+".join(channels)] = found
        print(f"{'+'.join(channels):26} " + "  ".join(f"@{k} {found[k]:3}" for k in KS), flush=True)
    for name, missed in misses.items():
        print(f"\nmissed @5 by {name}: {len(missed)}", *missed[:5], sep="\n  ")
    (args.run / "search_recall.json").write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
