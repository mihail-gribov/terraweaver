"""What a run spent on Nemotron, by step and model, from the `usage.jsonl` files under a folder
(written when `TERRAWEAVER_USAGE` names one; benchmarks/scenarios.py sets it per scenario).

Run: .venv/bin/python scripts/usage.py benchmarks/results/scenarios-...
"""
import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    rows = [json.loads(line) for f in Path(sys.argv[1]).rglob("usage.jsonl") for line in f.read_text().splitlines() if line]
    by = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        b = by[(r["step"], r["model"])]
        b[0] += 1
        b[1] += r["in"]
        b[2] += r["out"]
        b[3] += r.get("thought") or 0
    total = sum(b[1] + b[2] for b in by.values()) or 1
    print(f"{'step':34} {'model':32} {'calls':>6} {'in':>9} {'out':>8} {'thought':>8} {'share':>6}")
    for (step, model), (n, i, o, t) in sorted(by.items(), key=lambda kv: -(kv[1][1] + kv[1][2])):
        print(f"{step:34} {model:32} {n:6} {i:9} {o:8} {t:8} {(i + o) / total:6.1%}")
    print(f"\n{len(rows)} calls, {sum(b[1] for b in by.values())} in, {sum(b[2] for b in by.values())} out")
    return 0


if __name__ == "__main__":
    sys.exit(main())
