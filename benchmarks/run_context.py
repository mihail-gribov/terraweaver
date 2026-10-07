"""The same model with no world: every fact in the prompt, then the question. The world's effect is the difference.

    .venv/bin/python benchmarks/run_context.py --model haiku

What the world is measured against. `run_fc.py --mode world` writes the facts into a world in
batches and asks each question in a fresh session that sees nothing but the world; this gives the
same model the benchmark's own numbered list and its own rule ("a larger number is newer"), with no
tools, and asks the same 100 questions. At 6k the whole list fits in any window, which is the
regime most kind to the model alone — so a world that does not beat this at 6k has no effect there.
"""
import argparse
import concurrent.futures
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"

# MemoryAgentBench's own framing of the task: numbered facts, the newer one wins.
PROMPT = """Below is a list of facts, numbered in the order they were stated. Some facts were later \
updated: when two facts conflict, the one with the larger number is newer and is the one that holds.

{facts}

Question: {question}

Answer with the value that holds now and nothing else."""


def ask(prompt: str, model: str, where: Path) -> dict:
    started = time.monotonic()
    run = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--output-format", "json",
         "--strict-mcp-config", "--allowedTools", "",
         "--disallowedTools", "Read Write Edit Bash Glob Grep WebFetch WebSearch NotebookEdit "
                              "AskUserQuestion EnterPlanMode EnterWorktree Task Agent Skill"],
        cwd=where, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
    try:
        out = json.loads(run.stdout)
    except json.JSONDecodeError:
        return {"text": "", "cost": 0.0, "error": (run.stderr or run.stdout)[:300],
                "seconds": time.monotonic() - started}
    return {"text": out.get("result") or "", "cost": out.get("total_cost_usd") or 0.0,
            "seconds": time.monotonic() - started}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hops", default="sh")
    parser.add_argument("--context", default="6k")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--questions", type=int, default=100)
    parser.add_argument("--parallel", type=int, default=4)
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    facts = "\n".join(f"{n}. {fact}" for n, fact in enumerate(variant.facts, 1))
    questions = variant.questions[:args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-{variant.name}-context-{args.model}"
    out_dir.mkdir(parents=True)
    where = Path(tempfile.mkdtemp(prefix="tw-context-"))   # an empty folder: no memory to find

    def one(q):
        got = ask(PROMPT.format(facts=facts, question=q.text), args.model, where)
        return {"id": q.id, "question": q.text, "gold": q.gold, "answer": got["text"][:300],
                "correct": fc.correct(got["text"], q.gold), "cost": got["cost"],
                **({"error": got["error"]} if "error" in got else {})}

    with concurrent.futures.ThreadPoolExecutor(args.parallel) as pool:
        runs = list(pool.map(one, questions))
    for n, r in enumerate(runs, 1):
        print(f"{'ok ' if r['correct'] else '   '} {n:>3}/{len(runs)} {r['gold']} <- {r['answer'][:80]}")
    summary = {"accuracy": round(sum(r["correct"] for r in runs) / len(runs), 3),
               "questions": len(runs), "errors": sum("error" in r for r in runs),
               "cost_usd": round(sum(r["cost"] for r in runs), 2), "model": args.model,
               "mode": "context", "facts": len(variant.facts)}
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "runs": runs}, indent=1))
    print(json.dumps(summary, indent=2))
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
