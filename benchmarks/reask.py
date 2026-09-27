"""Ask an existing world the benchmark's questions again, without writing it a second time.

    .venv/bin/python benchmarks/reask.py --db /tmp/tw-blank-x/world.db \
        --specs /tmp/tw-blank-x/grown --questions 20

Recording 455 facts costs most of an hour; the questions cost a minute. So when what changed is
the *structure* — a restructuring pass, a new relation type, a repair — the honest measurement is
to take the world as it stands and ask it the same twenty questions. Before and after, one
variable, no re-ingestion in between to muddy it.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc
import host as hosting

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"

ASK = """\
Today is {when}. {question}

Answer from what is recorded, with the value and nothing else. If a thing was recorded more than \
once over time, give the one that holds now, not the first one."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True)
    parser.add_argument("--specs", default=None, help="the world's own class specs, if it built them")
    parser.add_argument("--hops", default="sh")
    parser.add_argument("--context", default="6k")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--port", type=int, default=7070)
    parser.add_argument("--label", default="reask")
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    questions = variant.questions[:args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-{args.label}-{variant.name}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="tw-reask-"))
    log = out_dir / "host.jsonl"
    server = subprocess.Popen(
        [sys.executable, "-m", "terraweaver.server", "--db", args.db, "--port", str(args.port),
         *(["--specs", args.specs] if args.specs else [])],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import urllib.request
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{args.port}/health", timeout=1)
            break
        except OSError:
            time.sleep(0.5)

    agent = hosting.World(work, args.label, args.port)
    results, spent = [], {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    try:
        for number, question in enumerate(questions, 1):
            got = hosting.ask(agent, ASK.format(when="2020-01-20", question=question.text),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            right = fc.correct(got["text"], question.gold)
            results.append({"id": question.id, "question": question.text, "gold": question.gold,
                            "answer": got["text"][:300], "correct": right})
            print(f"{'ok ' if right else '   '} {number:>3}/{len(questions)} {question.gold} "
                  f"<- {got['text'][:70].replace(chr(10), ' ')}", flush=True)
    finally:
        hosting.stop(server)
        hosting.forget_folder_memory(agent.cwd)

    summary = {"accuracy": round(sum(r["correct"] for r in results) / max(1, len(results)), 3),
               "questions": len(results), "world": args.db, "label": args.label,
               "cost_usd": round(spent["cost"], 2), "turns": spent["turns"],
               "minutes": round((time.monotonic() - started) / 60, 1)}
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "runs": results}, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
