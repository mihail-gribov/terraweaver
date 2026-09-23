"""All the facts, ten at a time, into one world, checking each batch as it lands.

The batches are the same as `first_batch.py` runs one at a time; this drives them in order and
keeps a line per batch, so the run can be watched while it happens and read after it. Facts are
given in the order the benchmark gives them, into one accumulating world — which is the only
way the superseding pairs meet, since most of them are a hundred facts apart.

    .venv/bin/python experiments/full_run.py --facts 455 --port 7300
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts", type=int, default=455)
    parser.add_argument("--batch", type=int, default=10)
    parser.add_argument("--from", dest="start", type=int, default=1)
    parser.add_argument("--port", type=int, default=7300)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--into", type=Path, default=None)
    parser.add_argument("--repeat", type=int, default=1,
                        help="run the whole thing this many times, into separate worlds")
    args = parser.parse_args()

    if args.repeat > 1:
        # Every number this measurement produced today came from one run, and one batch scored
        # 4, 9, 10, 0, 3 and 0 out of ten on unchanged code. A single run cannot tell a change
        # from a bad afternoon; repeats can, and they are the cheapest thing that can.
        base = (args.into or ROOT / "experiments" / "results" / "batches" /
                f"{datetime.now():%Y%m%d-%H%M%S}-repeat").resolve()
        runs = []
        for turn in range(args.repeat):
            where = base.parent / f"{base.name}-{turn + 1}"
            run = subprocess.run(
                [sys.executable, __file__, "--facts", str(args.facts), "--batch", str(args.batch),
                 "--from", str(args.start), "--port", str(args.port + turn), "--model", args.model,
                 "--into", str(where)], cwd=ROOT, capture_output=True, text=True)
            print(run.stdout.rstrip(), flush=True)
            runs.append(where)
        print("\n--- the same batches across runs")
        per: dict = {}
        for where in runs:
            for line in open(where / "batches.jsonl"):
                one = json.loads(line)
                if "/" in one["scored"]:
                    per.setdefault(one["from"], []).append(int(one["scored"].split("/")[0]))
        for first, got in sorted(per.items()):
            got = sorted(got)
            middle = got[len(got) // 2]
            print(f"  {first:>3}-{first + args.batch - 1:<3}  {'  '.join(str(g) for g in got)}"
                  f"   median {middle}   spread {got[-1] - got[0]}")
        print(f"\nworlds: {', '.join(str(r) for r in runs)}")
        return 0

    work = (args.into or ROOT / "experiments" / "results" / "batches" /
            f"{datetime.now():%Y%m%d-%H%M%S}-full-{args.model}").resolve()
    work.mkdir(parents=True, exist_ok=True)
    summary = work / "batches.jsonl"
    print(f"{args.facts} facts, {args.batch} at a time, into {work}", flush=True)

    started = time.monotonic()
    total = {"ok": 0, "seen": 0, "turns": 0, "cost": 0.0}
    for first in range(args.start, args.start + args.facts, args.batch):
        run = subprocess.run(
            [sys.executable, str(ROOT / "experiments" / "first_batch.py"),
             "--from", str(first), "--facts", str(args.batch), "--into", str(work),
             "--port", str(args.port), "--model", args.model],
            cwd=ROOT, capture_output=True, text=True, timeout=1800)
        out = run.stdout
        scored = [l for l in out.splitlines() if "joined;" in l]
        got = scored[0].split("—")[-1].strip().split()[0] if scored else "?/?"
        spent = [l for l in out.splitlines() if l.strip().endswith("min")]
        turns = int(spent[0].split()[0]) if spent else 0
        cost = float(spent[0].split("$")[1].split(",")[0]) if spent else 0.0
        wrong = [l.strip() for l in out.splitlines()
                 if l.strip().startswith(("WAY", "WORD", "MISSING", "NO LINK"))]
        ok, seen = (int(x) for x in got.split("/")) if "/" in got and got != "?/?" else (0, 0)
        total["ok"] += ok; total["seen"] += seen
        total["turns"] += turns; total["cost"] += cost
        line = {"from": first, "scored": got, "turns": turns, "cost": cost,
                "wrong": [w[:90] for w in wrong], "failed": run.returncode != 0}
        with open(summary, "a") as fh:
            fh.write(json.dumps(line) + "\n")
        print(f"  {first:>3}-{first + args.batch - 1:<3} {got:>6}  {turns:>3} turns  ${cost:.2f}"
              + (f"   [{len(wrong)} flagged]" if wrong else "")
              + ("   FAILED" if run.returncode != 0 else ""), flush=True)
        if run.returncode != 0:
            print("    " + (run.stderr or out).strip().splitlines()[-1][:160], flush=True)

    print(f"\n{total['ok']}/{total['seen']} joined, {total['turns']} turns, ${total['cost']:.2f}, "
          f"{(time.monotonic() - started) / 60:.0f} min")
    print(f"world: {work}/world.db")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
