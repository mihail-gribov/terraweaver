# What is already known about the problems we hit

Three of our hardest problems are old problems with literature behind them: agents that give a
different answer on the second run, a knowledge base that must hold contradictions, and deciding
when to spend the user's attention on a question. This is what that literature says, what it
calls the things we built, and what we should change because of it.

## 1. Instability is the normal condition, and it has a metric

τ-bench (Yao et al., 2024, [arXiv:2406.12045](https://arxiv.org/abs/2406.12045)) introduced
**pass^k**: run each task n times and report the chance that *all* of k sampled trials succeed.
Its headline number is the point: gpt-4o scored ~61% pass^1 on retail and **under 25% pass^8**.
Our "7 of 15 scenarios flip between two attempts" is that same phenomenon, stated less precisely.

- **Adopt pass^k**, computed the unbiased way — for c successes in n trials,
  `pass^k = mean over scenarios of C(c,k)/C(n,k)` — not the `(c/n)^k` shortcut seen in blogs.
  Report pass^1 and pass^k side by side, with the error/rollback rate as a separate number.
- Part of the floor is not ours to fix: at temperature 0, batch-invariance in inference kernels
  alone produced 80 distinct outputs in 1000 completions
  ([Thinking Machines, 2025](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)).
- Single-run numbers are artifacts — *AI Agents That Matter*
  ([arXiv:2407.01502](https://arxiv.org/abs/2407.01502)) — which is the same conclusion we
  reached from our own reruns, and the reason the repeat readout exists.
- Before blaming the model, audit the scoring: the Agentic Benchmark Checklist
  ([arXiv:2507.02825](https://arxiv.org/abs/2507.02825)) found task and reward-design flaws that
  shift scores by up to 100% relative, τ-bench included. Our own EXPECT blocks deserve the same
  suspicion — an assertion that reads a question object rather than a result will "fail" for the
  wrong reason, which has already happened to us once.

**The interface moves the number.** SWE-agent's Agent-Computer Interface ablations
([arXiv:2405.15793](https://arxiv.org/abs/2405.15793)) are the strongest causal evidence we have
for the work we've been doing: same model, interface only — full 18.0%, **without the lint
guardrail on edits 15.0%**, with a full-file view 12.7%. Guarding a write *before it commits*,
with a message naming the violation, was worth three points. Code-as-action over JSON tool calls
is worth up to 20% success (CodeAct, [arXiv:2402.01030](https://arxiv.org/abs/2402.01030)) —
which is the design we already have. Self-repair, by contrast, is weak and bounded by feedback
quality ([arXiv:2306.09896](https://arxiv.org/abs/2306.09896)): better to make the first attempt
right than to add retry rounds.

**What this tells us to build:** a check that runs *before* the transaction commits and reports
every violation at once, rather than a run that dies on its first bad line and rolls the rest
back. Our error rate is 20–26% of runs, and a rolled-back run is exactly where two attempts of
the same task diverge. Savepoints — keeping the good statements of a run that failed late —
belong in the same conversation, against the atomicity rule that the user set deliberately.

## 2. Our contradiction machinery has established names

Everything in `docs/archive/questions.md` turns out to be a known mechanism. Using the standard names
costs nothing and buys the right to reuse their results:

| what we built | what it is called |
|---|---|
| taking inconsistent data and answering anyway | **inconsistency-tolerant / paraconsistent query answering** |
| "the later statement counts" as the standing reading | **preferred repair under a priority relation** (prioritized repairing, [Staworko et al.](https://arxiv.org/pdf/0908.0464)); as a semantics it is **brave**, not certain |
| a doubt attached to the entity, re-raised on contact | **nogood / contradiction node** in a truth-maintenance system |
| never merging identities silently, resolving later | **deferred merge, pay-as-you-go entity resolution** (dataspaces) |
| `starts`/`until` vs `created_at` | **bitemporal** (valid time vs transaction time) |
| closing a question from a reliable source | **truth discovery / source-accuracy fusion** |
| accepting the user's answer but not every claim | **credibility-limited revision** (non-prioritized belief revision) |

Three things they do better than we do:

- **A merge is a derived artifact, never a destructive edit.** The consensus across master-data
  management, Swoosh ([VLDB J. 2009](http://infolab.stanford.edu/serf/swoosh_vldbj.pdf)) and
  provenance work: keep source records, keep a link table with provenance and confidence, and
  compute the surviving record from the cluster. Un-merging is deleting a link. This is the
  answer to our open problem — an agent that answers its own identity question and leaves a
  duplicate should record a *proposed* `same_as` with provenance "agent", ranked below a
  user-confirmed one; a hard merge only on confirmation.
- **Swoosh's ICAR properties** (idempotent, commutative, associative, representative) make merge
  order-independent, so two agents merging in different orders converge — worth checking our
  merge against when we write one.
- **Deprecate, don't delete** ([Wikidata ranks](https://www.wikidata.org/wiki/Help:Ranking)): a
  superseded value keeps a machine-readable reason for its demotion. We already keep old values
  in history; the reason is what we don't record.

One warning worth taking seriously: possible-worlds databases (Trio, MayBMS) were technically
sound and failed in practice — query evaluation is #P-hard
([CACM 2009](https://homes.cs.washington.edu/~suciu/file16_cacm-paper.pdf)). A single standing
reading plus a recorded doubt is the pragmatic shape, and it is the one we chose.

## 3. When to ask: our policy is right in shape, wrong in its priority

The three moments have names, and two of them are well supported:

- ask when the pending read depends on the doubt = **query-driven repair**
  ([Bienvenu et al., IJCAI'16](https://hal-lirmm.ccsd.cnrs.fr/lirmm-01367864v1)) — repair only
  the contradictions that affect answers people actually ask;
- ask at the end of a task = **defer-to-breakpoint**
  ([Iqbal & Bailey, CHI'08](https://interruptions.net/literature/Iqbal-CHI08.pdf)). A 2026 study
  of developers with a proactive assistant found **52% engagement with post-commit suggestions
  against 62% dismissal mid-implementation** ([arXiv:2601.10253](https://arxiv.org/abs/2601.10253));
- silent identification with an `[assumed]` note = **implicit confirmation** on the grounding
  ladder (Paek & Horvitz, [UAI'00](https://arxiv.org/abs/1301.3883)).

What we got wrong: **priority by access count**. The established criterion is the expected value
of the answer — P(it changes an outcome) × consequence × future reads − cost of asking. SAGE-Agent
([arXiv:2511.08798](https://arxiv.org/abs/2511.08798)) implements exactly this with EVPI and
reports 1.5–2.7× fewer questions at higher coverage. Access frequency is only the third factor.

Both reviews converged on the same specific criticism of our design: **re-raising a doubt on
every contact with the entity is noise**. Raise it when the read depends on it (we have that),
batch the rest at the task boundary (we have that), and stop repeating the passive list in
between.

Two more worth having:

- a **fourth action** beside answer/act/ask: *report irreducible uncertainty*
  ([When2Call](https://arxiv.org/abs/2504.18851)). When neither a source nor recency can settle
  it, saying "two readings, unresolved" is the correct output, not another question.
- metrics that count the friction, not only the answers: turns-to-clarify and an
  efficiency-adjusted score ([ClarEval](https://arxiv.org/abs/2603.00187)), plus our own
  **wasted-ask rate** (asked, and the answer changed nothing) and **correction rate on
  `[assumed]` notes** — if nobody ever corrects an assumption, the note is noise and the
  threshold should loosen.

## 4. A schema that grows by measurement, not by judgement: EvoOntology

EvoOntology (Chong, Zhang, Fan, Du, Renmin U., Sept 2026,
[arXiv:2609.15779](https://arxiv.org/abs/2609.15779), PDF in [library/](library/),
[code](https://github.com/ruc-datalab/EvoOntology)) is the closest published system to the
shape we chose: an ontology served as an **MCP server** with a schema layer, a content layer and a
tool layer, which a data agent queries at runtime instead of reading from its prompt. Their
ontology is a map over data that lives elsewhere (tables, filings, CSVs); ours holds the data.
That difference is why they have no time, no provenance, no contradictions and no identity —
and why their numbers are not ours. What they have and we do not is a **measured loop** that
changes the ontology:

1. **Diagnose** — cluster failure signatures from agent trajectories.
2. **Attribute** — tag each signature with the one level it belongs to: content, tool or schema.
3. **Patch** — a typed edit at that level only, with a stated hypothesis.
4. **Gate** — candidate against parent on the same held-out set, same backbone, same budget;
   kept only if the gain reaches a margin. Rejected candidates are logged so they are not
   proposed again.

Every step was ablated (DDR-Bench, four backbones, trajectory-wise accuracy):

| removed | cost |
|---|---|
| gate (accept every patch) | −11.2 |
| attribution (edit any level, no hypothesis) | −6.3 |
| diagnose (edit from a random trace sample) | −4.8 |
| typed patch (free-form rewrite instead) | −1.7 |

And the object families of the content layer: masking Mappings (term → column and join path)
costs −13.4, Evidence (the probe query behind an entry) −8.7, Constraints −3.5, Relations −2.1.
Their rule follows: **no entry is committed on a natural-language description alone; each is
anchored in a probe that was actually run.**

### Principles of ours that now have someone else's experiment behind them

- **Knowledge behind a tool, not in the prompt.** The same semantic layer pasted into the
  context cost −15.0 on Claude-Sonnet-5 and −11.9 overall; exposed through two MCP tools it gave
  +8.8. Only a short manifest goes into the prompt. This is our "guarantee in the prompt is not a
  guarantee" from the reading side, and it says the host guide should stay a manifest, not a
  textbook.
- **The interface moves the number more than the content.** Tool-level edits (how the ontology
  is exposed) gave 57% of the accumulated gain, content 34%, schema 9% — the same finding as the
  SWE-agent ACI ablations in section 1.
- **One run measures nothing, so a change needs a gate.** Their gate is a paired, same-budget
  comparison on a held-out fold with a margin, and it is the single most valuable step. Our
  `pass^k` and repeat runs are the measurement; the gate — a schema change stays only if the host
  answers better with it — is what we have not built.
- **Grounded, not described.** Mappings and Evidence are the load-bearing families. Our version:
  a type is crystallised from counted shapes of free links, and a fact carries its provenance; a
  class description is not evidence.
- **Typed structure beats episodic replay.** ReAct + retrieved past trajectories: +6.3.
  EvoOntology: +20.0, "because episodic memory only replays what has been done and does not
  expose typed, composable structure". The citation for the position in
  [landscape.md](landscape.md#2-not-just-memory--and-memory-is-more-than-a-store).
- **Different hosts need different exposure.** Ontologies evolved for four backbones from the
  same start overlap at most 0.62 (Jaccard on term ids), and serving one backbone's store to
  another loses 6.6–10.9 points. Measure per host; a Haiku failure and a Sonnet failure are two
  data points, not one average.
- **Structure converges.** Terms grew 61 → 80 over five accepted rounds, under 5% per round after
  the third, flattening together with the score. A crystallisation step whose type count keeps
  growing is a bug, not progress.
- **Count the turns, not only the answers.** Per-turn context rose (3.2K → 4.1K input tokens)
  but turns per task fell 14.6 → 8.4 and total tokens −20%, with accuracy 69.5 → 89.5. The
  run-count metric planned for the runner is the right one.

### What is new to us

- **Attribute before fixing.** When a run fails, name the level — data, interface (API + guide),
  or schema — and state the hypothesis before touching anything. Without the tag their loop
  "makes content edits when the failure is a manifest problem, and vice versa"; that is what we
  do by hand after every Haiku run.
- **The interface is an editable level of the same loop.** Their evolution agent rewrites the
  manifest and tools, not only the content. Our host guide and API are tuned by hand and never
  measured as a candidate against a parent.
- **A logged rejection is a nogood for proposals.** We keep nogoods for contradictions; a
  rejected schema proposal deserves the same record, so the next session does not re-propose it.
- **The evaluation protocol**: two disjoint folds, 70% of the adaptation fold for building and
  30% for the gate, swap and average, ontology frozen before the held-out fold is touched. Cheap
  to copy onto our scenario pool when the gate exists.

## What we changed because of this

- `pass^k` is what the runner reports for repeated runs, with the rollback rate beside it.
- The passive `[open questions]` block no longer repeats on every contact: a doubt surfaces when
  a read depends on it, and once more as a batch when the task ends.
- `docs/archive/questions.md` and `docs/TODO.md` now carry the established names, so the next change
  starts from what is known rather than from scratch.

Still open, in order: a pre-commit check that reports all violations at once; a proposed-vs-
confirmed `same_as` link with provenance instead of a duplicate; EVPI-shaped ranking to replace
raw access counts; a gate for schema changes — a crystallised type or a grown attribute stays
only if the host scores better with it on a held-out slice, with rejections logged (section 4).
