# The field around us, September 2026

A survey of where personal-agent memory actually stands, written to answer three questions:
what the field is converging on, where this project is genuinely ahead, and what we do not
express at all — including with tags and meaning search, which were finished this week. It also
states, because the survey makes it unavoidable, what kind of thing this is: not *just* a memory
mechanism. Memory's functions are ours as well — but memory is a larger thing than a key-value
store with clever rules for writing and reading, and doing it properly is most of why the rest
of the world exists.
Companion to [related-work.md](related-work.md), which covers the literature behind our three
hardest problems; this one covers the products and the direction of travel.

Sources are linked inline. Everything below was read in September 2026; the field moves fast
enough that a number without a date is worthless.

## 1. What the field is converging on

**Memory is now a layer with a market.** [Memory Atlas](https://memoryatlas.dev/) catalogues 48
self-hostable memory frameworks — Mem0 (~55k stars), Letta (~22k), Zep/Graphiti, Supermemory,
Cognee, MemOS — grouped into six architectural families. The consensus across surveys is a
hybrid: a typed graph with bi-temporal provenance plus selective vector retrieval. A flat vector
store is no longer defensible on its own; "raw vector stores are fast but blind, pure graphs are
expressive but costly" is the standard framing.

**Bi-temporality is the de-facto standard.** Graphiti/Zep keeps two clocks on every edge (when
the fact was true, when we learned it) and never deletes: a contradicted fact has its validity
window closed and a new edge opened. That is the same commitment as our one axis of time, except
we also put periods on relations themselves and answer with `timeline()`.

**But the bottleneck turned out to be assembly, not storage.** *Don't Ask the LLM to Track
Freshness* ([arXiv:2606.01435](https://arxiv.org/abs/2606.01435)) measured conflict resolution on
MemoryAgentBench's FactConsolidation task, where the rule ("higher serial is newer") is stated
outright: Zep/Graphiti scores **7%** on single-hop, Mem0 18%, BM25 48%, HippoRAG-v2 54%.
Replacing LLM judgement in the answer pipeline with candidate extraction plus a deterministic
`max(serial)` adds +10.8 points and reaches 78% (gpt-4o-mini) / 94.8% (gpt-4o); multi-hop is
near-unsolved at 7% across 22 systems. Storing the timeline correctly is not the same as
answering from it correctly.

**Ontology is coming back.** MOOSEDev ([arXiv:2608.13662](https://arxiv.org/abs/2608.13662),
NeSy 2026) gives coding agents typed records with lifecycle status, provenance and supersession
links over MCP: on supersession, set-completeness and negation questions it returns 0.98–1.00 of
the expected answer set where a production vector memory surfaces 6–27%. Relevance recall and
token cost came out equivalent — the gain is entirely in the question types where structure is
the answer.

**Someone has published our architecture.** WorldDB
([arXiv:2604.18478](https://arxiv.org/abs/2604.18478)) builds a memory engine on three
commitments: every node is a *world* with its own interior subgraph and ontology scope; nodes are
content-addressed and immutable, so an edit produces a new hash and a Merkle-style audit trail
for free; and edges are write-time programs — `supersession` closes validity, `contradicts`
preserves both sides, `same_as` **stages a merge proposal** rather than merging. There is no raw
append path. It reports 96.4% on LongMemEval-s. This is the closest published relative of our
statements → assembly → images design, and the overlap is worth knowing about before a judge
finds it for us. Where we differ: their reconciliation happens at write time and the node is the
unit; ours happens in assembly over statements that keep their subject, so the *rule* can change
and the world is rebuilt from what was actually said.

**Governance is the unclaimed layer.** The clearest statement of the landscape is
[Personal Agentic OS](https://htdocs.dev/posts/personal-agentic-os-who-will-own-the-personal-knowledge-layer)
(July 2026): the format converged (Karpathy's LLM-wiki pattern, then Google Cloud's Open
Knowledge Format — markdown plus frontmatter, cross-links as the graph); capture went passive
(Rowboat grows an entity vault out of Gmail, calendar and Slack, and creates an entity only once
enough evidence has accumulated); editing went agent-native (Tolaria: "types are lenses, not
schemas", every vault a git repo with an MCP server and an `AGENTS.md`); the protocol layer
exists ([MacPaw portable-memory](https://github.com/MacPaw/portable-memory), cross-tool memory
over MCP). What nobody has an incentive to standardise is what happens to knowledge *after*
capture: who resolved the contradiction, what is forgotten, on whose authority. That is the layer
this project is built on.

**Proactivity and asking became an evaluation axis.** π-Bench
([arXiv:2605.14678](https://arxiv.org/abs/2605.14678)) scores 100 multi-turn tasks with hidden
intents, inter-task dependencies and cross-session continuity, and finds task completion and
proactivity are distinct capabilities. *Knowing but Not Showing*
([arXiv:2605.25284](https://arxiv.org/abs/2605.25284)) finds models recognise ambiguity and
still rarely ask. See also PROPER ([arXiv:2601.09926](https://arxiv.org/abs/2601.09926)) and
uncertainty decomposition for clarification
([arXiv:2606.19559](https://arxiv.org/abs/2606.19559)).

**Consolidation moved off the hot path.** Letta ships sleep-time compute — a
["dreaming" subagent](https://doc.holiday/library/letta/dreaming-and-reflection) sharing memory
blocks with the primary agent, which deduplicates, invalidates and writes learned context between
turns. Decay mechanics (FSRS-6, Ebbinghaus half-lives) are common in the hobbyist end of the
ecosystem.

**The write path is an attack surface.** MINJA reports a 98.2% memory-injection success rate
using nothing but ordinary user messages, with LLM detectors missing 66% of poisoned entries;
content-only screening has a measured ceiling, and provenance-weighted retrieval is the defence
that survives scrutiny ([arXiv:2608.21230](https://arxiv.org/abs/2608.21230)).

**Benchmarks are rotting.** *Ground Truth First*
([arXiv:2607.21962](https://arxiv.org/abs/2607.21962)): 6.4% audited label errors in LoCoMo's
answer key, real-world entities that leak to pretraining (frontier models answer 70–85% from
priors), saturation at the top of leaderboards, and histories short enough that full-context
answering is still competitive — and, most usefully for us, a **tenure crossover**: which memory
architecture ranks first depends on how long the agent has been running. Newer instruments:
LongMemEval, BEAM, MemGym, π-Bench, MCP-Persona
([arXiv:2606.02470](https://ar5iv.labs.arxiv.org/html/2606.02470)), FinPerMA
([arXiv:2608.04095](https://arxiv.org/abs/2608.04095)).

**Code instead of tool calls is becoming mainstream.** CaveAgent
([arXiv:2601.01569](https://arxiv.org/abs/2601.01569)) reframes the model as a runtime operator
over a persistent Python environment; programmatic tool calling keeps intermediate data in the
sandbox instead of the context. The bet we made a year ago is no longer contrarian, which is good
for the world's ergonomics and bad for it as a differentiator.

## 2. Not just memory — and memory is more than a store

Everything in section 1 is filed under memory: extract facts, embed them, retrieve them when
they look relevant, keep the timeline straight. That is storage with clever rules for writing
and reading. If this project is filed beside it, it gets compared on recall@k against systems
that do nothing else.

The answer is not that we are not memory. We owe every function memory owes: remembering what
was said, returning it when it is wanted, keeping it true as it ages. That duty is not up for
negotiation, and a world that fails it is not interesting. The point is that memory itself is
bigger than the category makes it. Remembering a life means deciding what is worth keeping,
holding two accounts of the same thing until one of them settles, knowing where each piece came
from and how much it is worth, forgetting on purpose, and — the part nobody in a store can do —
changing the shape of what is kept as the life changes shape. A store with a fixed schema and a
similarity function drifts away from the person it describes within a year.

So the mechanisms below are not extras bolted onto a memory; they are what memory needs in order
to stay true over years:

- **It grows its own schema.** A class gains an attribute when the evidence says it should
  (`growth.py`, `ontology/grown/`, [schema-growth.md](schema-growth.md)); a relation label used
  often enough is a missing relation type with characteristics to be settled
  ([architecture.md](architecture.md), `properties.py`). A memory layer's schema is whatever the
  extractor happened to emit.
- **It concludes, and says on what basis.** `facts.conclude()` writes the world's own inferences
  into `reasoning_*` tables, ranked below anything a person said and retractable one at a time.
  Judgement is a recorded, weakest-source statement rather than a hidden summary.
- **It keeps procedures**, not only facts ([procedural-memory.md](procedural-memory.md)): how
  this person does a recurring thing, attached to the class it belongs to.
- **It models dynamics rather than logging them.** Validity periods live on entities *and*
  relations; `until` / `ttl` / `expire()` say in advance that a fact is expected to stop holding;
  overlap of periods, not "now", decides conflicts; a current read that hides an ended relation
  emits a hint. The world is a state that moves, with the movement written down.
- **It reaches outside itself.** `lookup.py` permits a query about a public thing — a car model,
  a company, a place — or anything the person asked about, never about a person in this world,
  and what comes back is statements carrying the page as their source and an "as of".
- **It notices and proposes.** `ticks.py` finds what has gone stale, what was said twice, which
  tags have drifted; `assembly.unsettled()` reports identities that cannot be settled without
  help; open questions hold a doubt on the entity until somebody answers it.

Statements with sources, periods and reversible assembly are exactly what memory needs, which is
why this does memory well. But the thing being built is a governed, self-structuring model of a
person's world, and the honest comparison set is
[personal world models](https://emergentmind.com/topics/personal-world-models) and the governance
layer of the personal knowledge stack — with Mem0 and Zep as one capability inside it, not as
peers.

The part of "world model" we cannot yet claim is consequence prediction: state plus a candidate
action giving a predicted next state, and refusing to act when the prediction is unacceptable
([self.md](https://self.md/concepts/jepa-world-models) draws the ladder as memory / state / world
model / planner / guardrails). We model observed dynamics and anticipated staleness; we do not
model what happens if the agent acts. Worth naming precisely, because everything else on that
ladder is already here.

## 3. Where we are genuinely ahead

- **Statements → assembly → images.** The record keeps what was said; images are derived and
  disposable. `rebuild()` is idempotent, so the assembly *rule* can change and the world is
  rebuilt from evidence. Mem0 ingests ADD-only with no update or delete path; most products write
  destructively. WorldDB gets immutability but reconciles at write time, so its rule is baked in.
- **A merge is reversible** because statements stay with the subject they were made about
  (`subject_id`). Elsewhere a merge is either destructive or, at best, a proposal.
- **Sources are ranked** — the assistant, a named source, the world's own conclusions, weakest —
  which is provenance-weighted defence built in rather than bolted on after a poisoning paper.
- **Uncertainty is an outcome, and doubts live on the entity.** One standing reading for every
  host, `[ask first]` exactly when the current read depends on the doubt, and a sweep at the end
  of a task. That is query-driven repair plus defer-to-breakpoint, implemented. No product
  surveyed does this: they either merge silently or interrupt at the wrong moment.
- **Relation types carry characteristics checked in code** — cardinality, functional at a point
  in time, symmetry, acyclicity — rather than a label on an edge.
- **The world is a service, not a context dump.** One MCP tool, the host never sees raw data.
  The field is arguing about exactly this (memory silos, portability, "a memory you can see");
  most implementations still spill fragments into the prompt.
- **We measure honestly**: pass^k, world versus baseline with the same host, instability tracked
  as a metric rather than excused. Against the benchmark rot above, this is defensible.

## 4. Tags and meaning search: what they express, and what they do not

What is already right: a tag is held in one form while the statement keeps it as typed (the same
arrangement as an email address); tags are statements, so they carry **time and source** and read
through `holding(at=)` / `any_time`; usage is counted with every spelling kept visible; review is
triggered by growth rather than by the calendar; `merge` / `untag` / `tagged_all` are ordinary
reversible writes; `look_alike` proposes and never decides. Meaning is an index, never a source,
and takes no part in identity. All of that is stronger than the usual flat list of strings.

What they do not express:

1. **No hybrid retrieval.** `like()` is dense cosine over a full table scan, with a synchronous
   `refresh()` on every query. The field's consensus is BM25 + dense + graph traversal fused
   (RRF). We have no lexical branch and no rerank, so an exact-word question — a model number, a
   surname in a note — is answered by similarity or not at all.
2. **Meaning composes with structure, as of 2026-09-21.** `selecting.where()` narrows by
   attributes, links, tags and meaning in one call, with the class optional, `at=` for a moment
   and `closeness=` as the threshold on the meaning score. This was the gap; it is now the door,
   and `like()` should stay a scorer rather than grow filters of its own.
3. **No number on it.** We measured that clustering remarks by embedding does not work (0.46–0.61
   within a topic against 0.49 across topics) and acted on it, but recall@k of the search itself
   on our own scenarios is unmeasured.
4. **The folksonomy is flat.** No broader/narrower, no split (merge exists, its inverse by
   meaning does not), no polysemy handling, no vocabulary shared between worlds.
5. **No feedback loop.** What was found and turned out to be useful changes neither ranking nor
   tags; there is no decay of usefulness (comments expire, relevance does not).
6. **The proposals have no addressee.** `look_alike`, `due_for_review`, `written_several_ways`
   and `unsettled()` all produce work for somebody, and the agenda that would carry it
   (`agenda.db`) is designed but not built.

## 5. What we do not express at all

- **No passive capture.** The market ingests mail, calendar and transcripts; our world grows only
  through conversation. Our evidence threshold for creating an entity is better than Rowboat's,
  and there is nothing flowing into it.
- **No proactivity as behaviour.** `ticks.py` notices; nothing carries what it noticed to the
  user. This is what π-Bench measures and what a judge perceives as intelligence.
- **No consolidation off the hot path.** `rebuild()` is synchronous; there is no background pass
  that deduplicates, ages and proposes schema.
- **No consequence prediction** (section 2): the world holds state and its dynamics, but not
  "what happens if the agent does X", and there is no gate that refuses an action whose predicted
  outcome is unacceptable. Irreversible effects are not modelled at all.
- **Scale is untested.** PerQA volumes, latency, tens of thousands of entities. `describe_world`
  is ~490 lines read before every task, and that cost is already visible in money.
- **No export format.** "Portable on a memory stick" is a claim; the format is our SQLite.
- **Nothing a human can look at.** "Show me what the world knows about me" is a live trend
  (ChatGPT moved to self-rewriting memory in June 2026 and lost line-level deletion, and was
  criticised for exactly that).
- **No external benchmark number.** We measure only our own scenarios.

## 6. What follows from this

Ordered by return on effort:

1. **Hybrid `like()`**: a lexical branch, filters by class / relation / period, and a threshold.
   Cheap, and it closes the gap where structure is supposed to beat vectors.
2. **Deterministic assembly for conflicts** wherever we still leave the choice to the model —
   the one measured +10-point result in the field, and it agrees with our own rule that a
   guarantee belongs in code.
3. **The agenda**, even minimal: review-due tags, look-alikes, unsettled identities and open
   questions in one list of tickets. Without it, half of what is built is unobservable.
4. **One external benchmark on a slice** — see below.
5. **Position it by what it is**: a governed, self-structuring model of a person's world —
   records, sources, reversible decisions, open questions, a schema that grows, procedures, a
   line to the outside. It owes memory's functions and should be tested on them; it is not
   another memory layer, and the comparison set in section 2 is the one to be judged against.

### On running an external benchmark

Not as a goal, and not a leaderboard entry: one calibration point against the field, on a slice.
The candidates are not equivalent:

- **MemoryAgentBench / FactConsolidation** is aimed straight at our strength — supersession and
  "which value holds now" — and everyone fails it (Zep 7%, Mem0 18%). Small, cheap, and the
  result is interpretable either way. It is synthetic (numbered serials), which makes it a test
  of the assembly step rather than of the world.
- **LongMemEval-s** is the number others quote, so it is the comparable one; it needs an
  ingestion path from transcripts that we do not have. That path is the same missing piece as
  passive capture, so the work is dual-use rather than wasted.
- **π-Bench / MCP-Persona** sit at the agent level, which is what we actually are, and are the
  heaviest to run.

A memory benchmark scores one face of this world. It is a face we are obliged to have — failing
it would be a real failure — but it scores recall over a transcript and says nothing about a
schema that grows, a doubt carried until it is answered, or a fact fetched from outside with an
"as of". That is a reason to run one small slice and stop, not a reason to skip it — the projection is where the field's numbers live, and
one comparable number buys credibility for the parts that have no benchmark yet. π-Bench and
MCP-Persona score the agent, which is closer to the real claim.

Whatever is chosen, it must be run in both modes — world and baseline, same host, same model —
because our claim is "the world makes the host better", not "our retrieval is state of the art".
And per *Ground Truth First*, a single benchmark number says less about us than the tenure
crossover it hides: our architecture is built for long-lived worlds, which is the regime those
benchmarks measure least.
