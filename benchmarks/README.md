# Benchmarks

**`scenarios.py`** is the scenarios benchmark, the one measure this repository carries: short
personal histories, one class of task each, told through the memory's own `say` on a fresh memory and
checked by words.

| Class | What the answer must do |
|---|---|
| latest | give the value that holds now |
| count | give the number |
| time | get the days, order, how long ago right |
| world | name the right person |
| recall | bring the right fact beside a new message nobody asked about (`/say`) |
| unknown | say the memory does not know, for what was never said |

A check passes when the answer holds every group of words (any one word of a group), so a reader
sees why it passed. Five stories (family, books, running, home, trips), 45 checks, each story on a
fresh memory of its own, all at once.

## Run it

Needs `NEBIUS_API_KEY` (the models are Nemotron on Nebius Token Factory). The web is off, so no
Tavily key. It takes a few minutes.

```bash
set -a; . ./.env; set +a
.venv/bin/python benchmarks/scenarios.py [--only family,books] [--port 7150]
```

It prints each check as `ok` or `MISS` with what the memory said, the pass count by class, and
the total.

## Check it

A run is kept under `benchmarks/runs/scenarios-<stamp>/`: per story the journal (`facts.md`), what was
heard and said back, the trace of every step, the graph, the tokens, and `results.json` with every
check and the answer it was scored on. The run in this repository, `scenarios-20261030-035627`,
scored 43 of 45; replay it with `scripts/replay.py`. The histories were seen during development, so
treat the number as tuned on them; the stories are in `scenarios.py`, and a new one is a dict
of talks and checks.

Runs differ: the models are not deterministic and one run measures little. Run it more than once.
