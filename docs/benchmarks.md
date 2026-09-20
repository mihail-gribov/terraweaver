# Public benchmarks: which ones, in what order, and how they get run

The reason is judging (1–15 Dec): a judge should not have to take our word that the thing works.
One comparable public number does that argument for us, and the methodology around it (both
modes, pass^k, full config) is itself evidence of how the project is built.

The caveat from [landscape.md](landscape.md) §2 holds: a memory benchmark scores one face of this
world. It is a face we are obliged to have, so the number must be good — but the submission says
plainly what it does and does not cover.

## What has to exist first: an ingestion path

Confirmed with the other session working this repo on 2026-09-21: nothing of this exists yet,
and `benchmarks/` is free. `scenarios/run.py` drives a live MCP host and scores against per-
scenario EXPECT/PROBES — worth reading before writing a runner, and not to be bent into an
ingestion path.

Every memory benchmark hands over a transcript; our world is written by a host agent. So one
component is needed before any of them can run: `benchmarks/ingest.py`, sessions in
chronological order → statements, with the session as the source and its timestamp as the
statement's time, deduplicated the way repeats already are (`restated_at`). Two rules learned
from the field: extraction loses detail, so the session text is also kept verbatim as a dated
comment on the entities it touched; and nothing is written that the transcript does not support.

This is the same missing piece as passive capture (landscape §5), so the work is dual-use.

## The picks

### 1. LongMemEval (ICLR 2025) — the comparable number

- Data: HF `xiaowu0162/longmemeval-cleaned` — `_oracle`, `_s_cleaned` (~40 sessions, ~115k
  tokens), `_m_cleaned` (~500 sessions, ~1.5M). 500 questions; types: single-session
  user/assistant/preference, multi-session, temporal-reasoning, knowledge-update, abstention.
- Why it fits: **knowledge-update** is supersession, which is what assembly does;
  **temporal-reasoning** is our one axis of time; **abstention** rewards saying "the world does
  not know", which is our rule rather than a bolted-on refusal.
- Order of running: `oracle` first (evidence sessions only — the retrieval-ablation upper bound,
  and it separates "we read it wrong" from "we did not retrieve it"), then a stratified subset of
  `_s`, then all of `_s`. `_m` only if the earlier numbers justify the spend.
- Points of comparison to quote next to ours: Mem0 ~93.4, Supermemory 85.2, WorldDB 96.4 — and a
  long-context stuffing baseline, which is mandatory because the benchmark predates 1M contexts.

### 2. MemoryAgentBench (ICLR 2026) — the one aimed at our thesis

- Data: HF `ai-hyz/MemoryAgentBench`, code `HUST-AI-HYZ/MemoryAgentBench`. Four competencies:
  Accurate Retrieval, Test-Time Learning, Long-Range Understanding, **Conflict Resolution**
  (EventQA and FactConsolidation are theirs). Corpora are chunked into incremental multi-turn
  injection — closer to how a world is actually written than a static corpus.
- Why it fits: on FactConsolidation every published system fails (Zep/Graphiti 7% single-hop,
  Mem0 18%, multi-hop ≤7% across 22 systems). Deciding which value holds now is exactly what
  statements plus assembly are for. Test-Time Learning touches the procedural side.
- Honesty requirement: report ours beside the deterministic recipe of
  [arXiv:2606.01435](https://arxiv.org/abs/2606.01435) (78% / 94.8% FC-SH), not only beside the
  memory products, so the win is against the best known method rather than the weakest.

### 3. π-Bench — the only public benchmark that scores what is uniquely ours

- Data and code: `Simplified-Reasoning/Pi-Bench`, HF `zzzhr97/Pi-Bench`
  ([arXiv:2605.14678](https://arxiv.org/abs/2605.14678)). 100 multi-turn tasks, 5 personas,
  persistent workspaces, hidden intents, cross-session continuity; proactivity is scored
  separately from task completion.
- Why it fits: "infers what it can, asks focused questions when needed, and carries those
  decisions through later turns" is a description of open questions, `[ask first]` and remembered
  name choices. Nothing else public scores that.
- Cost: agent-level, needs a host loop per task — heaviest of the three, therefore third.

### 4. PerQA — scale, not comparability

Already downloaded (`data/perqa/raw`, 20 personas, 793k events, 17.6k questions with SQL gold).
Not a leaderboard; a way to show the world holds at volume and to measure cost and latency per
answer, which every other number hides.

## Deliberately not run, and the submission says why

- **LoCoMo** — 6.4% audited answer-key errors, pretraining leakage, saturation
  ([arXiv:2607.21962](https://arxiv.org/abs/2607.21962)). Adding a number nobody should trust is
  worse than having one fewer number.
- **BEAM** (up to 10M tokens, ICLR 2026) — the right instrument for tenure, the wrong size for
  the weeks left and for 68 GB of free disk. Named as future work.
- **MemOps** (write-side operations, already downloaded) and **Veracium / Ground Truth First**
  (gold by construction, measures the tenure crossover) — the natural next step after the
  submission, and the better instruments for what we actually are.

## Local first

Nothing is bought until the harness is proven. Hardware here: one RTX 5060 Ti (16 GB), 188 GB
RAM, `bge-m3` already served by Ollama.

- **Stage A — free, local.** Build the harness and `ingest.py`; run 20–50 instances of
  `longmemeval_oracle` and the FactConsolidation slice with a local answerer (pull a ~8–20B
  instruct model that fits 16 GB) and `bge-m3` as the embedder. The goal is a correct pipeline,
  not a score: gold parsing, ingestion without loss, the answer contract, the judge's prompt.
  Local also means repeatable, so pass^k costs nothing but time.
- **Stage B — local answerer, paid judge.** Same slices, judging with a small hosted model, so
  the scores are trustworthy while generation stays free. This is where a number first means
  something and where the two known weak spots show up.
- **Stage C — reportable.** Nemotron through Nebius Token Factory as the answerer (which also
  satisfies the hackathon's runtime requirement), a fixed judge, world vs baseline on the same
  slice, and the full config on every row — backbone, embedder, retrieval, chunking, top-k —
  because a score without its config is noise (Memory Atlas's rule, and it is right).

## What must be built before Stage B means anything

1. **A lexical branch in `like()`** — `single-session-user` questions are pure retrieval and
   often hinge on an exact word (a model number, a surname in a note), which cosine alone will
   lose. Filtering and composition already exist in `selecting.where()` (attributes, links, tags,
   meaning, `at=`, `closeness=`), so `like()` stays a scorer: same `(entity, text, score)` shape,
   same score scale, or `where()` and `tags.look_alike()` break with it.
2. **Verbatim retention on ingest** — the session text as a dated comment, so an extraction miss
   is recoverable instead of fatal.
3. **An abstention path in the answer contract** — the world says it does not know, and the
   answerer is allowed to say so. LongMemEval scores this directly.

## How results get reported

Both modes (world and baseline), same host, same model, same slice. Config on every row. A
self-reported flag on anything of ours. pass^k rather than a single run
([related-work.md](related-work.md) §1). And a list of the questions we lost, with why — that
list is worth more to a judge than a percentage.
