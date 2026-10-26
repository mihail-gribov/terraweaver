"""The link check as `formalise.check` now asks it of a claim-reading picker, on the gold facts.

    .venv/bin/python experiments/09_decision/check_links.py [--limit N]

Each fact's link three ways — as said (owes says_so), turned round (owes backwards; predicates that
read the same either way are left out) and with another fact's predicate (owes not_in_it, which the
check does not act on). Two noul questions each, built by `check._link_as_claims` and folded by
`check._as_three`, so what is measured is the check's own question. Reported: how often the verdict
is right, and how often a line would be refused (`SURE_ENOUGH`) when it should not be.
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from terraweaver import decision, prompts  # noqa: E402
from terraweaver.formalise import check  # noqa: E402
import run  # noqa: E402

OUT = HERE.parents[1] / "experiments/results/09_decision/check_links.jsonl"


def cases(limit):
    import random

    rng, out = random.Random(9), []
    facts = run.facts()
    for f in facts[:limit]:
        other = rng.choice([g for g in facts if g["predicate"] != f["predicate"]])
        s, o, p = f["subject"], f["object"], f["predicate"]
        out.append((f, s, p, o, check.SAYS_SO))
        if not any(w in p for w in run.EITHER_WAY):
            out.append((f, o, p, s, check.BACKWARDS))
        out.append((f, s, other["predicate"], o, check.NOT_IN_IT))
    return out


def one(picker, case):
    f, a, word, b, owed = case
    claim = {"what": "link", "subject": run._thing(a), "object": run._thing(b), "word": word}
    got = picker.ask(prompts.IS_IT_SAID.format(words=f["said"]),
                     {k: v for k, v in check._link_as_claims(claim).items()})
    scored = check._as_three(got["as_written"]["noul"], got["turned"]["noul"])
    verdict = max(scored, key=scored.get)
    return {"fact": f["fact"], "owed": owed, "verdict": verdict, "sure": scored[verdict],
            "as_written": got["as_written"]["noul"], "turned": got["turned"]["noul"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=decision.MODEL)
    a = ap.parse_args()
    picker = decision.Decision(model=a.model, ttl=90)
    todo = cases(a.limit)
    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(lambda c: one(picker, c), todo))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows))
    for owed in (check.SAYS_SO, check.BACKWARDS, check.NOT_IN_IT):
        mine = [r for r in rows if r["owed"] == owed]
        right = sum(r["verdict"] == owed for r in mine)
        # What the check would do: refuse a link only on a sure backwards.
        refused = sum(r["verdict"] == check.BACKWARDS and r["sure"] >= check.SURE_ENOUGH for r in mine)
        print(f"{owed:10} n={len(mine):3}  verdict right {right / len(mine):.3f}  refused {refused}")


if __name__ == "__main__":
    main()
