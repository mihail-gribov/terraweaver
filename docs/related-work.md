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

Everything in `docs/questions.md` turns out to be a known mechanism. Using the standard names
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

## What we changed because of this

- `pass^k` is what the runner reports for repeated runs, with the rollback rate beside it.
- The passive `[open questions]` block no longer repeats on every contact: a doubt surfaces when
  a read depends on it, and once more as a batch when the task ends.
- `docs/questions.md` and `docs/TODO.md` now carry the established names, so the next change
  starts from what is known rather than from scratch.

Still open, in order: a pre-commit check that reports all violations at once; a proposed-vs-
confirmed `same_as` link with provenance instead of a duplicate; EVPI-shaped ranking to replace
raw access counts.
