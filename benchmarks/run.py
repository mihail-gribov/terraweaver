"""Run a public benchmark against the world, and against a baseline with the same host.

    benchmarks/fetch.sh oracle
    .venv/bin/python benchmarks/run.py --count 12                  # world, Haiku, 12 questions
    .venv/bin/python benchmarks/run.py --count 12 --mode baseline  # the same, without the world
    .venv/bin/python benchmarks/run.py --count 6 --repeat 3        # pass^k instead of one draw

One question is one world. The sessions of its history are given to the host in the order they
happened, one turn each, exactly as a person would say them over weeks; then the question is
asked in a fresh session, so nothing is answered out of the conversation that is still in
context. That is the whole point of the exercise: the answer has to come out of what was
written down, not out of what was said a moment ago.

What gets reported is what the field's own catalogues say a score needs — the dataset and its
slice, the host model, the judge, the embedder, the commit — because a number without its
configuration is noise. Costs and turns are reported too; they are the part a leaderboard hides.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import host as hosting
import longmemeval
from judge import judge

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"

RECORD = """\
It is {when}. Here is a conversation we had. Record in my world whatever it says about me and \
my life — people, places, organisations, events, projects, preferences, plans — as of that date. \
Don't answer anything, don't summarise back to me: just record it, and stop.

{text}"""

ANSWER = """\
Today is {when}. Answer this question from what you have recorded about me, and nothing else: \
{question}

Answer in one or two sentences. If what you have recorded does not answer it, say that you \
don't know rather than guessing."""


def one(instance, mode: str, model: str, port: int, out_dir: Path, judge_model: str) -> dict:
    """One question end to end: an empty world, its history written in, then the question."""
    work = Path(tempfile.mkdtemp(prefix=f"tw-bench-{instance.id}-"))
    log = out_dir / f"{instance.id}.{mode}.jsonl"
    server = totals = None
    try:
        totals = {"turns": 0, "cost": 0.0, "seconds": 0.0}
        if mode == "world":
            server = hosting.start_server(work / "world.db", port)
        agent = (hosting.World if mode == "world" else hosting.Baseline)(work, instance.id, port)

        for session in instance.sessions:
            outcome = hosting.ask(agent, RECORD.format(when=session.when, text=session.as_text()),
                                  agent.conversation(), None, log, model)
            for key in totals:
                totals[key] += outcome[key]

        outcome = hosting.ask(agent, ANSWER.format(when=instance.asked_on, question=instance.question),
                              agent.conversation(), None, log, model)
        for key in totals:
            totals[key] += outcome[key]
        answer = outcome["text"]

        verdict = judge(instance, answer, model=judge_model)
        (out_dir / f"{instance.id}.{mode}.answer.txt").write_text(
            f"Q: {instance.question}\nGold: {instance.answer}\n\n{answer}\n\n-- {verdict}\n")
        return {"id": instance.id, "kind": instance.kind, "mode": mode,
                "correct": verdict["correct"], "how": verdict["how"], "answer": answer[:400],
                **{k: round(v, 2) for k, v in totals.items()}}
    except Exception as trouble:  # one question failing is data, not a reason to lose the run
        return {"id": instance.id, "kind": instance.kind, "mode": mode, "correct": False,
                "how": "error", "answer": f"{type(trouble).__name__}: {trouble}",
                **(totals or {})}
    finally:
        if server:
            hosting.stop(server)


def pass_hat_k(per_question: list[list[bool]], k: int) -> float:
    """tau-bench's pass^k: for c successes in n attempts, the chance k drawn all succeeded."""
    shares = []
    for got in per_question:
        n, c = len(got), sum(got)
        if n >= k:
            shares.append(comb(c, k) / comb(n, k) if c >= k else 0.0)
    return sum(shares) / len(shares) if shares else 0.0


def commit() -> str:
    got = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return got.stdout.strip() or "unknown"


def embedder_name() -> str:
    try:
        sys.path.insert(0, str(ROOT))
        from terraweaver.meaning import embedder
        return embedder().name
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bench", default="oracle", choices=["oracle", "s", "m"],
                        help="which LongMemEval file (oracle = evidence sessions only)")
    parser.add_argument("--mode", default="world", choices=["world", "baseline"])
    parser.add_argument("--model", default="haiku", help="the host's model")
    parser.add_argument("--judge", default="haiku", help="the model that grades the answers")
    parser.add_argument("--count", type=int, default=12, help="how many questions (stratified)")
    parser.add_argument("--kinds", default="", help="comma-separated question types to keep")
    parser.add_argument("--repeat", type=int, default=1, help="attempts per question, for pass^k")
    parser.add_argument("--jobs", type=int, default=3, help="questions in flight at once")
    parser.add_argument("--port", type=int, default=7030, help="first port; one per job")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    instances = longmemeval.slice_of(longmemeval.load(args.bench), args.count,
                                     [k for k in args.kinds.split(",") if k] or None, args.seed)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-longmemeval-{args.bench}-{args.mode}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"benchmark": f"longmemeval-{args.bench}", "questions": len(instances),
              "slice": {"count": args.count, "kinds": args.kinds or "all", "seed": args.seed},
              "mode": args.mode, "host_model": args.model, "judge_model": args.judge,
              "embedder": embedder_name(), "repeat": args.repeat, "commit": commit(),
              "self_reported": True, "started": stamp}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config, indent=2))

    work = [(instance, attempt) for attempt in range(args.repeat) for instance in instances]
    results, lock, started = [], threading.Lock(), time.monotonic()

    def worker(slot: int):
        while True:
            with lock:
                if not work:
                    return
                instance, attempt = work.pop(0)
            got = one(instance, args.mode, args.model, args.port + slot, out_dir, args.judge)
            got["attempt"] = attempt
            with lock:
                results.append(got)
                mark = "ok " if got["correct"] else "   "
                print(f"{mark} {got['id']:<28} {got['kind']:<26} "
                      f"{got.get('turns', 0):>3} turns  ${got.get('cost', 0):.2f}  {got['how']}")

    threads = [threading.Thread(target=worker, args=(slot,)) for slot in range(args.jobs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    by_question: dict[str, list[bool]] = {}
    for got in results:
        by_question.setdefault(got["id"], []).append(got["correct"])
    by_kind: dict[str, list[bool]] = {}
    for got in results:
        by_kind.setdefault(got["kind"], []).append(got["correct"])

    summary = {
        "accuracy": round(sum(r["correct"] for r in results) / max(1, len(results)), 3),
        "by_kind": {kind: f"{sum(got)}/{len(got)}" for kind, got in sorted(by_kind.items())},
        "pass^1": round(pass_hat_k(list(by_question.values()), 1), 3),
        "errors": sum(1 for r in results if r["how"] == "error"),
        "cost_usd": round(sum(r.get("cost", 0) for r in results), 2),
        "turns": sum(r.get("turns", 0) for r in results),
        "minutes": round((time.monotonic() - started) / 60, 1),
    }
    if args.repeat > 1:
        summary[f"pass^{args.repeat}"] = round(pass_hat_k(list(by_question.values()), args.repeat), 3)
        summary["unsteady"] = sum(1 for got in by_question.values() if 0 < sum(got) < len(got))
    (out_dir / "results.json").write_text(json.dumps({"config": config, "summary": summary,
                                                      "runs": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
