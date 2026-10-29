"""LongMemEval through the memory's two doors, against the same model given everything.

    .venv/bin/python experiments/14_longmemeval/run.py                    # 25 questions, both modes
    .venv/bin/python experiments/14_longmemeval/run.py --count 6 --mode memory
    .venv/bin/python experiments/14_longmemeval/run.py --only gpt4_2655b836

A stratified slice of LongMemEval `oracle` (the sessions that hold the answer; benchmarks/fetch.sh),
without single-session-assistant: those ask what the assistant said, and the memory drops the
agent's messages by design (`--with-assistant` puts them back).

- **memory:** a fresh memory per question (`python -m memory.server`, `--no-world` unless `--graph`). Every turn of
  every session goes in by `/say` as the hooks would pass it — the user's and the assistant's, with
  the session's date as `now`. Then the question goes to `/ask` with `gather: false`: from what the
  memory holds only, never the web. Without `--graph`, journal and search only; with it, every entry
  is read into the graph (memory/graph.py) as it is kept, and the answer is given its topics too.
- **context:** the same model with every session in its prompt — what the memory is measured against.

In both, Nemotron Super words the final answer from what it was given, and the same judge
(`benchmarks/judge.py`, LongMemEval's rubrics, Claude Haiku) grades it. Kept per question in
experiments/results/14_longmemeval/<stamp>/: what was asked, what the memory answered, the final
answer, the verdict; the memory's own journal beside it.
"""
import argparse
import concurrent.futures
import json
import os
import queue
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import longmemeval as lme  # noqa: E402
from judge import judge  # noqa: E402

from memory.models import role  # noqa: E402

# The agent's part, the same in both modes: facts of the user's life only from what it was given;
# a suggestion its own, made for this user.
ANSWER_SYSTEM = ("You are a personal assistant answering the user's question. About the user's own life — "
                 "what they did, said, have or prefer, and when — answer only from what you are given; if it "
                 "does not say, answer that you don't know. When they ask for a suggestion or advice, give it, "
                 "made for them from what you are given about them. Be brief.")


def call(port: int, path: str, body: dict, timeout: float = 600) -> str:
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return answer.read().decode()


def answer(given: str, instance) -> str:
    prompt = f"{given}\n\nToday is {instance.asked_on}. The user asks: {instance.question}"
    return role("reader").say(ANSWER_SYSTEM, prompt, room=6000, thinking=True).strip()


GRAPH = False


def by_memory(instance, port: int, out: Path) -> dict:
    name = f"lme-{out.name}-{instance.id}"
    log = open(out / f"{instance.id}.server.log", "w")
    server = subprocess.Popen([sys.executable, "-m", "memory.server", "--name", name, "--port", str(port)]
                              + ([] if GRAPH else ["--no-world"]), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    began = time.time()
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/notes", timeout=2)
                break
            except OSError:
                time.sleep(1)
        for session in instance.sessions:
            now = session.date.isoformat(timespec="minutes")
            for turn in session.turns:
                role_of = "user" if turn["role"] == "user" else "agent"
                call(port, "/say", {"messages": [{"role": role_of, "text": turn["content"]}], "now": now})
        told = round(time.time() - began)
        asked = lme.Session(instance.asked_on, []).date.isoformat(timespec="minutes")
        held = call(port, "/ask", {"question": instance.question, "gather": False, "now": asked})
    finally:
        server.terminate()
        server.wait(timeout=30)
        memory = ROOT / "var" / "memory" / name
        if (memory / "facts.md").exists():
            shutil.copy(memory / "facts.md", out / f"{instance.id}.facts.md")
        shutil.rmtree(memory, ignore_errors=True)
    final = answer(f"What the user's personal memory gave for this question:\n{held}", instance)
    return {"memory": held, "answer": final, "told_seconds": told, "seconds": round(time.time() - began)}


def by_context(instance) -> dict:
    began = time.time()
    sessions = "\n\n".join(f"--- Session on {s.when} ---\n{s.as_text()}" for s in instance.sessions)
    final = answer(f"The user's past conversations with you, oldest first:\n{sessions}", instance)
    return {"answer": final, "seconds": round(time.time() - began)}


def one(instance, modes: list[str], ports: "queue.Queue", out: Path) -> dict:
    row = {"id": instance.id, "kind": instance.kind, "abstention": instance.abstention,
           "question": instance.question, "reference": instance.answer}
    for mode in modes:
        try:
            if mode == "memory":
                port = ports.get()  # one server per port at a time
                try:
                    got = by_memory(instance, port, out)
                finally:
                    ports.put(port)
            else:
                got = by_context(instance)
            got["judged"] = judge(instance, got["answer"])
        except Exception as wrong:  # noqa: BLE001 - one question failing is a wrong answer, kept with why
            got = {"error": repr(wrong), "judged": {"correct": False, "how": "error"}}
        row[mode] = got
    (out / f"{instance.id}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False))
    print(f"{instance.kind:28} {instance.id:22} " + "  ".join(
        f"{m}: {'ok ' if row[m]['judged']['correct'] else 'BAD'}" for m in modes), flush=True)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=25, help="questions, the same number of each type")
    parser.add_argument("--with-assistant", action="store_true",
                        help="keep single-session-assistant: what the agent said, which the memory drops")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--mode", choices=["memory", "context", "both"], default="both")
    parser.add_argument("--parallel", type=int, default=6)
    parser.add_argument("--port", type=int, default=7140, help="the first of --parallel ports")
    parser.add_argument("--only", nargs="*", help="these question ids")
    parser.add_argument("--graph", action="store_true", help="the memory reads every entry into its graph")
    args = parser.parse_args()
    global GRAPH
    GRAPH = args.graph
    if not os.environ.get("NEBIUS_API_KEY"):
        raise SystemExit("NEBIUS_API_KEY is not set: set -a; . ./.env; set +a")

    instances = lme.load("oracle")
    picked = ([i for i in instances if i.id in args.only] if args.only
              else lme.slice_of(instances, args.count, kinds=[k for k in lme.TYPES if args.with_assistant
                                                              or k != "single-session-assistant"], seed=args.seed))
    modes = ["memory", "context"] if args.mode == "both" else [args.mode]
    out = ROOT / "experiments" / "results" / "14_longmemeval" / f"{datetime.now():%Y%m%d-%H%M%S}-seed{args.seed}{'-graph' if args.graph else ''}"
    out.mkdir(parents=True)
    print(f"{len(picked)} questions, modes {modes}, results in {out}", flush=True)

    ports: queue.Queue = queue.Queue()
    for n in range(args.parallel):
        ports.put(args.port + n)
    with concurrent.futures.ThreadPoolExecutor(args.parallel) as pool:
        rows = list(pool.map(lambda instance: one(instance, modes, ports, out), picked))

    summary = {"slice": "oracle", "count": len(rows), "seed": args.seed, "with_assistant": args.with_assistant, "answerer": role("reader").model,
               "judge": "haiku", "memory": f"memory.server{'' if args.graph else ' --no-world'}, /ask gather=false"}
    for mode in modes:
        by_kind = defaultdict(list)
        for r in rows:
            by_kind[r["kind"]].append(r[mode]["judged"]["correct"])
        summary[mode] = {"accuracy": round(sum(r[mode]["judged"]["correct"] for r in rows) / len(rows), 3),
                         "by_kind": {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by_kind.items())}}
        print(f"\n{mode}: {summary[mode]['accuracy']:.1%}  " + "  ".join(f"{k} {v}" for k, v in summary[mode]["by_kind"].items()))
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
