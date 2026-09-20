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
