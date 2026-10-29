"""FactConsolidation through the contract: every fact by `tell`, every question by `ask`.

    .venv/bin/python benchmarks/run_contract.py                       # starts the baseline on :7160
    .venv/bin/python benchmarks/run_contract.py --url http://127.0.0.1:7100 --questions 10

The step the mock is cut up from. `run_context.py` gives the model the benchmark's numbered list in
one prompt; this gives the same facts to a memory behind the four calls (docs/contract.md), one
`tell` each in the order they were stated, and asks each question with `ask`. No agent in between:
what is measured is the memory, not a host's writing. Against the baseline it is the same thing as
`run_context.py` behind an interface, so it must score what that scores — and every step that
replaces a piece of the baseline must keep scoring it.

The question carries the benchmark's own instruction ("the value that holds now and nothing else"),
because the judge is a substring match: an answer that names the old value beside the new one
would pass whichever of them holds.
"""
import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
ONLY_THE_VALUE = " Answer with the value that holds now and nothing else."


def post(url: str, path: str, body: dict, timeout: float = 600) -> str:
    request = urllib.request.Request(f"{url}{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(request, timeout=timeout).read().decode()


def baseline(name: str, port: int) -> subprocess.Popen:
    server = subprocess.Popen([sys.executable, "-m", "memory.journal", "--name", name, "--port", str(port)],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            return server
        except OSError:
            time.sleep(0.5)
    server.terminate()
    raise RuntimeError(f"the baseline did not come up on port {port}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="a memory serving the contract; without it the baseline is started")
    parser.add_argument("--port", type=int, default=7160, help="where to start the baseline")
    parser.add_argument("--hops", default="sh")
    parser.add_argument("--context", default="6k")
    parser.add_argument("--questions", type=int, default=100)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--told", action="store_true", help="the memory already holds the facts: only ask")
    parser.add_argument("--failed", type=Path, help="ask only the questions this results.json got wrong")
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    server = None
    if not args.url:
        server = baseline(f"fc-{stamp}", args.port)
        args.url = f"http://127.0.0.1:{args.port}"
    try:
        if not args.told:
            started = time.monotonic()
            for fact in variant.facts:
                kept = post(args.url, "/tell", {"text": fact, "source": variant.name})
                if kept != "Kept.":
                    raise RuntimeError(f"tell answered {kept!r} for {fact!r}")
            print(f"told {len(variant.facts)} facts in {time.monotonic() - started:.0f}s")

        def one(q):
            started = time.monotonic()
            try:
                said = post(args.url, "/ask", {"question": q.text + ONLY_THE_VALUE})
                error = None
            except OSError as failed:
                said, error = "", str(failed)[:300]
            return {"id": q.id, "question": q.text, "gold": q.gold, "answer": said[:300],
                    "correct": fc.correct(said, q.gold), "seconds": round(time.monotonic() - started, 1),
                    **({"error": error} if error else {})}

        with concurrent.futures.ThreadPoolExecutor(args.parallel) as pool:
            asked = variant.questions[:args.questions]
            if args.failed:
                wrong = {r["id"] for r in json.loads(args.failed.read_text())["runs"] if not r["correct"]}
                asked = [q for q in asked if q.id in wrong]
            runs = list(pool.map(one, asked))
    finally:
        if server:
            server.terminate()
            server.wait()

    for n, r in enumerate(runs, 1):
        print(f"{'ok ' if r['correct'] else '   '} {n:>3}/{len(runs)} {r['gold']} <- {r['answer'][:80]}")
    summary = {"accuracy": round(sum(r["correct"] for r in runs) / len(runs), 3),
               "questions": len(runs), "errors": sum("error" in r for r in runs),
               "url": args.url, "mode": "contract", "facts": len(variant.facts)}
    out_dir = RESULTS / f"{stamp}-{variant.name}-contract"
    out_dir.mkdir(parents=True)
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "runs": runs}, indent=1))
    print(json.dumps(summary, indent=2))
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
