"""A first draft of what each batch of facts should leave in the world, for a person to correct.

The expectation used to be worked out from the sentence every time the check ran, by a parser
that got it wrong three times in a day — it left "the city of" on a name, took a whole clause
for a name, and compared each fact against the final world without noticing the fact had been
superseded. A measurement that reruns a parser measures the parser.

So the expectation is written down once instead: one file per batch, drafted here and then read
and corrected by hand. After that the check is a lookup and can only be wrong about the world.

    .venv/bin/python experiments/draft_expectations.py --facts 455 --batch 10
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc                       # noqa: E402
from experiments.expected import read, owed_for      # noqa: E402

WHERE = ROOT / "experiments" / "expected"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts", type=int, default=455)
    parser.add_argument("--batch", type=int, default=10)
    args = parser.parse_args()
    WHERE.mkdir(parents=True, exist_ok=True)

    facts = fc.load("sh", "6k").facts[: args.facts]
    standing: dict = {}          # (subject, predicate) -> object, across the whole slice so far
    for first in range(0, len(facts), args.batch):
        here = facts[first: first + args.batch]
        owed = []
        for offset, fact in enumerate(here):
            number = first + offset + 1
            got = read(fact)
            one = {"fact": number, "said": fact}
            if not got or not owed_for(got[1]):
                one["expect"] = None
                one["why"] = "the draft could not read this sentence — say what it owes by hand"
            else:
                subject, predicate, obj = got
                key = (subject, predicate)
                was = standing.get(key)
                standing[key] = obj
                one["expect"] = {"subject": subject, "predicate": predicate, "object": obj,
                                 "subject_first": True}
                if was is not None and was != obj:
                    one["expect"]["replaces"] = was
                    one["why"] = (f"says it again with a different value: the world should hold "
                                  f"{obj!r} and keep {was!r} as history")
            owed.append(one)
        path = WHERE / f"{first + 1:03d}-{first + len(here):03d}.json"
        # A hand correction outlives the draft. Redrafting wiped ten of them the first time,
        # which is the whole difference between an expectation somebody agreed to and one a
        # parser produced again.
        if path.exists():
            held = {one["fact"]: one for one in json.loads(path.read_text())["facts"]}
            owed = [held[one["fact"]]
                    if (held.get(one["fact"], {}).get("expect") or {}).get("corrected")
                    else one for one in owed]
        path.write_text(json.dumps({
            "batch": [first + 1, first + len(here)],
            "note": "Drafted from the sentences; read it and correct it. `expect: null` means "
                    "nobody has said what this fact owes yet, and it is not counted.",
            "facts": owed,
        }, indent=2, ensure_ascii=False) + "\n")
    made = sorted(WHERE.glob("*.json"))
    unread = sum(1 for p in made for f in json.loads(p.read_text())["facts"] if f["expect"] is None)
    print(f"{len(made)} files in {WHERE}")
    print(f"{unread} facts the draft could not read — those need a hand before they count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
