# Running public benchmarks

Why, which ones and in what order: [docs/benchmarks.md](../docs/benchmarks.md). This is the
how.

## Get the data

```bash
benchmarks/fetch.sh oracle   # LongMemEval oracle — evidence sessions only, 15 MB — start here
benchmarks/fetch.sh s        # LongMemEval_S — ~40 sessions per question, 277 MB
benchmarks/fetch.sh mab      # MemoryAgentBench — four competencies, parquet
```

Everything lands under `data/`, which is gitignored.

## Run

```bash
.venv/bin/python benchmarks/run.py --count 12                     # world, Haiku
.venv/bin/python benchmarks/run.py --count 12 --mode baseline     # same host, no world
.venv/bin/python benchmarks/run.py --count 6 --repeat 3           # pass^k, not one draw
.venv/bin/python benchmarks/run.py --count 6 --kinds knowledge-update,temporal-reasoning
```

Each question gets a world of its own (`--fixture ""`, so nothing is in it but `user` and
`agent`) on its own port, starting at `--port` and one per `--jobs`. Ports 7030+ by default, to
stay clear of the dev server (7000) and the scenario runner (7010–7029).

Results go to `benchmarks/results/<stamp>-longmemeval-<file>-<mode>-<model>/`: `config.json`,
`results.json`, the answer and verdict per question, and the full host transcript as JSONL.

## What a run actually does

1. An empty world per question.
2. Every session of that question's history, oldest first, one Claude Code turn each:
   *"It is <date>. Here is a conversation we had. Record in my world whatever it says about me
   and my life."* The host writes code against the world; in baseline mode it writes files.
3. The question in a fresh session, so the history is not still in context:
   *"Today is <date>. Answer from what you have recorded… if it does not answer it, say you
   don't know."*
4. A judge (`--judge`, Haiku by default) grades against the reference answer, with the
   LongMemEval rubric for temporal-reasoning, knowledge-update and preference questions.
   Abstention questions (`*_abs`, 30 of the 500) are graded by us: the answer must decline.

Both models go through the `claude` CLI, so a run needs no API key and is billed like the
scenario runs.

## Reading the result

`accuracy` is the headline, `by_kind` is what actually says something: knowledge-update is
supersession, temporal-reasoning is the time axis, single-session-user is plain retrieval and
the type we are most likely to lose. `cost_usd` and `turns` are reported because they are the
part a leaderboard hides, and `pass^k` because one draw is an artifact.

Every number carries its configuration — dataset, slice and seed, host model, judge, embedder,
commit — and `self_reported: true`, which is what it is until somebody else reproduces it.

## Honest limits, to state wherever a number is quoted

- The oracle file is evidence sessions only: it is the upper bound on retrieval, not the same
  task as `_s`.
- Recording is done by the host agent, so a bad run can be the host's fault rather than the
  world's — the transcripts are kept for exactly that reason.
- The judge is Haiku unless said otherwise, and a cheap judge is a real source of noise.

## What the first runs already showed (2026-09-21, oracle, Haiku, 2 knowledge-update questions)

Three findings, in the order they appeared — the first two were ours, the third is the world's:

1. **The host answered out of Claude Code's own memory.** Working in the shared temp dir, it
   inherited `~/.claude/projects/-tmp*/memory` from earlier scenario runs and answered a
   benchmark question with somebody else's life. Fixed: a folder per question, and the folder's
   memory is dropped after the run.
2. **"What you have recorded" is ambiguous to a host that has memory of its own.** It read
   `memory/MEMORY.md`, found nothing, and said it did not know — without ever calling the world.
   Fixed the way the scenario runner already does it: the prompt names the world (`Using my
   world (the terraweaver tools):`) or the folder, per mode, and in world mode file tools are
   disallowed outright.
3. **A changing preference went in as prose, so nothing superseded it.** Asked for the BBQ sauce
   the person is *currently* obsessed with, the world answered with the first one mentioned: the
   host had put both into `Person.descriptions` and a comment rather than into anything with a
   value that can change. Supersession cannot work on free text. This is the `Preference` gap in
   docs/TODO.md, now with a benchmark question attached to it.

The third one is the reason to run benchmarks at all: it is a real defect, found by an outside
question, in the exact place our own scenarios were not looking.

## FactConsolidation, first run (2026-09-21, sh/6k, Haiku, 20 questions)

**12/20 = 60%**, $3.83, 35 minutes (28 of them writing 455 facts in 19 batches, 434 host turns).
Published numbers on the same task: Zep/Graphiti 7%, Mem0 18%, BM25 48%, HippoRAG-v2 54%, and a
deterministic `max(serial)` recipe 78% (gpt-4o-mini) / 94.8% (gpt-4o). At n=20 the 95% interval
is roughly 39–78%, so the honest claim is "clear of the memory products, not yet separable from
the best method".

**Seven of the eight failures are the same failure**, and it is not retrieval: the world returned
the value that was stated *first* where a later fact overrode it — Microsoft's CEO (fact 85 then
188), the quarterback's sport (31 then 50), Japan's official language (240 then 439), Robert
Parish's position (330 then 334), the author of Sidereus Nuncius (124 then 401). The eighth was a
plain miss: "the author of The Marriage of Figaro" was recorded (fact 398) and not found.

**Why, from the world's own tables:** the host had nowhere typed to put these, so they went in as
prose — `Idea.title` with `Idea.descriptions` ("Quarterback position is associated with Muay
Thai"), and `Related.description` ("Robert Parish plays the position of quarterback"). Supersession
cannot work on prose: the two tellings sit side by side and the reader takes whichever it meets
first. The world absorbed 455 open-domain triples without refusing anything — it degraded into
text instead, which is worse than refusing, because it looks like it worked.

This is the same defect as the BBQ sauce in LongMemEval and the "Pilsner or Lager" that got
trimmed: **what will be asked about must be recorded as something that can change, not as a
sentence.** It is the `Preference` gap in docs/TODO.md, now with a number attached: fixing it is
worth roughly 35 points on this task.
