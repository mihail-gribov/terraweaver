"""Stage A: what web search returns, per scenario kind.

Runs QUERIES through ait-search with Tavily and records, per query: how many
results, how many are new to the store, how many carry a publication date,
and the urls with scores. Whether a result is a listing or an item page, and
whether it is about the wrong place, is read by a person from the printed
table — the probe does not guess it.

    python experiments/04_web_search/probe.py [--engine tavily] [--only event,news]
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

from queries import QUERIES

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
STORE = ROOT / "var" / "web_search_store"


def search(q: dict, engine: str, limit: int) -> dict:
    cmd = ["ait-search", "--engine", engine, "--store", str(STORE), "search", q["query"],
           "--limit", str(limit), "--tag", f"04:{q['kind']}"]
    if q.get("since"):
        cmd += ["--since", q["since"]]
    done = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"error": "no_json", "stdout": done.stdout[-2000:], "stderr": done.stderr[-2000:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="tavily")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--only", default="", help="comma-separated kinds")
    args = ap.parse_args()
    kinds = {k for k in args.only.split(",") if k}

    runs = []
    for q in QUERIES:
        if kinds and q["kind"] not in kinds:
            continue
        out = search(q, args.engine, args.limit)
        runs.append({**q, "response": out})
        if "error" in out:
            print(f"\n## [{q['kind']}] {q['query']}  ERROR {out.get('error')}: {out.get('hint', '')}")
            continue
        results = out.get("results", [])
        dated = sum(1 for r in results if r.get("published"))
        print(f"\n## [{q['kind']}] {q['query']}  n={out.get('n')} new={out.get('n_new')} "
              f"dated={dated}/{len(results)}")
        for r in results:
            print(f"   {r.get('published') or '-':10}  {r['url'][:100]}")

    STORE.mkdir(parents=True, exist_ok=True)
    (HERE / "results").mkdir(exist_ok=True)
    path = HERE / "results" / f"probe-{date.today().isoformat()}-{args.engine}.json"
    path.write_text(json.dumps(runs, ensure_ascii=False, indent=1))
    print(f"\ntrace: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
