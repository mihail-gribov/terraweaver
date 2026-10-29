# 09 — Nemotron as the decision model

**The question.** Can Nemotron answer the world's closed questions itself — which class, which way a
link runs, does the text say this — with a probability per option that means what it says, so the
world depends on neither Jev (402) nor `typecastlm` (issue #1)?

**How it is asked** (`terraweaver/decision.py`). Options lettered, thinking off, one token out,
`top_logprobs=20`: the probability of each option is read from the first token, not generated.
Optionally each question is read twice, options as given and reversed, the two log-probabilities
averaged. One temperature per mode on top.

## Two sets of rows

- **bench** (`bench.py`): held-out splits of public datasets in the local HF cache, 60 a set —
  noul: BoolQ, RTE, FEVER, VitaminC, PAWS, StrategyQA, PubMedQA; tfu: CB, ANLI, WANLI,
  Climate-FEVER, ContractNLI; choice: ARC-Challenge, RACE, QuALITY, AG News; scale: SST-5 (300).
  MNLI is not in the cache. **Temperatures are fitted here**, on half, by calibration error, and
  reported on the other half.
- **world**: the questions the world itself asks, built by its own code over the 447 gold facts of
  `experiments/expected` — `check._asking` (says_so / backwards / not_in_it), "does the sentence
  say «S P O»" as noul, and as tfu with a turned-round and an unrelated claim. Measured, never
  fitted on.

## Running it

    .venv/bin/python experiments/09_decision/run.py ask bench     # ~2500 calls, ~3 min, cents
    .venv/bin/python experiments/09_decision/run.py fit bench --ship
    .venv/bin/python experiments/09_decision/run.py ask world
    .venv/bin/python experiments/09_decision/run.py fit world      # with the shipped temperatures

Raw letters are cached in `experiments/results/09_decision/<set>.jsonl`; `fit` is free to re-run.

## What it found (2026-10-26, Nemotron-3-Nano-30B-A3B)

Held-out half; accuracy is the same before and after the temperature, ECE is raw → fitted.

| mode | bench acc (both orders) | balanced | ECE | world acc |
|---|---|---|---|---|
| noul | 0.819 | 0.824 | 0.031 → 0.061* | **0.895** (one order 0.699) |
| tfu | 0.547 | 0.538 | 0.146 → 0.069 | 0.585 |
| choice | 0.842 | 0.853 | 0.103 → 0.077 | 0.521 (check._asking) |
| scale | 0.500 | 0.432 | 0.165 → 0.084 | — |

\* noul's temperature on all rows is 1.007, i.e. raw logprobs are already calibrated there.

- **The first letter wins.** On noul the option shown first wins 75% (bench) and 79% (world) of the
  time. Plain accuracy hides it — on bench one order and both tie at 0.819 — but one order catches a
  "no" 63% of the time and both 86%; on the world's questions 40% against 80%. Both orders are on
  in every mode (chosen by accuracy averaged over labels). Cost: two calls of ~0.37 s, side by side.
- **`unsure` is weak.** tfu catches "the text does not settle it" 21% of the time on bench, 11% on
  the world's set. Do not rest "leave it unread" on it alone yet.
- **`check._asking` cannot be answered as worded.** says_so wins 100%, not_in_it 0% — at any
  temperature. The says_so option ("…or it does not say which way round and this one is not
  against it") absorbs everything. The same claims asked as noul are 0.895. A wording problem in
  `formalise/check.py`, outside this experiment.
- **Calibration transfers loosely.** On the world's noul questions the model is right more often
  than on bench and the bench temperature leaves it underconfident (ECE 0.22; its own fit would be
  t≈0.25). Bench is what is shipped; the world set says how far to trust it.

## Any Nemotron (2026-10-27)

`--model` picks the Nemotron; its letters are cached per model and `fit --ship` writes its own entry
into `terraweaver/decision.json`, so `Decision(model=...)` reads it calibrated. Bench, held-out half,
both orders, accuracy:

| model | noul | tfu | unsure caught | choice | scale | s a call |
|---|---|---|---|---|---|---|
| Nano-30B-A3B | 0.819 | 0.547 | 0.21 | 0.842 | 0.500 | 0.37 |
| 3.5-Lightning | 0.867 | 0.730 | 0.57 | 0.867 | 0.533 | 0.24 |
| 3.5-Super-VL | 0.867 | 0.709 | 0.70 | 0.900 | 0.547 | 0.25 |
| 3-Super-120B | 0.871 | 0.750 | 0.79 | 0.883 | 0.540 | 0.39 |
| 3-Ultra-550B | 0.886 | 0.709 | 0.55 | 0.875 | 0.553 | 0.25 |

The first-letter lean is the Nano's: 75% first-place wins on noul, 45–53% on the others. Its weak
`unsure` is the Nano's too — every larger Nemotron catches "the text does not settle it" more than
half the time. The default stays the Nano until the user says otherwise.

## The link check as two claims (`check_links.py`)

After the finding above, `formalise.check` asks a claim-reading picker two noul questions per link —
said as written? said turned round? — and folds them into says_so / backwards / not_in_it. On 150
gold facts: as said 150/150 says_so, none refused; turned round 67% backwards, 52/120 refused at
`SURE_ENOUGH` 0.6; another fact's word 73% not_in_it (not acted on).

    .venv/bin/python experiments/09_decision/check_links.py --limit 150
