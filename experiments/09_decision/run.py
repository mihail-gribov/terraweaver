"""09 — Nemotron as the decision model: how often it is right, how sure when wrong, and what fixes that.

    .venv/bin/python experiments/09_decision/run.py ask bench      # read every row, cache the logits
    .venv/bin/python experiments/09_decision/run.py ask world --limit 60
    .venv/bin/python experiments/09_decision/run.py fit bench --ship

Two sets of rows. **bench** (`bench.py`) is what the temperatures are fitted on: public datasets
from the local cache, ~300 rows a mode, as issue #1 asks. **world** is the questions the world
itself asks, over our own gold facts — the check of whether what is calibrated on public data
holds for the questions that matter here. It is measured and never fitted on.

`ask` reads each labelled row in two option orders — as given and reversed — and caches the raw
letter log-probabilities per order and the seconds it took in experiments/results/09_decision/
<set>.jsonl, so `fit` costs nothing and can be re-run. `fit` compares reading one order against the
mean of both, fits one temperature per mode on half the rows by calibration error (not log-loss),
reports the other half overall and per dataset, and with `--ship` writes terraweaver/decision.json:
per mode the temperature and whether both orders paid.

The world rows are the 447 facts of experiments/expected, each a sentence and the subject, predicate and
object it says. From each fact, questions the world really asks, built by the world's own code:

    choice   check._asking over the link as said (says_so), turned round (backwards) and with the
             predicate of another fact (not_in_it) — what `formalise` asks before it writes
    noul     "does the sentence say <claim>": the claim as said (true) or with a foreign predicate
    tfu      the same over three: as said (true), turned round (false), a third claim about
             things the sentence never joins (unsure)

Predicates that read the same either way round (married, associated, affiliated) give no backwards
row: turned round they are still what was said.
"""
import argparse
import json
import math
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from terraweaver import nemotron  # noqa: E402
from terraweaver import decision, prompts  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402
from terraweaver.formalise import check  # noqa: E402

OUT = ROOT / "experiments/results/09_decision"
MODEL = decision.MODEL          # --model: any Nemotron on Token Factory; caches and fits are per model


def cache(which: str) -> Path:
    return OUT / f"{which}-{MODEL.split('/')[-1]}.jsonl"
EITHER_WAY = ("married", "associated", "affiliated", "sibling", "partner")


def facts() -> list[dict]:
    rows = []
    for path in sorted((ROOT / "experiments/expected").glob("*.json")):
        for fact in json.loads(path.read_text())["facts"]:
            if fact.get("expect"):
                rows.append({"fact": fact["fact"], "said": fact["said"], **fact["expect"]})
    return rows


def _thing(name: str):
    return SimpleNamespace(display_name=lambda: name)


def _phrase(a: str, word: str, b: str) -> str:
    return f"{a} {word} {b}"


def rows(seed: int = 9) -> list[dict]:
    """Every labelled question, with the state, the instructions and the options in the world's form."""
    rng = random.Random(seed)
    all_facts = facts()
    out = []
    for f in all_facts:
        other = rng.choice([g for g in all_facts if g["predicate"] != f["predicate"]])
        third = rng.choice([g for g in all_facts if g["fact"] != f["fact"]])
        state = prompts.IS_IT_SAID.format(words=f["said"])
        symmetric = any(w in f["predicate"] for w in EITHER_WAY)
        s, o, p = f["subject"], f["object"], f["predicate"]

        def link(a, b, word):
            asked, options = check._asking({"what": "link", "subject": _thing(a), "object": _thing(b),
                                            "word": word})
            return {"type": "choice", "instructions": asked, "criteria": options}

        out.append({"id": f"{f['fact']}-c-says", "mode": "choice", "state": state,
                    "asked": link(s, o, p), "label": check.SAYS_SO})
        if not symmetric:
            out.append({"id": f"{f['fact']}-c-back", "mode": "choice", "state": state,
                        "asked": link(o, s, p), "label": check.BACKWARDS})
        out.append({"id": f"{f['fact']}-c-not", "mode": "choice", "state": state,
                    "asked": link(s, o, other["predicate"]), "label": check.NOT_IN_IT})

        def yes_no(kind, claim):
            return {"type": kind, "instructions": f"Does that sentence say «{claim}»?",
                    "criteria": {"true": "yes — it says that, in those words or plainly the same thing",
                                 "false": "no — it says something that rules this out"}}

        out.append({"id": f"{f['fact']}-n-true", "mode": "noul", "state": state,
                    "asked": yes_no("noul", _phrase(s, p, o)), "label": "true"})
        out.append({"id": f"{f['fact']}-n-false", "mode": "noul", "state": state,
                    "asked": yes_no("noul", _phrase(s, other["predicate"], o)), "label": "false"})
        out.append({"id": f"{f['fact']}-t-true", "mode": "tfu", "state": state,
                    "asked": yes_no("tfu", _phrase(s, p, o)), "label": "true"})
        if not symmetric:
            out.append({"id": f"{f['fact']}-t-false", "mode": "tfu", "state": state,
                        "asked": yes_no("tfu", _phrase(o, p, s)), "label": "false"})
        out.append({"id": f"{f['fact']}-t-unsure", "mode": "tfu", "state": state,
                    "asked": yes_no("tfu", _phrase(s, third["predicate"], third["object"])),
                    "label": "unsure"})
    return out


# --- ask: the raw letters, in two orders, cached ------------------------------------------------

SETS = {"bench": bench.rows, "world": rows}


def _names_and_texts(asked: dict) -> tuple[list, list]:
    criteria = asked["criteria"]
    if asked["type"] in ("noul", "tfu"):
        names = ["true", "false"] + (["unsure"] if asked["type"] == "tfu" else [])
        texts = [criteria["true"], criteria["false"]] + ([decision.UNSETTLED] if asked["type"] == "tfu" else [])
        return names, texts
    return list(criteria), [str(v) for v in criteria.values()]


def read_row(model: decision.Decision, row: dict) -> dict:
    names, texts = _names_and_texts(row["asked"])
    orders, seconds = {}, []
    for order, idx in (("given", list(range(len(names)))), ("reversed", list(range(len(names)))[::-1])):
        began = time.monotonic()
        raw = model.reader.marks(row["state"], row["asked"]["instructions"], [texts[i] for i in idx])
        seconds.append(round(time.monotonic() - began, 3))
        orders[order] = {names[i]: raw[nemotron.LETTERS[k]] for k, i in enumerate(idx)}
    return {"id": row["id"], "mode": row["mode"], "data": row.get("data", "world"),
            "label": row["label"], "orders": orders, "seconds": seconds}


def ask(which: str, limit: int | None, workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = cache(which)
    done = {json.loads(line)["id"] for line in raw.open()} if raw.exists() else set()
    todo = [r for r in SETS[which]() if r["id"] not in done][:limit]
    print(f"{len(done)} cached, {len(todo)} to ask")
    model = decision.Decision(model=MODEL, ttl=120)
    failed = 0
    with ThreadPoolExecutor(workers) as pool, raw.open("a") as out:
        for row, future in zip(todo, [pool.submit(read_row, model, r) for r in todo]):
            try:
                out.write(json.dumps(future.result()) + "\n")
            except Exception as wrong:  # noqa: BLE001 - one row lost is counted, not fatal
                failed += 1
                print(f"  {row['id']}: {str(wrong)[:120]}")
    print(f"asked {len(todo) - failed}, failed {failed}")


# --- fit: measure, calibrate, ship --------------------------------------------------------------

BINS = 15


def _logits(rec: dict, how: str) -> dict:
    if how == "given":
        return rec["orders"]["given"]
    # Both orders: the mean log-probability, which cancels a lean towards the first letter.
    return {k: (rec["orders"]["given"][k] + rec["orders"]["reversed"][k]) / 2 for k in rec["orders"]["given"]}


def _measure(recs: list, how: str, t: float) -> dict:
    n = len(recs)
    if not n:
        return {}
    right, nll, wrong_sure, bins = 0, 0.0, 0, [[0, 0.0, 0] for _ in range(BINS)]
    for r in recs:
        p = nemotron.softmax(_logits(r, how), t)
        pick = max(p, key=p.get)
        ok = pick == r["label"]
        right += ok
        nll -= math.log(max(p[r["label"]], 1e-12))
        wrong_sure += (not ok) and p[pick] >= 0.9
        b = bins[min(BINS - 1, int(p[pick] * BINS))]
        b[0] += 1
        b[1] += p[pick]
        b[2] += ok
    ece = sum(abs(b[1] - b[2]) for b in bins) / n
    return {"n": n, "accuracy": round(right / n, 3), "ece": round(ece, 3), "nll": round(nll / n, 3),
            "wrong_at_0.9": wrong_sure}


GRID = [round(0.2 * 1.08 ** i, 3) for i in range(80)]


def _fit_t(recs: list, how: str) -> float:
    # By calibration error, as the issue asks; log-loss breaks near-ties, which ECE on a few hundred
    # rows has plenty of. A temperature reorders nothing, so accuracy is untouched by it.
    return min(GRID, key=lambda t: (lambda m: (m["ece"], m["nll"]))(_measure(recs, how, t)))


def _first_place(recs: list) -> float:
    """How often the option shown first wins, over both orders."""
    wins = sum(max(o, key=o.get) == list(o)[0] for r in recs for o in r["orders"].values())
    return round(wins / max(1, 2 * len(recs)), 3)


def _split(recs: list, seed: int = 9) -> tuple[list, list]:
    """Half to fit, half to report, within every dataset; world rows by fact, so no sentence is on both."""
    rng, train = random.Random(seed), set()
    for data in sorted({r["data"] for r in recs}):
        groups = sorted({r["id"].split("-")[0] if data == "world" else r["id"]
                         for r in recs if r["data"] == data})
        rng.shuffle(groups)
        train |= {(data, g) for g in groups[: len(groups) // 2]}
    key = lambda r: (r["data"], r["id"].split("-")[0] if r["data"] == "world" else r["id"])  # noqa: E731
    return [r for r in recs if key(r) in train], [r for r in recs if key(r) not in train]


def fit(which: str, ship: bool) -> None:
    recs = [{"data": "world", **json.loads(line)} for line in cache(which).open()]
    shipped = {"calibration": nemotron.fitted_for(nemotron.CALIBRATION, MODEL)} if which == "world" else {}
    report = {"model": MODEL, "set": which, "rows": len(recs), "modes": {}}
    calibration = {}
    for mode in ("noul", "tfu", "choice", "scale"):
        mine = [r for r in recs if r["mode"] == mode]
        if not mine:
            continue
        train, test = _split(mine)
        seconds = sorted(s for r in mine for s in r.get("seconds", []))
        out = {"first_place_wins": _first_place(mine),
               "seconds_median": seconds[len(seconds) // 2] if seconds else None}
        for how in ("given", "both"):
            t = _fit_t(train, how)
            out[how] = {"t": t, "raw": _measure(test, how, 1.0), "fitted": _measure(test, how, t)}
            if shipped.get("calibration", {}).get(mode):
                ts = shipped["calibration"][mode]["temperature"]
                out[how]["shipped_t"] = {"t": ts, **_measure(mine, how, ts)}
            out[how]["by_data"] = {d: _measure([r for r in test if r["data"] == d], how, t)
                                   for d in sorted({r["data"] for r in test})}
            out[how]["by_label"] = {lab: _measure([r for r in test if r["label"] == lab], how, t)["accuracy"]
                                    for lab in sorted({r["label"] for r in test})}
        report["modes"][mode] = out
        # Both orders cost a second call; kept where they pay on held-out rows, by accuracy averaged over
        # the labels — plain accuracy tied on noul (0.819 each) while one order caught a "no" 63% of
        # the time and both 86%, which is the answer a judge exists to give.
        balanced = {h: sum(out[h]["by_label"].values()) / len(out[h]["by_label"]) for h in ("given", "both")}
        out["balanced_accuracy"] = {h: round(v, 3) for h, v in balanced.items()}
        both = balanced["both"] >= balanced["given"]
        how = "both" if both else "given"
        calibration[mode] = {"orders": 2 if both else 1, "temperature": _fit_t(mine, how)}
    report["calibration (all rows)"] = calibration
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{which}_report-{MODEL.split('/')[-1]}.json").write_text(json.dumps(report, indent=2))
    _print(report)
    if ship:
        if which != "bench":
            raise SystemExit("only the bench set is fitted on; the world set checks it")
        held = json.loads(nemotron.CALIBRATION.read_text()) if nemotron.CALIBRATION.exists() else {}
        held.setdefault("models", {})[MODEL] = {"calibration": calibration,
                                                "fitted_on": "experiments/09_decision bench", "rows": len(recs)}
        nemotron.CALIBRATION.write_text(json.dumps(held, indent=2) + "\n")
        print(f"wrote {MODEL} into {nemotron.CALIBRATION}")


def _print(report: dict) -> None:
    for mode, out in report["modes"].items():
        print(f"\n{mode}: first place wins {out['first_place_wins']}, {out['seconds_median']} s a call, "
              f"balanced accuracy {out['balanced_accuracy']}")
        for how in ("given", "both"):
            x = out[how]
            line = (f"  {how:6} acc {x['fitted']['accuracy']:.3f}  ECE {x['raw']['ece']:.3f} -> "
                    f"{x['fitted']['ece']:.3f} (t={x['t']})  wrong@0.9 {x['raw']['wrong_at_0.9']} -> "
                    f"{x['fitted']['wrong_at_0.9']}  by label {x['by_label']}")
            if "shipped_t" in x:
                line += f"  | shipped t={x['shipped_t']['t']}: ECE {x['shipped_t']['ece']}"
            print(line)
            for d, m in x["by_data"].items():
                print(f"      {d:14} n={m['n']:3}  acc {m['accuracy']:.3f}  ECE {m['ece']:.3f}")
    print("\nship:", report["calibration (all rows)"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ask", "fit"])
    ap.add_argument("which", choices=list(SETS))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ship", action="store_true")
    ap.add_argument("--model", default=decision.MODEL)
    a = ap.parse_args()
    MODEL = a.model
    ask(a.which, a.limit, a.workers) if a.what == "ask" else fit(a.which, a.ship)
