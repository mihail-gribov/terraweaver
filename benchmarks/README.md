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

## Experiment zero: a world with no classes (2026-09-21, sh/6k, Haiku, 20 questions)

**11/20 = 55%** against **12/20 = 60%** for the fixed class set — the same slice, the same host,
the same questions. At n=20 those are one number, not two. $4.82 and 45 minutes, against $3.83
and 35 for the fixed classes, so authoring the ontology is not expensive.

**The vocabulary converged, and fast.** Twenty classes defined in the first batch of 25 facts, one
more at batch ten, nothing after that — 430 further facts were recorded in words the host had
already chosen. What it built: `Person`, `Place`, `Organization`, `Work`, `Movement`,
`SportsTeam`, and fifteen relation types — `authored`, `born_in`, `died_in`, `citizen_of`,
`spouse`, `ceo_of`, `chairperson_of`, `director_of`, `educated_at`, `founded`, `founded_movement`,
`headquarters_in`, `located_in`, `worked_in`, `associated_with`. Recognisably an ontology, and
recognisably close to the one we wrote by hand.

**What got better is exactly what we predicted.** Four of the five supersession losses turned into
wins: Microsoft's CEO, the sport of the quarterback position, Japan's official language, what
Nobuhiro Watsuki is famous for. Typed values supersede; that part of the thesis held.

**What got worse is the other half, and it is a new finding.** Five questions the fixed classes
answered were lost, and none of them to supersession:

- *Ferdowsi is famous for Shahnameh* — not recorded at all. There is a `Work` and an `authored`,
  but "famous for" was not in the vocabulary by the time fact 86 arrived, and the fact was
  dropped rather than the vocabulary extended.
- *rugby union was created in England, then in India* — recorded as prose
  (`Place.descriptions: "rugby union was created here"`), so the later fact could not supersede.
  Worse, "rugby" exists in that world four times over: as a `Place`, an `Organization`, a `Work`
  and a `SportsTeam`. Nothing ties them together, because identity is declared per class and
  nothing looks across classes.
- *Meredith Grey was performed by Ellen Pompeo* — no relation type for performing; dropped.
- *Cédric Klapisch is a citizen of France, then of Malaysia* — `citizen_of` exists with 83
  statements, but the first value came back, so it was not declared to hold one at a time.

So: **the host froze its vocabulary after the first batches and then made the data fit**, by
dropping it, by writing prose, or by instantiating the same word as four different kinds of
thing. Convergence is what we hoped for; convergence this early is the failure mode.

Three things follow, and they are cheap:

1. The world should notice the reach for prose or the silent drop, and say so — a fact that fits
   nothing is a proposal to extend the vocabulary, not a fact to squeeze.
2. `over_time` (one holder at a time) should be asked about at definition, not defaulted away:
   `citizen_of` had the statements and still answered with the first one.
3. Identity has to look across classes, not only within one: four rugbies is a worse outcome than
   any wrong answer on this list.

## Experiment zero, second run (same slice, with `over_time` required and the anti-prose primer)

**10/20.** With the first blank run at 11/20 and the fixed classes at 12/20, that is three numbers
that say nothing: at n=20 each is worth ±20 points, and which questions they win keeps changing.
Reading single-run totals here is the mistake our own rules already forbid.

What *did* move is readable, because it is structural rather than statistical:

**The vocabulary was designed once again, and again it was richer than it needed to be.** Twenty-
four classes on the first twenty-five facts, then flat for 430 more: `Person`, `Place`,
`Organization`, `Work`, `Sport`, `Religion`, `Continent` plus seventeen relation types including
`plays_position`, `capital_of`, `married_to`, `founder_of`, `author_of`. The primer's instruction
to extend the vocabulary whenever something did not fit changed **what it defined up front** —
`Sport` and `Religion` are precisely the gaps that lost run one — and did not make it extend
later. A host designs an ontology once, at the beginning, from the first thing it sees.

That is the evening's sharpest lesson and it is one we have written down before: **a guarantee
that lives in the prompt is not a guarantee.** "Extend when something does not fit" is a rule the
world must provoke — by noticing, counting, and coming back with a proposal — not a sentence in
a brief.

**The coverage losses came back as wins**: Ferdowsi's Shahnameh, the quarterback's position,
Ellen Pompeo, where rugby union was created. Other questions lost instead. The kind of failure
keeps moving; the total does not.

**Prose share is the measurement worth keeping.** Counting what went into `descriptions`/`notes`
against everything said about a class — no sentence read, exactly the deterministic signal the
core refused to fake at write time:

| run | most prose-heavy classes |
|---|---|
| fixed classes | Person 0.49, Idea 0.27, Place 0.27, Organization 0.26, Related 0.25 |
| blank, first | SportsTeam 0.50, Person 0.41, Work 0.36, Organization 0.24 |
| blank, with the primer | Sport 0.42, Person 0.37, Work 0.33, Place 0.29 |

Half of everything said about a person under our own classes went into prose; under a host-built
ontology with the anti-prose primer it is a third. That trend is visible where accuracy is not,
and it is the number to track while the scores are this noisy.
