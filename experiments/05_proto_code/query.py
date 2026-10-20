"""Ask FactConsolidation's questions of the structure a proto run left: by things, not by all.

    .venv/bin/python experiments/05_proto_code/query.py experiments/results/05_proto_code/<stamp>
    .venv/bin/python experiments/05_proto_code/query.py <run> --questions 20 --recall-only

For each question, the things it names (their names in its words, the longest first) are looked
up; what the model is shown is the texts of every entry about them, numbered as in the journal,
in the baseline's own `ask` words. Nothing else: no vectors, no model to find them. Recall is
whether any text shown carries a gold answer — checked without a model, and what a cut of the
baseline has to hold at 100. Accuracy is the model's answer, against the baseline's ~90.
"""
import argparse
import concurrent.futures
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "benchmarks")]

import factconsolidation as fc  # noqa: E402
from baseline import server as base  # noqa: E402
from proto import server  # noqa: E402
from proto.model import Structure  # noqa: E402

import importlib.util  # noqa: E402

# The run's own model call, loaded by path: `run` is also the name of benchmarks/run.py.
_spec = importlib.util.spec_from_file_location("proto_run", Path(__file__).with_name("run.py"))
_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_run)
haiku = _run.haiku

ONLY_THE_VALUE = " Answer with the value that holds now and nothing else."


def named_in(question: str, things: list[dict]) -> list[dict]:
    """The things whose names the question says, longest first, none inside a longer one."""
    said, found, taken = question.lower(), [], []
    for t in sorted(things, key=lambda t: -len(t["name"])):
        name = t["name"].lower()
        for m in re.finditer(r"(?<!\w)" + re.escape(name) + r"(?!\w)", said):
            if not any(a <= m.start() and m.end() <= b for a, b in taken):
                found.append(t)
                taken.append((m.start(), m.end()))
                break
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--hops", default="sh")
    parser.add_argument("--context", default="6k")
    parser.add_argument("--questions", type=int, default=100)
    parser.add_argument("--recall-only", action="store_true", help="no model calls")
    parser.add_argument("--parallel", type=int, default=6)
    args = parser.parse_args()

    base.facts = args.run / "facts.md"
    structure = Structure(args.run / "structure.jsonl", base._keep, server.held)
    things = [r for r in structure.records if "thing" in r]
    held = {n: text for n, _, text in base._entries(base._memory())}
    variant = fc.load(args.hops, args.context)
    questions = variant.questions[:args.questions]

    def shown(q) -> tuple[list[dict], list[int]]:
        found = named_in(q.text, things)
        numbers = sorted({n for t in found
                          for n in (int(e.split(" · ")[0][3:]) for e in structure.about(structure.thing("q", t["thing"])))})
        return found, [n for n in numbers if n in held]

    def one(q):
        found, numbers = shown(q)
        texts = [held[n] for n in numbers]
        recall = any(fc.correct(t, q.gold) for t in texts)
        row = {"id": q.id, "question": q.text, "gold": q.gold, "things": [t["name"] for t in found],
               "shown": len(texts), "recall": recall}
        if not args.recall_only:
            memory = "\n".join(f"{n}. {' '.join(held[n].split())}" for n in numbers)
            answer, _ = haiku(base.ASK.format(memory=memory or "(nothing)", question=q.text + ONLY_THE_VALUE))
            row |= {"answer": answer[:300], "correct": fc.correct(answer, q.gold)}
        return row

    with concurrent.futures.ThreadPoolExecutor(args.parallel) as pool:
        rows = list(pool.map(one, questions))

    n = len(rows)
    print(f"recall {sum(r['recall'] for r in rows)}/{n}, no thing found {sum(not r['things'] for r in rows)}, "
          f"texts shown {sum(r['shown'] for r in rows) / n:.1f} on average (the baseline shows {len(held)})")
    if not args.recall_only:
        print(f"accuracy {sum(r['correct'] for r in rows)}/{n}")
    for r in rows:
        if not r["recall"] or not r.get("correct", True):
            print(f"  {'R' if not r['recall'] else ' '}{'A' if not r.get('correct', True) else ' '} "
                  f"{r['question']}  things={r['things']} shown={r['shown']} gold={r['gold']}"
                  + (f" <- {r['answer'][:60]!r}" if "answer" in r else ""))
    out = args.run / ("recall.json" if args.recall_only else "query.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
