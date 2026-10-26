"""Find in the catalogue by a task in words: code ranks every row, the decision model reads the few.

    .venv/bin/python experiments/12_pick_product/find.py <catalog dir> "a robot vacuum under 400 euros, ..."

1. The task is said in words, as a host would say it to the memory.
2. Nemotron turns it into conditions, and each into code over the catalogue's fields: once per
   task, not per row. The code is kept (find.json), so what was asked of the data can be read.
3. The code scores every row: a condition met counts, an unknown counts half, a condition broken
   rules the row out if the condition is a hard one. No model per row.
4. What the finalists lack, the web is asked for: per finalist, one search for its model and the
   fields its conditions need but its row doesn't hold; the pages read for that model alone, the
   rows folded again and scored again. Only the few are searched, never the thousand.
5. The top ten go to the decision model: for each condition the code could not settle, "do these
   texts say the model meets it?", read from the sentences the pages said about it.
6. The pick is the row with the most conditions held, by the product of their probabilities.
"""
import argparse
import concurrent.futures
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from terraweaver.nemotron import Nemotron as Reader  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harvest  # noqa: E402

SUPER = "nvidia/nemotron-3-super-120b-a12b"

FIELDS = """Each row is a dict:
  brand, model: str
  price_eur: [min, max] in euros over the offers seen, or None
  noise_db, threshold_mm, suction_pa: [min, max] over what pages said, or None
  hepa, pet_hair, carpet, needs_cloud, mop: True, False or None (not said)
  texts: list of {"text": what one page said about it, "url"}
  sources: number of pages that named it"""

PLAN = """A user asked for this: {task}

The candidates are rows of a catalogue.
{fields}

Split the request into its conditions. For each, write a Python expression over a row `r` that \
is True when the row meets it, False when it breaks it, and None when the row's fields can't tell \
(a field that is None). Use the interval's best end when judging a range (a price is met if the \
lowest seen fits). Say whether the condition is hard (a row that breaks it is out) or soft.
Answer with JSON only:
{{"conditions": [{{"name": "short", "says": "the condition in words", "hard": true, "code": "..."}}]}}"""


def score(row: dict, conditions: list[dict]) -> tuple[float, dict]:
    held = {}
    for c in conditions:
        # Unknown is decided here, not left to the planner's code: asked to answer None for a
        # field not known, it wrote `r['x'] is not None and ...`, and every row was ruled out.
        if any(row.get(f) is None for f in re.findall(r"r\[['\"](\w+)['\"]\]", c["code"])):
            held[c["name"]] = None
            continue
        try:
            held[c["name"]] = eval(c["code"], {"__builtins__": {"min": min, "max": max, "abs": abs}}, {"r": row})
        except Exception:  # noqa: BLE001 - a field the code didn't expect is a field not known
            held[c["name"]] = None
        if held[c["name"]] is not None:
            held[c["name"]] = bool(held[c["name"]])
    if any(held[c["name"]] is False and c.get("hard") for c in conditions):
        return -1.0, held
    return sum(1.0 if v else 0.5 if v is None else 0.0 for v in held.values()) + 0.01 * row["sources"], held


# What a search for a model's missing field says, in the words German shops and tests use.
ASKS = {"price_eur": "Preis", "noise_db": "Lautstärke dB", "threshold_mm": "Schwellenhöhe mm",
        "suction_pa": "Saugkraft Pa", "hepa": "HEPA Filter", "pet_hair": "Tierhaare",
        "carpet": "Hochflor Teppich", "needs_cloud": "ohne App Cloud lokal", "mop": "Wischfunktion"}


def wanted(row: dict, conditions: list[dict]) -> list[str]:
    """The fields the conditions read that this row does not hold."""
    return sorted({f for c in conditions for f in re.findall(r"r\[['\"](\w+)['\"]\]", c["code"])
                   if f in ASKS and row.get(f) is None})


def refill(catalog: Path, rows: list[dict], conditions: list[dict], engine: str, need: str) -> list[dict]:
    """Search the web for what the finalists lack; the offers found for them, kept in refill.jsonl."""
    reader = Reader(model=SUPER, timeout=300)

    def one(row):
        fields = wanted(row, conditions)
        if not fields:
            return []
        q = f"{row['brand']} {row['model']} " + " ".join(ASKS[f] for f in fields)
        run = harvest.subprocess.run(["ait-search", "--engine", engine, "search", q, "--limit", "5",
                                      "--fetch", "3", "--tag", "pick12-refill"],
                                     capture_output=True, text=True, timeout=600)
        try:
            found = json.loads(run.stdout).get("results", [])
        except ValueError:
            return []
        offers = []
        for r in found:
            body = next((b for b in r.get("bodies") or [] if b.get("path") and b.get("source") == engine), None)
            if body:
                page = {"url": r["url"], "published": r.get("published"), "path": body["path"]}
                offers += [o for o in harvest.read(reader, need, page) if harvest.key(o) == row["key"]]
        print(f"  {row['brand']} {row['model']}: asked {fields}, {len(offers)} offers")
        return offers
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        got = [o for offers in pool.map(one, rows) for o in offers]
    harvest.verify(Reader(), got)
    with open(catalog / "refill.jsonl", "a") as kept:
        kept.writelines(json.dumps(o, ensure_ascii=False) + "\n" for o in got)
    return got


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("task")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--refill", type=int, default=20, help="finalists the web is asked about")
    parser.add_argument("--engine", default="tavily")
    parser.add_argument("--need", default="robot vacuum cleaners")
    args = parser.parse_args()

    rows = [json.loads(l) for l in (args.catalog / "catalog.jsonl").read_text().splitlines() if l.strip()]
    said = Reader(model=SUPER, timeout=300).say("Answer exactly in the form asked.",
                                                 PLAN.format(task=args.task, fields=FIELDS),
                                                 room=6000, thinking=False)
    plan = json.loads(said[said.find("{"):said.rfind("}") + 1])
    conditions = plan["conditions"]
    for c in conditions:
        print(f"  {'HARD' if c.get('hard') else 'soft'}  {c['name']}: {c['code']}")

    scored = sorted(((score(r, conditions), r) for r in rows), key=lambda x: -x[0][0])
    out_count = sum(1 for (s, _), _ in scored if s < 0)
    if args.refill:
        few = [r for (s, _), r in scored[:args.refill] if s >= 0]
        print(f"\n{len(rows)} rows; {out_count} ruled out by code; the web asked about {len(few)}")
        refill(args.catalog, few, conditions, args.engine, args.need)
        offers = harvest.jsonl(args.catalog / "offers.jsonl") + harvest.jsonl(args.catalog / "refill.jsonl")
        rows = harvest.fold(offers)
        scored = sorted(((score(r, conditions), r) for r in rows), key=lambda x: -x[0][0])
        out_count = sum(1 for (s, _), _ in scored if s < 0)
    top = [(held, r) for (s, held), r in scored[:args.top] if s >= 0]
    print(f"\n{len(rows)} rows; {out_count} ruled out by code; top {len(top)} to the decision model\n")

    reader = Reader()

    def check(item):
        held, row = item
        texts = "\n".join(f"- {t['text']}" for t in row["texts"][:12] if t.get("text"))
        facts = {k: v for k, v in row.items() if k not in ("texts", "key")}
        state = f"{row['brand']} {row['model']}\nFields: {json.dumps(facts)}\nWhat pages said:\n{texts}"
        p = {}
        for c in conditions:
            if held[c["name"]] is not None:
                p[c["name"]] = 1.0 if held[c["name"]] else 0.0
                continue
            p[c["name"]] = reader.noul(state, f"Does this model meet the condition: {c['says']}?",
                                       true="yes, what is said shows it meets it",
                                       false="no, or nothing said shows it")["p"]["yes"]
        return row, held, p

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        checked = list(pool.map(check, top))
    checked.sort(key=lambda x: -sum(math.log(max(v, 1e-3)) for v in x[2].values()))
    for row, held, p in checked:
        price = row["price_eur"]
        print(f"{row['brand']} {row['model']}  {price}  sources {row['sources']}")
        print("   " + "  ".join(f"{k}={'code:' + str(held[k]) if held[k] is not None else f'p{v:.2f}'}"
                                for k, v in p.items()))
    (args.catalog / "find.json").write_text(json.dumps(
        {"task": args.task, "conditions": conditions, "rows": len(rows), "ruled_out": out_count,
         "finalists": [{"brand": r["brand"], "model": r["model"], "price_eur": r["price_eur"],
                        "held": h, "p": p} for r, h, p in checked]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
