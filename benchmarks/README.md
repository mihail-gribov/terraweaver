# Benchmarks

- **`scenarios.py`** — the scenarios benchmark: short personal histories, one class of task each
  (latest value, count, time, who is who, recall without a question, "never said"), told through the
  memory's own `say` on a fresh memory and checked by words. Results and what they mean:
  [README.md](../README.md#measured). Run:

  ```bash
  set -a; . ./.env; set +a
  .venv/bin/python benchmarks/scenarios.py [--only family,books] [--port 7150]
  ```

  A run is kept under `benchmarks/runs/<stamp>/`: per scenario the journal, what was heard and said
  back, the trace of every step, the graph, the tokens and `results.json`.

- **LongMemEval** — the public benchmark for a long personal history. `fetch.sh` downloads the data
  into `data/` (gitignored: other people's datasets), `longmemeval.py` loads it, `judge.py` grades
  with LongMemEval's rubrics (Claude Sonnet), and `experiments/14_longmemeval/run.py` runs the
  memory against the same model given every session. Only a slice of the `oracle` file has been
  run; LongMemEval_S, read entry by entry, takes hours and has not been run in full.

  ```bash
  benchmarks/fetch.sh oracle     # also: s, m, mab
  .venv/bin/python experiments/14_longmemeval/run.py --count 6 --mode memory
  ```

Why these and in what order: [docs/benchmarks.md](../docs/benchmarks.md).
