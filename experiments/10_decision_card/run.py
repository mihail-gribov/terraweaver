"""10 — the decision model's card: Nemotron read as a decision model, on the rows the TypeCastLM card used.

    .venv/bin/python experiments/10_decision_card/run.py ask              # read every row, cached
    .venv/bin/python experiments/10_decision_card/run.py ask --limit 200
    .venv/bin/python experiments/10_decision_card/run.py report           # the card's Numbers table

The rows are the TypeCastLM-Qwen3.5-3.8B card's own (`readme_items.jsonl`: SuperGLUE BoolQ 3000,
SuperGLUE RTE 277, FEVER in NLI form 2089 of which 694 NOT ENOUGH INFO), with the card's states,
questions and criteria word for word, so the two tables compare row for row. Each row is read by
`terraweaver.decision.Decision` with the calibration it ships (`decision.json`): `noul` on every
row, `tfu` on the FEVER rows for the third answer. Raw logits and the seconds each read took are
cached in experiments/results/10_decision_card/reads.jsonl, so `report` costs nothing.

Definitions are the card's (TypeCastLM exp89 `card_numbers.py`): yes/no on decidable rows, AUC on
z_true - z_false, accuracy at 0.5 at the shipped `noul` temperature, ECE on max(p, 1-p) in ten
bins; on FEVER, unsure AUC on z_unsure - max(z_true, z_false) and three-class accuracy at the
shipped `tfu` temperature, over all rows.
"""
import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from terraweaver.nemotron import softmax  # noqa: E402
from terraweaver import decision  # noqa: E402

ITEMS = Path(os.environ.get(
    "CARD_ITEMS", Path.home() / "Projects/ai-safity/.claude/worktrees/agent-ad5eaef903fb6848c/"
                                "experiments/77_question_gen/data/readme_items.jsonl"))
OUT = ROOT / "experiments/results/10_decision_card"
READS = OUT / "reads.jsonl"
CARD_38B = {"boolq": (3000, 0.942, 0.872, 0.087), "rte": (277, 0.947, 0.877, 0.066),
            "fever": (1395, 0.953, 0.898, 0.061)}


def items() -> list[dict]:
    return [json.loads(line) for line in ITEMS.open()]


def read_one(model: decision.Decision, item: dict) -> dict:
    out = {"id": item["id"], "task": item["task"], "gold": item["gold"], "chars": len(item["state"])}
    started = time.time()
    out["noul"] = model.reader.answer(item["state"], {**item["question"], "type": "noul"})["logits"]
    out["seconds"] = round(time.time() - started, 3)
    if item["task"] == "fever":
        out["tfu"] = model.reader.answer(item["state"], {**item["question"], "type": "tfu"})["logits"]
    return out


def ask(limit: int | None, workers: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    done = {json.loads(line)["id"] for line in READS.open()} if READS.exists() else set()
    todo = [i for i in items() if i["id"] not in done][:limit]
    print(f"{len(done)} cached, {len(todo)} to read", flush=True)
    model = decision.Decision(ttl=60)
    failed = 0
    with ThreadPoolExecutor(workers) as pool, READS.open("a") as out:
        for n, (item, future) in enumerate(zip(todo, [pool.submit(read_one, model, i) for i in todo])):
            try:
                out.write(json.dumps(future.result()) + "\n")
                out.flush()
            except Exception as wrong:  # noqa: BLE001 - a row lost is counted, not fatal
                failed += 1
                print(f"  {item['id']}: {str(wrong)[:120]}", flush=True)
            if n % 250 == 249:
                print(f"  {n + 1}/{len(todo)}", flush=True)
    print(f"read {len(todo) - failed}, failed {failed}", flush=True)


# --- the card ------------------------------------------------------------------------------------

def _auc(scores: list[float], positive: list[bool]) -> float:
    ranked = sorted(zip(scores, positive))
    pos = sum(positive)
    neg = len(positive) - pos
    rank_sum, i = 0.0, 0
    while i < len(ranked):
        j = i
        while j < len(ranked) and ranked[j][0] == ranked[i][0]:
            j += 1
        mid = (i + j + 1) / 2                      # ties share the mean rank
        rank_sum += mid * sum(p for _, p in ranked[i:j])
        i = j
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def _ece(conf: list[float], ok: list[bool]) -> float:
    bins = [[0, 0.0, 0] for _ in range(10)]
    for c, k in zip(conf, ok):
        b = bins[min(9, int(c * 10))]
        b[0] += 1
        b[1] += c
        b[2] += k
    return sum(abs(b[1] - b[2]) for b in bins) / len(conf)


def report() -> None:
    reads = [json.loads(line) for line in READS.open()]
    t = {mode: decision.fitted_for(decision.CALIBRATION, decision.MODEL).get(mode, {}).get("temperature", 1.0)
         for mode in ("noul", "tfu")}
    lines = ["| benchmark | rows | AUC | accuracy @0.5 | calibration error | TypeCastLM 3.8B (AUC / acc / ECE) |",
             "|---|---|---|---|---|---|"]
    result = {"model": decision.MODEL, "temperatures": t, "tasks": {}}
    for task, name in (("boolq", "SuperGLUE BoolQ"), ("rte", "SuperGLUE RTE"),
                       ("fever", "FEVER (NLI form), decidable rows")):
        rows = [r for r in reads if r["task"] == task and r["gold"] != "unsure"]
        if not rows:
            continue
        d = [r["noul"]["true"] - r["noul"]["false"] for r in rows]
        yes = [r["gold"] == "yes" for r in rows]
        p = [1 / (1 + math.exp(-x / t["noul"])) for x in d]
        ok = [(q > 0.5) == y for q, y in zip(p, yes)]
        auc, acc, ece = _auc(d, yes), sum(ok) / len(ok), _ece([max(q, 1 - q) for q in p], ok)
        ref = CARD_38B[task]
        lines.append(f"| {name} | {len(rows)} | {auc:.3f} | {acc:.3f} | {ece:.3f} | "
                     f"{ref[1]:.3f} / {ref[2]:.3f} / {ref[3]:.3f} |")
        result["tasks"][task] = {"rows": len(rows), "auc": round(auc, 3), "accuracy": round(acc, 3),
                                 "ece": round(ece, 3)}
    fever = [r for r in reads if r["task"] == "fever" and "tfu" in r]
    if fever:
        z = [r["tfu"] for r in fever]
        unsure = [r["gold"] == "unsure" for r in fever]
        auc_u = _auc([x["unsure"] - max(x["true"], x["false"]) for x in z], unsure)
        name_of = {"yes": "true", "no": "false", "unsure": "unsure"}
        right = 0
        for x, r in zip(z, fever):
            p3 = softmax(x, t["tfu"])
            right += max(p3, key=p3.get) == name_of[r["gold"]]
        result["fever_third"] = {"rows": len(fever), "unsure_auc": round(auc_u, 3),
                                 "three_class_accuracy": round(right / len(fever), 3)}
        lines += ["", f"FEVER, third answer: unsure AUC {auc_u:.3f} (TypeCastLM 0.771), three-class "
                      f"accuracy {right / len(fever):.3f} (TypeCastLM 0.698), {len(fever)} rows."]
    # Speed: one noul decision, both orders, by the length of the material (about four chars a token).
    speed = ["", "| material | reads | p50 | p90 |", "|---|---|---|---|"]
    for label, lo, hi in (("under 200 tokens", 0, 800), ("200–1000", 800, 4000), ("1000–4000", 4000, 16000)):
        s = sorted(r["seconds"] for r in reads if lo <= r["chars"] < hi)
        if s:
            speed.append(f"| {label} | {len(s)} | {s[len(s) // 2]:.2f} s | {s[int(len(s) * 0.9)]:.2f} s |")
            result.setdefault("speed", {})[label] = {"p50": s[len(s) // 2], "p90": s[int(len(s) * 0.9)]}
    lines += speed
    (OUT / "card.json").write_text(json.dumps(result, indent=1))
    (OUT / "card.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["ask", "report"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    ask(a.limit, a.workers) if a.what == "ask" else report()
