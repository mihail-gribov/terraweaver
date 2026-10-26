"""Labelled rows from the public datasets in the local Hugging Face cache, in the decision model's shapes.

Only held-out splits (validation or test with labels), never a split anything here was fitted on.
Read straight from the cached Arrow and Parquet files, so nothing is downloaded and `datasets` is not
needed. Each row: {"id", "mode", "data", "state", "asked", "label"} — `asked` is what
`Decision.read` takes, `label` an option name.

    noul    BoolQ, RTE, FEVER (nli_fever), VitaminC, PAWS, StrategyQA, PubMedQA
    tfu     CB, ANLI, WANLI, Climate-FEVER, ContractNLI   (MNLI is not in the cache)
    choice  ARC-Challenge, RACE, QuALITY, AG News
    scale   SST-5
"""
import ast
import glob
import json
import os
import random

import pyarrow as pa
import pyarrow.parquet as pq

CACHE = os.path.expanduser("~/.cache/huggingface/")
PER_SET = 60     # ~300 a mode over five sets; the split keeps every set on both sides


def _arrow(pattern: str) -> list[dict]:
    path = glob.glob(CACHE + "datasets/" + pattern)
    if not path:
        raise FileNotFoundError(pattern)
    return pa.ipc.open_stream(open(path[0], "rb")).read_all().to_pylist()


def _parquet(pattern: str) -> list[dict]:
    return pq.read_table(glob.glob(CACHE + "hub/" + pattern)[0]).to_pylist()


SAYS = "yes — the text says this, in those words or plainly the same thing"
DENIES = "no — the text says something that rules this out"
NOT_SAID = "no — the text does not say this"


def _claim(data, n, mode, text, claim, label):
    true, false = (SAYS, DENIES) if mode == "tfu" else (SAYS, NOT_SAID)
    return {"id": f"{data}-{n}", "mode": mode, "data": data, "state": f"Text: {text}",
            "asked": {"type": mode, "instructions": f"Does the text say: «{claim}»?",
                      "criteria": {"true": true, "false": false}},
            "label": label}


def _yes_no(data, n, text, question, label):
    return {"id": f"{data}-{n}", "mode": "noul", "data": data, "state": f"Text: {text}",
            "asked": {"type": "noul", "instructions": question,
                      "criteria": {"true": "yes", "false": "no"}},
            "label": label}


def _choice(data, n, text, question, options, answer, mode="choice"):
    names = [chr(97 + i) for i in range(len(options))]
    return {"id": f"{data}-{n}", "mode": mode, "data": data, "state": text,
            "asked": {"type": mode, "instructions": question,
                      "criteria": dict(zip(names, options))},
            "label": names[answer]}


NLI = {"entailment": "true", "contradiction": "false", "neutral": "unsure"}


def noul() -> list[dict]:
    out = []
    for n, r in enumerate(_arrow("aps___super_glue/boolq/*/*/super_glue-validation.arrow")):
        out.append(_yes_no("boolq", n, r["passage"], r["question"].capitalize() + "?",
                           "true" if int(r["label"]) == 1 else "false"))
    for n, r in enumerate(_arrow("aps___super_glue/rte/*/*/super_glue-validation.arrow")):
        out.append(_claim("rte", n, "noul", r["premise"], r["hypothesis"],
                          "true" if int(r["label"]) == 0 else "false"))
    for n, r in enumerate(_arrow("pietrolesci___nli_fever/default/*/*/nli_fever-dev.arrow")):
        if r["fever_gold_label"] in ("SUPPORTS", "REFUTES"):
            # nli_fever puts the claim in `premise` and the evidence in `hypothesis`.
            out.append(_claim("fever", n, "noul", r["hypothesis"], r["premise"],
                              "true" if r["fever_gold_label"] == "SUPPORTS" else "false"))
    for n, r in enumerate(_arrow("tals___vitaminc/default/*/*/vitaminc-test.arrow")):
        if r["label"] in ("SUPPORTS", "REFUTES"):
            out.append(_claim("vitaminc", n, "noul", r["evidence"], r["claim"],
                              "true" if r["label"] == "SUPPORTS" else "false"))
    for n, r in enumerate(_arrow("google-research-datasets___paws/labeled_final/*/*/paws-test.arrow")):
        out.append({"id": f"paws-{n}", "mode": "noul", "data": "paws",
                    "state": f"First: {r['sentence1']}\nSecond: {r['sentence2']}",
                    "asked": {"type": "noul", "instructions": "Do the two sentences mean the same thing?",
                              "criteria": {"true": "yes — the same meaning",
                                           "false": "no — the meaning differs"}},
                    "label": "true" if int(r["label"]) == 1 else "false"})
    for n, r in enumerate(_arrow("ChilleD___strategy_qa/default/*/*/strategy_qa-test.arrow")):
        out.append(_yes_no("strategyqa", n, r["facts"], r["question"],
                           "true" if r["answer"] in ("True", True) else "false"))
    for n, r in enumerate(_parquet("datasets--qiaojin--PubMedQA/snapshots/*/pqa_labeled/*.parquet")):
        if r["final_decision"] in ("yes", "no"):
            out.append(_yes_no("pubmedqa", n, " ".join(r["context"]["contexts"]), r["question"],
                               "true" if r["final_decision"] == "yes" else "false"))
    return out


def tfu() -> list[dict]:
    out = []
    cb = {0: "true", 1: "false", 2: "unsure"}
    for n, r in enumerate(_arrow("aps___super_glue/cb/*/*/super_glue-validation.arrow")):
        out.append(_claim("cb", n, "tfu", r["premise"], r["hypothesis"], cb[int(r["label"])]))
    anli = {0: "true", 1: "unsure", 2: "false"}
    for part in ("r1", "r2", "r3"):
        for n, r in enumerate(_arrow(f"facebook___anli/plain_text/*/*/anli-test_{part}.arrow")):
            out.append(_claim("anli", f"{part}-{n}", "tfu", r["premise"], r["hypothesis"],
                              anli[int(r["label"])]))
    for n, r in enumerate(_arrow("alisawuffles___wanli/default/*/*/wanli-test.arrow")):
        out.append(_claim("wanli", n, "tfu", r["premise"], r["hypothesis"], NLI[r["gold"]]))
    cf = {0: "true", 1: "false", 2: "unsure"}          # 3 is DISPUTED: no gold, left out
    for n, r in enumerate(_arrow("climate_fever/default/*/*/climate_fever-test.arrow")):
        if int(r["claim_label"]) in cf:
            evidences = r["evidences"]
            evidences = ast.literal_eval(evidences) if isinstance(evidences, str) else evidences
            text = " ".join(e["evidence"].strip('"') for e in evidences)
            out.append(_claim("climate_fever", n, "tfu", text, r["claim"], cf[int(r["claim_label"])]))
    cn = {"Entailment": "true", "Contradiction": "false", "Not mentioned": "unsure"}
    for n, r in enumerate(_arrow("urialon___converted_contract_nli/default/*/*/converted_contract_nli-validation.arrow")):
        claim, _, text = r["input"].partition("\nText: ")
        out.append(_claim("contract_nli", n, "tfu", text, claim.removeprefix("Q: "), cn[r["output"]]))
    return out


def choice() -> list[dict]:
    out = []
    for n, r in enumerate(_arrow("allenai___ai2_arc/ARC-Challenge/*/*/ai2_arc-test.arrow")):
        choices = r["choices"] if isinstance(r["choices"], dict) else ast.literal_eval(r["choices"])
        if r["answerKey"] in choices["label"]:
            out.append(_choice("arc", n, "A science question.", r["question"], choices["text"],
                               choices["label"].index(r["answerKey"])))
    for n, r in enumerate(_arrow("ehovy___race/high/*/*/race-test.arrow")):
        options = r["options"] if isinstance(r["options"], list) else ast.literal_eval(r["options"])
        out.append(_choice("race", n, r["article"], r["question"], options, "ABCD".index(r["answer"])))
    for n, r in enumerate(_arrow("emozilla___quality/default/*/*/quality-validation.arrow")):
        options = r["options"] if isinstance(r["options"], list) else ast.literal_eval(r["options"])
        out.append(_choice("quality", n, r["article"], r["question"], options, int(r["answer"])))
    topics = ["world news", "sports", "business", "science and technology"]
    for n, r in enumerate(_arrow("fancyzhx___ag_news/default/*/*/ag_news-test.arrow")):
        out.append(_choice("ag_news", n, r["text"], "What is this news item about?", topics,
                           int(r["label"])))
    return out


def scale() -> list[dict]:
    levels = ["very negative", "negative", "neutral", "positive", "very positive"]
    return [_choice("sst5", n, r["text"], "How positive is this review?", levels, int(r["label"]),
                    mode="scale")
            for n, r in enumerate(_arrow("SetFit___sst5/default/*/*/sst5-test.arrow"))]


def rows(seed: int = 9, per_set: int = PER_SET) -> list[dict]:
    """A balanced sample: `per_set` rows from each dataset (all of it where it is smaller)."""
    rng, out = random.Random(seed), []
    for mode, load in (("noul", noul), ("tfu", tfu), ("choice", choice), ("scale", scale)):
        loaded = load()
        for data in sorted({r["data"] for r in loaded}):
            mine = [r for r in loaded if r["data"] == data]
            n = per_set * 5 if mode == "scale" else per_set
            out += rng.sample(mine, min(n, len(mine)))
    return out


if __name__ == "__main__":
    import collections

    got = rows()
    print(len(got), json.dumps(collections.Counter(f"{r['mode']}/{r['data']}" for r in got), indent=1))
