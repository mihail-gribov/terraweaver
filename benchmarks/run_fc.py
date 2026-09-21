"""Run MemoryAgentBench's Conflict Resolution (FactConsolidation) against the world.

    benchmarks/fetch.sh mab
    .venv/bin/python benchmarks/run_fc.py --hops sh --questions 20
    .venv/bin/python benchmarks/run_fc.py --hops mh --questions 20 --mode baseline

Unlike LongMemEval, one world serves the whole variant: the benchmark's own design is "inject
once, query many", and it is the right shape here anyway — 455 facts are one person's world,
and a hundred questions are a hundred readings of it. The facts go in batches, each batch a day
later than the last, so that "a larger serial is newer" becomes "this was said later", which is
what the world already understands.

No judge: the gold answer is a list of strings and the match is a normalised substring. Every
system in the published table is graded the same way, which is why this is the number worth
having.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc
import host as hosting

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"

RECORD = """\
It is {when}. Here are facts I am telling you, in the order I learned them. Record all of them.

If one of them says something different from what is already recorded about the same thing — the \
same person, the same organisation, the same place — then what I am telling you now is what \
holds, and the earlier one stopped holding today. Keep both if you can; what matters is that \
asking later gives today's answer.

{facts}"""

ASK = """\
Today is {when}. {question}

Answer from what is recorded, with the value and nothing else. If a thing was recorded more \
than once over time, give the one that holds now, not the first one."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hops", default="sh", choices=["sh", "mh"])
    parser.add_argument("--context", default="6k", choices=["6k", "32k", "64k", "262k"])
    parser.add_argument("--mode", default="world", choices=["world", "baseline"])
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--chunk", type=int, default=25, help="facts per recording turn")
    parser.add_argument("--port", type=int, default=7050)
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    questions = variant.questions[:args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-{variant.name}-{args.mode}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"benchmark": variant.name, "hops": variant.hops, "facts": len(variant.facts),
              "questions": len(questions), "chunk": args.chunk, "mode": args.mode,
              "host_model": args.model, "judge": "string match, no model",
              "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True).stdout.strip(),
              "self_reported": True, "started": stamp}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config, indent=2))

    work = Path(tempfile.mkdtemp(prefix=f"tw-fc-{args.hops}-"))
    log = out_dir / "host.jsonl"
    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    try:
        if args.mode == "world":
            server = hosting.start_server(work / "world.db", args.port)
        agent = (hosting.World if args.mode == "world" else hosting.Baseline)(
            work, variant.name, args.port)

        last_day = None
        for day, facts in variant.batches(args.chunk):
            last_day = day
            listed = "\n".join(f"- {fact}" for fact in facts)
            got = hosting.ask(agent, RECORD.format(when=day.isoformat(), facts=listed),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            print(f"  recorded {day} ({len(facts)} facts)  {got['turns']} turns  "
                  f"${spent['cost']:.2f} so far")

        asked_on = (last_day + timedelta(days=1)).isoformat()
        results = []
        for number, question in enumerate(questions, 1):
            got = hosting.ask(agent, ASK.format(when=asked_on, question=question.text),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            right = fc.correct(got["text"], question.gold)
            results.append({"id": question.id, "question": question.text, "gold": question.gold,
                            "answer": got["text"][:300], "correct": right,
                            "turns": got["turns"], "cost": round(got["cost"], 3)})
            print(f"{'ok ' if right else '   '} {number:>3}/{len(questions)} {question.gold} "
                  f"<- {got['text'][:80].replace(chr(10), ' ')}")
    finally:
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)

    summary = {"accuracy": round(sum(r["correct"] for r in results) / max(1, len(results)), 3),
               "questions": len(results), "cost_usd": round(spent["cost"], 2),
               "turns": spent["turns"], "minutes": round((time.monotonic() - started) / 60, 1)}
    (out_dir / "results.json").write_text(json.dumps(
        {"config": config, "summary": summary, "runs": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
