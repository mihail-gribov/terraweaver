# TODO

## Road to submission (set 2026-09-25)

Deadline 2026-10-30 10:00 PT. **Submit on 2026-10-28**, two days of margin. **Feature freeze on
2026-10-16**; after it, testing and fixes only. The testing window is two weeks because one run
measures nothing here — the spread between runs is as large as the differences we want to see, and
repeats cost time. Reasons for every decision below: `docs/decisions.md`, 2026-09-25, "the road to
submission".

| When | What | Done when |
|---|---|---|
| Sep 26 – Oct 2 | The loop end to end on the base world with a real host over MCP: the host says it in words, `formalise` reads it at the close, the host answers from what was recorded. A run on the FactConsolidation slice for a first number. `inspector.twins` moved out of the host's run (it can kill `define_relation` when the GPU is busy). A picker on Nemotron through Token Factory `logprobs` replaces Jev. Training of typecastlm on a Nemotron trunk starts in parallel. | the loop passes on the slice and the number is written down |
| Oct 3 – 9 | Research through Tavily: candidates go into a research world of their own through `formalise`, with the web page as the source and `check.py` verifying every attribute against it. The trained picker served from a Nebius AI Cloud GPU machine. | "pick it for me" runs from the request to sourced candidates |
| Oct 10 – 16 | The demo scenario, "where to go on Saturday". English README with a section on Nemotron, Token Factory and Nebius; licence; public repository; `facts` merged into `main`; first draft of the write-up. **Freeze.** | the repository can be handed to a stranger |
| Oct 17 – 30 | Testing only: pass^k on the scenarios and the slice, a "judge on a clean machine" run strictly by the README, fixes only. Video Oct 24–27. **Submit Oct 28.** | submitted |

**Waiting on the author:** a Tavily key (by week 2); access to Nebius AI Cloud for a GPU machine;
where the typecastlm training recipe lives (`typecastlm/package/scripts` has `export_head.py` and
conversion, not the training).

**After submission: apply for a Nebius AI Builder Program compute grant.** Announced 2026-10-19
(https://nebius.com/blog/posts/ai-builder-program-in-europe): compute grants for independent
developers, open-source builders, researchers and small teams in Europe, part of a $10M package
with NVIDIA and Accel (also VC introductions, hackathons, demo days). Areas named: open models,
coding agents, agent runtimes, inference tooling, post-training, RL, evaluations. The form is on
the Builder Program pages (dev.nebius.com/builders).

Ordered by what currently blocks progress. The focus is reading the world; write tasks are
deliberately parked (see below).

## Sorting what the user says (queued 2026-10-27, built 2026-10-28 in `memory/intake/`)

Agreed with the user, simple for now. The rewrite sees two messages, the agent's and the user's
after it — what came earlier the memory already holds. Prompts in `memory/intake/prompts/`.

1. **The decision model, on the last four messages:** anything personal, or a request? No — done.
2. **The big Nemotron (Super, thinking)**, the rewrite worded by the user: a new-topic flag; the
   message rewritten to stand alone, references resolved from the agent's message only, a word
   left as it is when the agent's message does not say what it means; the questions copied out.
   No agent's message before it — the message as said.
3. **Each question** by the decision model: the user's? Its kind: know or find, the memory, an
   action.

Measured 2026-10-28 on the three dialogues of `experiments/13_dialogues`, 16 hand checks, six
runs: 14, 16, 14, 13, 15, 14. Unsteady: "Which of those" gets the concert the agent named in 2 of
6 (the user: not critical); a question now and then not copied out.

Subtasks:
1. **Forget — left for later (the user, 2026-10-28); so is "don't keep this": personal data beyond the `SECRETS` regex is the agent's for now.** "Please forget everything about Olga" is
   reworded in 4 of 6 runs (once to "everything you told me about Olga", which narrows it) and
   not copied out as a request in 4 of 6.
2. **The personal gate's wording**, measured on a labelled set. Hard cases: a personal aside in a
   work task, work facts that are the user's life ("I started at Brightwork in March"), general
   questions with a personal reason, pasted text with a name in it. The three dialogues hold no
   work message, so the gate's "no" is untested.
3. **The new-topic flag**, measured on `data/contexts/history.py` against the embedding gap (F1
   0.73).
4. **A labelled set:** about 100 user messages, each with the agent's message before it, with what
   they hold; MemOps and LongMemEval through `memory/intake/sources.py`.
5. ~~**Into `say`**~~ — done 2026-10-28: `memory/listen.py` reads through the intake.

## Preparing by the user's interests (queued 2026-10-28, the world's — f8)

The user's questions are kept in `interests.jsonl` beside the journal (`memory/listen.py`):
`{"id", "asked", "by": "user", "at"}`, and `{"id", "asked_again"}` for each repeat. They are not
answered or searched for (docs/decisions.md, 2026-10-28). They should order what the world reads
and structures in the quiet: the texts a frequent or recent interest bears on first, so that the
agent's next `ask` about it finds them ready. Only what the memory holds; no web from here.
Measure: the same `ask` before and after the world prepared it — time and what it gives.

## The host's own web search beside the memory's (queued 2026-10-28, to think through)

`experiments/13_dialogues` turns the host's WebSearch/WebFetch off, so all finding goes through
`ask`. A real host has its own search. Open: does it search itself, ask the memory, or both; and
what it finds — a page the agent read — reaches the memory only through the user's answer.

## Cutting the journal into contexts, and joining a context across sessions (queued 2026-10-27)

What is said together should be read together: work with work, the cats with the cats, even when
both pass in one session, and a context left yesterday and taken up today is one context. Neither
a session nor a message is that unit, so neither is the truth to measure by. Material:
`data/contexts/` — `history.py`, 64 entries over 12 sessions in the agent's style, each tagged at
writing with its context (8: job, cats, flat, trip, health, vacuum, sister, running);
`contexts.py` measures on it; `topics.py` measured the same on the dialogue journals, by message.

Measured 2026-10-27 (bge-small, the vectors search already keeps beside the journal):
- **cut** where two neighbouring entries are less alike than 0.6: precision 0.71, recall 0.75 on
  the labelled history (0.84 / 0.72 against messages in experiments/13_dialogues). Work → cats is
  cut every time (0.35–0.43).
- **link** a fragment to the most alike earlier fragment: its own context 13/13. Embeddings rank well.
- **join** by a threshold ("same context, or new?"): pair F1 at most 0.68 — no threshold separates
  them; inside one context similarity drops to 0.43, across two it reaches 0.73.

To do: embeddings propose, the judge settles. Cut below 0.5, keep above 0.7, and ask the judge in
between: "does this entry go on the same conversation?". Join each fragment to its nearest earlier
one only when the judge says "it goes on that one". Measure on `data/contexts`, then on a second
history written apart. Then use it: the world reads by context instead of by size (`memory/world.py`,
f8's), a name's identity is judged against the contexts it was said in ("Tom" the flatmate and
"Tom Becker" the manager are in the labelled history on purpose), and a task gets its facts with
their contexts. Open: whether my own labels at the edges are right — knee pain after a run is
"running" or "health"?

**Each topic its own summary, kept apart** (the user, 2026-10-29). "We talked about this before" needs
no roles: it is knowing that a topic was taken up already, raising what it came to, and answering
with it. So each context, once cut and joined across sessions, gets a summary of its own, stored
beside the journal, and **kept up to date as the topic goes on**: a new entry joined to a topic
updates its summary (the summary so far plus what was just said — "we chose the ryokan in
Gion", "the trip moved to May"), so what the talk has come to is the latest; and now and then it
is rebuilt from all the topic's entries, so updates on updates do not drift. Derived like the
world's image, never written over the user's words: a wrong summary is rebuilt, not a memory
spoiled. What the assistant said in those talks is another subject (working with dialogues), not
this one.

## Skill tests: what the world must be able to do, with a real agent, three times each (queued 2026-10-05)

**Why the cardinality and the shadowing defects lived for weeks.**

1. *The unit tests carry the same assumption as the code.* Every test that touches supersession
   declares its own word — `base.word(rt, "plays_position", ..., cardinality="many-to-one")` — so
   it tests what the world does with a correct type, never which type the world makes. The
   decision that was wrong is made by the engineer, the picker or the host, and no model-free test
   can reach it.
2. *The benchmark's number aggregates over the failure.* 20 of the 26 unlimited sides were
   answered right because the host believed the "latest told first" hint, so the defect cost six
   answers in a slice and read as host noise. `wrong_answers.py` looks only at wrong answers; a
   world that holds the gold *beside* another value and gets lucky is invisible to it.
3. *The schema emerges in a real world only.* `Country.capital` beside `capital_of` exists only
   after the engineer grew both; no fixture has it, and no lint looked across the two.
4. *Full runs are rare and expensive*, and a 25-fact gate answers "does the chain run".

**What to build.** A pool of skill tests, one per thing the world must do, each the smallest story
that exercises it, run through the real chain (host over MCP, engineer, picker, the close) and
judged on **what the world holds**, not on the text of an answer — plus one question at the end
for the answering stage. Each run **three times** (pass^3, `benchmarks/run.py` already has
`pass_hat_k`), because a skill that holds one draw in three is not a skill. Cents per skill; the
pool is a gate before any full run.

First skills, each from a real loss:
- supersession at the object end: "The capital of X is A", later "... is B" → X holds B only
- supersession at the subject end: "H plays the position of A", later "... B"
- no supersession where several are normal: a second citizenship, a second language → both hold
- a word that is an attribute and a link: after the engineer grows `capital`, `x.capital` reads the link
- direction from a passive sentence: "S was performed by P" → P performed S, never the other way
- told order within one day: two tellings with the same date → the later stands
- identity across batches: a thing told in batch 1 and again in batch 3 → one thing, not a copy
- a fact on a failing line of a block → it is in the world when the task closes

**And free lints over every world a run writes**, so a defect of this shape shows in the first
gate: a declared attribute with the same word as a link reaching the class; a doubled side with no
`how_many` ruling; bare links still unread; copies of one name; questions in the asked shape
("as it stands now") where the world holds the gold beside another value — counted on right
answers too, not only wrong ones (the scratch scripts `sides.py` / `only_gold.py` of 2026-10-05
are the start of the last one).

## Read every prompt again, the engineer's and the checker's, one by one (queued 2026-10-05)

The author's request, after the cardinality defect: the example in `prompts.NO_WORD_YET` said
`mayor_of` is `many-to-one` — wrong (a city has one mayor at a time, so the limited end is the
object) — and an example is copied, not read, so the engineer and the host reproduced it on most
types they made. One wrong example cost the supersession of every "the X of Y is Z" fact.

Go through every prompt the world sends out, with the same suspicion, and check each against what
it is for and against the runs it produced (`readings`, `portraits`, `type_checks` in a world.db):

- the engineer: `A_LINK_SAID`, `NO_WORD_YET`, `THE_WORD_IS_HERE`, `WRITE_AGAIN`, `JOINED_NOTHING`,
  `WRITING`/`WRITE_ONE`, the portraits and namer prompts;
- the checker and the look: `IS_IT_SAID` and what `check.py` asks per attribute (87 of 211
  verdicts were `not_in_it` on the 250-fact world, sure 0.69 — are those right?), `WHICH_WORD`,
  `NONE_OF_THESE_IS`, `outside.ENDS_FRAME`;
- the host-facing ones that teach the same things: `describe.py`, the refusals in `relations.py`
  and `authoring.py` that carry an example call.

For each: is every example right, does it name a word no fact in sight needs, does it teach
something the world now decides itself (cardinality is the picker's since `how_many`), and does
the run data show it being copied.

## The recorder keeps fumbling the definition calls

Measured mid-run on 2026-09-24 (`dated455`, first eight batches). The host's calls to
`world.define` and `world.define_relation` fail on their own signature far more often than in
either earlier full run, and a type it failed to define is a link that never lands — which is
most of what the check reports as a missing fact.

| run | errors on `define*` | turns | per 1000 |
|---|---|---|---|
| `final455` | 60 | 6250 | 9.6 |
| `clean455` | 12 | 5995 | 2.0 |
| `dated455` | 48 | 1243 | **38.6** |

What they are: `define_relation() got multiple values for argument`, `define() missing 1
required positional argument: 'identified_by'`, `define() got multiple values for argument
'description'`. All three are the host mixing positional and keyword arguments — it passes the
name positionally and then names `description=` as well, or leaves out `identified_by`.

Neither `describe.py` nor `authoring.py` has changed since those runs (`git diff` is empty), so
this is not a regression in what the world teaches. Two things to separate before fixing
anything:

- whether it is spread evenly or sits on particular batches — the full run will say;
- whether it follows the date refusal. Refusals run at the same rate as before (47.5 per 1000
  against 46.2 and 39.2), but each one makes the host rewrite its block, and a rewritten block
  is where the signature goes wrong. Turns per batch are up too (155 against 136 and 130).

The fix is probably not a better sentence in the guide — [[terraweaver-working-principles]]:
enforce in code, not in the prompt. `define(name, description, identified_by)` taking its
arguments in an order the host keeps getting wrong is the world's problem to remove, by
accepting what it is given or by refusing in a way that says which argument is missing and
what to write instead.

## Jev on link direction: measured three ways, not connected

2026-09-24. With "the fact never landed" fixed, the top remaining error is a link written
backwards — three of six flags in a hundred-fact run, and a backwards link is worse than a
missing one: the world then asserts that Great Britain is London's capital. The user's framing
of the question is the right one and worth keeping: **semantic** correctness is not "is this
true" but "*can* this be so — is each end the kind of thing that belongs at that end", so
"Rome capital of Japan" is fine and "Japan capital of Rome" is not. **Substantive** correctness
is a separate question the world records and never acts on, because a fact may be refuted later
and a capital really does get moved.

Asked Jev (`jev-1.13.0`, TypeSafe systemone, `choice` questions) three ways over the links of
`fixed100`:

    plain English sentence      5/5 on a picked set, but rejects the benchmark's deliberate
                                falsehoods and mangles any `_by` / `_language` type name
    "can this be so at all"     9/12 — keeps absurd-but-possible 4/4, catches impossible 1/1,
                                catches reversed 1/4
    "which of A / B"            7/12 — catches some reversals and confidently inverts others

**Not connected, and the reason is the shape of the errors, not the average.** The wrong calls
come with p=0.93 (`Starship Troopers author Robert A. Heinlein` judged right way round) and
p=0.89 (`Andy Warhol founded by Chanel` judged right way round). Acting on a confident wrong
answer corrupts a correct link, which is worse than the error it was meant to catch. The
world's own majority rule found 13 candidates over the same links and is wrong only where no
majority exists yet — weak, but never confidently wrong.

**What did hold up**, and is worth wiring when there is a place for it: the substantive verdict.
17 of 115 links came back "contradicts what is generally known", and the list is almost exactly
the benchmark's superseding pairs — `quarterback associated with sport Muay Thai`,
`Japan official language Swedish`, `Frank Zappa died in Berlin`. As a remark on the link, with
`stating("world")` so the record says who said it, that is real information. As a refusal it
would throw away precisely the facts the benchmark exists to test.

Next, per the user: generalise from what the world has accumulated, and decide deterministically.
The majority rule is that in embryo — it reads `Person → Thing` against `Thing → Person` from
the links already written. What it lacks is the first few links of a type, which is where every
one of today's reversals was written.

## Where the twenty-two capitals actually went — and what is still open

Traced 2026-09-24, after two wrong diagnoses of my own. `capital_of` was defined in **batch
31–40**, not 221–230: only fact 27 predates it. The other twenty-one were lost while the type
existed, and the host knew it — in the session recording fact 104 it names `capital_of` 74 times
and reads `classes_here`. What it also hit, **eighteen times in that one session**, was
`AttributeError: CapitalOf has no 'subject'`.

So the chain is one bug, not a vocabulary problem: `retype` dropped the ends of two links →
every read of the type raised → the host could read nothing back about capitals and fell to
prose → twenty-two facts. **Two bad rows cost a type for the rest of the run.** Both halves are
fixed now (`retype` carries the ends; a read skips a link it cannot follow and says so), so the
next run is the measurement.

Still open, and not explained by any of this:

- **13 `citizen_of` losses.** `citizen_of` was defined in batch 241–250, so facts before it had
  no type — the prose story may be right *here*, where it was wrong for capitals. Unchecked.
- **8 capitals after the type existed** may be the same poisoning or may not; the count above
  does not separate them.
- **`official_language` and `famous_for` were never defined at all** in that run, so every fact
  under them had nowhere typed to go from beginning to end.

## A type that arrives late leaves everything before it in prose

2026-09-24, from the run that lost 22 capital facts. `capital_of` was not in the world when the
run began — the recorder defines its own vocabulary, which is the design working. It defined the
type at **turn 599 of 1143**, recording facts 221–230. Of the twenty-two capitals that never
became links, **fourteen arrived before that turn** and eight after.

The fourteen went into descriptions: Tokyo holds "the capital of Japan" and "the capital city of
Japan" and no link at all; New Delhi the same, twice over. That is the honest move when there is
no type — but `take_in` moves free *links* into a new type and nothing ever revisits a
description. So a fact written as prose before its type existed stays prose for good, and the
moment the recorder is most likely to reach for prose is exactly the moment when doing so is
permanent.

`finish_task` now refuses to close while a description this task wrote names another entity that
nothing joins to it (`_facts_hiding_in_prose`), which catches it at the one moment the host can
still act. What it does not do is go back over what is already there. Two things that would:

- when a type is defined, look at the descriptions that read like it and offer them, the way
  `take_in` offers free links. That is [[project-world-as-crystallizer]] applied to prose, and
  prose is where the structure actually accumulates first.
- `world.wanted()` already reports words written several times with no type behind them. It
  reads links; reading descriptions too would have named `capital_of` around fact 30 instead of
  fact 225.

## The word the recorder picks decides whether the fact can be answered

2026-09-24, two worlds built from the same 455 facts by the same recorder, asked the same
twenty questions (`benchmarks/ask_world.py`): `worlds/facts455` answered 17/20, the run made
today 15/20. The two grew **different vocabularies** — 32 types against 28, twelve words in one
that are not in the other — and the difference is not cosmetic. Two worked examples, both from
the questions that parted:

**Japan's official language.** Both worlds hold both facts, Swedish and Japanese, neither ended.

    facts455   OfficialLanguage  Japan -> Swedish, Japan -> Japanese    answered Swedish   ✓
    dated455   Speaks            Japan -> Swedish, Japan -> Japanese    answered Japanese  ✗

Same two statements, same order, opposite answer. `OfficialLanguage` was defined
`functional: True`, so the later telling holds at read time; `Speaks` was defined
`functional: False`, so both stand and the host picked the first. `Speaks` is also the type that
collects "a country's official language" and "a person speaks a language" — a type that answers
for several ideas answers for none of them, which the primer says in those words.

**Microsoft's chief executive.** A different failure wearing the same face.

    facts455   CEOOf       Steve Jobs -> Microsoft, Satya Nadella -> Microsoft   answered Jobs ✓
    dated455   Leadership  Satya Nadella -> Microsoft                            answered Nadella ✗

Here the superseding fact never landed at all — one of that run's 101 real losses. The host
answered correctly from what it had.

So a wrong answer to a conflict question has (at least) two causes that look identical from the
outside, and only reading the record tells them apart: **the fact did not land**, or **the fact
landed under a word that cannot supersede**. Any measurement of "conflict resolution" that does
not separate them is measuring the recorder's vocabulary and calling it the world's memory.

## A link whose end cannot be loaded breaks every read of that entity

Found while probing the above. `entity.relations()` raised:

    AttributeError: CapitalOf has no 'subject' — did you mean 'subject'?
                    It has: subject, object, descriptions, tags.

The message names the attribute as missing and as present in the same sentence, and the raise
takes down the whole call, so an entity with one broken link cannot have any of its links read.
Two `CapitalOf` links in `dated455` are in this state. Two things to fix: the link with an end
that no longer resolves (why it happens), and the read that dies on it (a link nobody can follow
should be reported, not thrown — an image is a reading of the record and a reading that cannot
be made should leave that one thing out, which is what `rebuild._fill` already does).

## A type defined not to supersede answers wrong forever

Found 2026-09-24 by asking `worlds/facts455` three questions with `benchmarks/ask_world.py`.
"What is Nobuhiro Watsuki famous for?" came back as a list of two — Rurouni Kenshin *and* The
Fairly OddParents — where the benchmark's answer is the later one. The world was right to say
both: the recorder defined `famous_for` with `over_time=False`, so the two accumulate and
nothing supersedes anything. The substring match scored it correct, which is how the whole
published table is graded, so the number hides it.

Of the 32 link types that run defined, 23 do supersede (14 `functional: True` — the latest
telling holds at read time; 9 `at_any_time` — a new start ends the previous one). Nine do not:

    AffiliatedWith  a place's religious affiliation      5 subjects hold several at once
    AssociatedWith  is associated with the sport of     17
    FamousFor       someone is famous for a work         3
    Speaks          speaks the language                  3
    EducatedAt      was educated at                      3
    Founded, Performed, Produced, WorkFieldOf

**The thing worth saying plainly:** in FactConsolidation every fact is a superseding fact by
construction — the benchmark injects conflicting updates and grades on the latest. So a type
defined `over_time=False` does not merely lose a little accuracy, it guarantees a wrong answer
for every fact recorded under it, and the recorder makes that decision once, early, from one
example. Seventeen subjects under `AssociatedWith` alone.

The guide already insists `over_time` be said and says why (`experiments/base_run.py`, PRIMER).
Saying it and saying it right are different things, and this is the second time a level-2
decision made from the first example has cost more than the fact it was made for — see the note
about `define_relation` above, and [[terraweaver-working-principles]]: attribute the failure to a
level first. Options, none decided:

- the world notices the shape: a subject that accumulates a third live link of a type whose
  earlier ones it never ended is a type worth asking about. `_too_many_handovers` already does
  this for the other direction, at `_HANDOVERS_BEFORE_ASKING = 3`.
- `over_time` stops being a definition-time answer and becomes one the world revises from what
  accumulates — which is [[project-world-as-crystallizer]] applied to a property rather than a
  type.
- nothing: the recorder is told plainly and gets it wrong, and that is a model result, not ours.
  Worth knowing which, and only a run with the question asked out loud can say.

## Two instances in every world: `user` and `agent`

Every world should hold two explicit instances: `user` — the person the world belongs to and
the host talks with — and `agent` — the assistant itself. Today the fixture has `owner` (a
Person) and `me` (an Agent persona); decide whether `user` / `agent` replace them or sit next
to them, and make them present in every world, not only in `job_search`.

## Debug the host–world loop

The world is served over MCP; the host agent writes code against the object model through
`describe_world()` and `run(code)`. Everything else — procedural memory
(`docs/engine/procedural-memory.md`), `remember`, `research`, `extend` — builds on this loop, so it
comes first.

## A scenario needs its own world, not the fixture underneath

`scenarios/run.py` starts every scenario's server with `--rebuild`, which loads `job_search`, and
then runs the scenario's SETUP on top. For the small scenarios that is a feature — there is
already a world to work in. For a scenario about something specific (s26, keeping a move
together) it means the checks keep tripping over entities nobody in the story ever mentioned: a
Job search project, an Anna Peterson, a dozen events.

What it wants: a scenario that says `FIXTURE = None` (or names its own), so SETUP builds the only
world there is. Small change to the runner, and it makes the scenarios that come next honest.

## Structuring what was written as prose

A remark is what the host writes when the class has no place for something — "allergic to
peanuts", "her son started school", "prefers mornings". The world should read those, notice when
the same *sort* of fact keeps coming back, and propose the attribute that is missing; then the
remarks can be read into it instead of sitting as prose.

The obvious way does not work, and it was measured rather than assumed: clustering short remarks
by embedding similarity. In bge-m3, remarks on one topic sit 0.46–0.61 apart while remarks on
different topics sit at 0.49 — no threshold separates them, and a schema proposal built on that
would be noise. Embeddings stay where they are good: retrieval, and finding what is plainly the
same thing said twice (`ticks.py`, *said-twice*).

What should do it instead: **the model names the kind** of each remark — "dietary", "family",
"work", "preference" — once per remark, kept with it like any judgement, with its basis. Then
counting kinds is arithmetic, and a kind that recurs across enough people is an attribute
proposal with real evidence behind it. That is the agenda's work, and it wants the judgement
layer (`facts.conclude`) rather than a new mechanism.

## Research for one thing: "find out more about this"

The person says "I'm interested in a BMW X5, 2026". The world records the thing and then goes and
fills it in — specifications, prices, what people say about it — so that by the time they come
back to it there is something to talk about. `entity.research()`, roughly.

The shape it should take, from what is already decided elsewhere:

- **a ticket, not a call.** Expensive, several pages, background, one at a time, on a budget; it
  does not happen in the middle of answering someone.
- **what it finds are statements**, each with the page it came from as its source — so they are
  checkable, outranked by the person's own word, and retractable one by one if a source turns
  out to be rubbish. Where it summarises rather than copies, that is a conclusion with its basis
  (`facts.conclude`), and it goes stale like any other.
- **only where it is allowed** (`lookup.py`): a public thing — a car model, a company, a place —
  or anything at all if the person asked for it about that thing. Never a person from this world,
  and never a query carrying what they told us.
- **it has an "as of".** Prices and reviews age; the entity should say when it was looked into,
  and the tick should notice when that was long ago.

Open: whether a researched thing is an ordinary entity of an ordinary class (a `Product` we do
not have yet) or something looser, and how much of a page is worth keeping versus fetching again.

**Decided 2026-09-25** (`docs/decisions.md`, "the road to submission"):

- **One mechanism, "pick it for me"**, for tickets, housing, products and things to do. The query is
  built from the person's world — requirements without identity — and the findings are text like any
  other, so they go through the same `formalise` pipeline with the web page as the source, and
  `check.py` refuses any attribute the page does not bear out.
- **A world for each search.** Candidates go into a research world of their own, not into the
  person's. There the host picks, ranks and filters them with code, the person's world loaded beside
  it in the same namespace for the criteria. What moves into the person's world is the choice and why.
  Open: whether a research world is kept, dated, or discarded after the choice.
- **Preferences need no class of their own.** "Anna likes jazz" becomes a typed link through the same
  door as any other fact.
- **The demo is "where to go on Saturday".** Housing and products are the same code, shown in a line.

## Giving a new link its rules: the parts not built

The chain is described in `docs/engine/architecture.md`. What exists: the trigger (`ticks.py`,
*loose-links* — a `related` label used three times or more) and the evidence
(`properties.py` — what the links have ever done, and which declared rules the data breaks).
What is missing is the middle: a ticket that asks whether the type already exists, brings the
model's general knowledge to bear on its properties, checks that setting them breaks nothing,
and writes `ontology/grown/`. That is the agenda's first real job.

## A change that happened in the past can't be backdated

`person.organization = new_place` ends the old membership *now* and opens the new one *now*. When
the user says "she moved to Halden in July", there is no way to say so through the derived
setter: the world records today. Seen in s24, where the answer correctly read "the change is
recorded as ending today" — which is true and wrong at once.

What it needs: the period to travel with the assignment (`person.set("organization", place,
starts=date(...))`, or the same through `relate`), and `history("organization")` to read from the
statements rather than from when the write happened.

## Judgements: the parts not built yet

The layer itself works — `facts.conclude(...)` with a basis, staleness when the basis moves,
`entity.why(attr)` handing the host the judgement and what it rests on. What is missing:

- **the forms**: `ontology/judgements/` — what a judgement is *about*, what it is drawn from,
  what fields it has, and what work produces it. The third structure of classes
  (`docs/engine/architecture.md`), still only described.
- **the machinery**: what to re-derive, when, on what budget. This is work for the agenda: one
  expensive job at a time, ordered by who is actually asked about.
- **"why do you think that" reaching the ticket.** Today the answer is the judgement plus its
  basis, handed to the host to put into a sentence. Once work is organised into tickets, the
  run that made it names the ticket that ordered it — `run_id` already carries it — and the
  answer can include what the world was trying to work out, not only what it read.

## Onboarding: what belongs in it beyond the two parties

`terraweaver/onboarding.py` is the named step that brings a world up from the files beside it.
It runs on every open, not once. Today it reads `USER.md` / `soul.md` into the two parties
(`selves.py`) and nothing else. What belongs there:

- class additions and procedures from `AGENT.md` (the parked sketch below);
- the first conversation — a world with nothing in it asking for the few things that make the
  rest useful, rather than waiting to be told;
- importing what already exists (contacts, a calendar) as statements from those sources.

## Parked: AGENT.md as the person's own growth

`terraweaver/agentfile.py` parses class additions and procedures out of an AGENT.md — the same
two upper levels the world grows for itself, written by hand instead. Written as a sketch, not
wired in: the write path comes first. (`USER.md` and `soul.md` are live — see `selves.py`.)

## From the literature review (docs/related-work.md), in order

1. **A check before the commit.** 20–26% of runs come back as errors and are rolled back whole;
   each is a fork where two attempts of the same task diverge. SWE-agent's ablations put +3pp on
   exactly this: validate the write, report the violation, don't let the run die on line one.
   Savepoints — keeping the good statements of a run that failed late — belong in the same
   discussion, against the atomicity rule set deliberately.
2. **A proposed `same_as` instead of a duplicate.** When an agent answers its own identity
   question, record a link with provenance "agent", ranked below a user-confirmed one, rather
   than a second person. Merge is a derived artifact, never a destructive edit: keep the source
   records, keep the link table, compute the survivor — then un-merging is deleting a link.
3. **Rank doubts by what the answer changes**, not by how often the entity is touched:
   P(it flips an answer) × consequence × future reads − cost of asking. Access count is only the
   third factor.
4. **Report pass^k** (done for the runner) and audit our own EXPECT blocks the way the Agentic
   Benchmark Checklist says to — a check that reads a question object rather than a result fails
   for the wrong reason, which has already happened here once.

## A hint the host ignores, a question the host answers itself

Partly addressed: contradictions are now kept as open questions on the entity
(`docs/archive/questions.md`), so a doubt outlives the run that noticed it and comes back every time
anyone works with that entity. What is still open is below.

Two failures from the same run, both host behaviour that the world can see but not prevent:

- s20: the world hinted "Michael already has a dentist for that time: Arun Rao — both stand
  unless you end one". The host read it, answered the user correctly ("Arun Rao through
  September 30"), and never ended the relation. The answer was right, the world was wrong.
- s19: `Person.get(full_name="Olga")` came back as a NeedsResolution; the host swallowed it in a
  bare `except`, called `world.settle(needs, new=True)` on its own, and created a second Olga —
  exactly what the guide forbids ("never answer it yourself — not even with new=True").

The rule of this project is to enforce in code, not in the prompt, and neither of these is
enforced today. A question keeps the doubt alive (s20's two dentists, s19's second Olga), but it
still doesn't make the host act. Open: whether `settle(..., new=True)` can require the user's
answer at all — the world never sees the conversation, so it can't be verified from inside — and
whether an open question should reach the user another way than through the host that ignored it.

## Direction of relations, measured

Hosts wrote relations backwards — `owner.relate(nina, "service", label="dentist")` for "my
dentist is Nina". The answer so far is convention, not a new API: one rule stated once (the
subject is the one the label describes), an example per relation type in the world description
showing the sentence it makes, and every result printing a relation as that sentence. If runs
still come out reversed, the fallback is a role-first call — `nina.relate_as("dentist",
of=owner)` and `owner.who("dentist")` — where direction can't be got wrong because it isn't
expressed.

## Close the `Preference` gap

A fact is stored as `predicate` + free-text `value` — "wants" / "зарплату от 150000". Nothing
records what a fact is *about*, so "чего я хотел от работы" can only be answered by matching
keywords against free text, which is where `read_owner_wants` goes wrong: the agent decided
`wants_remote: False` while the world says the opposite.

This is the same gap `Event.kind` had, and the same fix applies — record the thing that gets
asked about instead of leaving it to be inferred.

## Make a misused `FindResult` fail loudly

`FindResult` is list-like, so passing the whole result where an entity is expected —
`Person.find(organization=Organization.find(name="TechCorp"))`, forgetting `.main[0]` — doesn't
raise. It silently matches nothing, and an empty result reads as "there are none". A wrong
answer delivered confidently is worse than an error.

## Detect emulating scripts

A scenario check trusts that the agent's script did the real work. It doesn't have to:

- hardcoding the expected answer — `report("hello-terraweaver")` passed the `machine_echo`
  check after the `Machine` class had been removed entirely;
- computing the answer with plain Python while bypassing the world model;
- reporting a plausible constant instead of deriving the value.

The world now counts what a script actually touched (`world_queries`, `world_writes`,
`entity_reads`), and exp01 refuses an answer from a script that consulted nothing. That closes
the blunt case. Still open: a script that touches the world *and* reports something unrelated.

Ideas: check that the reported value derives from what was read; run a scenario against a
deliberately altered world and require the answer to change — an emulating script gives the
same answer either way.

## Parked: the write path

`link_person_org` fails 0/3. Told to record a new person, the agent searches with `find`,
doesn't find them, and reports "not found" rather than creating them with `ensure`. Parked by
choice while the focus is on reading — not because it's understood.

Related: creating an entity still bypasses the consistency layer entirely. `Person(...)`
direct construction is allowed, so deduplication can be avoided at creation the same way it
used to be avoidable on attribute writes.

## A design pool: scenarios that guard the ideas, not the model

The unit suites check that a mechanism is arithmetic. They cannot check that it earns its place.
A design scenario does: the task is what a person would actually say, nothing in it explains how
to store anything, and the mechanism is the only cheap way to get the answers right. If the
mechanism rots — or stops being reachable from the host's side, which has happened twice — every
probe in its scenario goes wrong at once. Run them as their own pool: `--level design`.

Written: `s27_standing_things` (cyclic periods).

Wanted, one per idea we've committed to:
- tags with periods — something true for a season, asked about after the season
- `where` with no class — a question about a thing that is not one kind of thing (s26 is a draft
  of this; it needs its own fixture instead of the job-search one)
- the two-stage record — "those were two different people after all", and nothing is lost
- questions — a contradiction taken, remembered, and raised when the entity is next touched
- direction — a relation written from the wrong end, and the world saying so
- identity — a name that is a form of another name, merged; a namesake, not merged

## Known limits of repeats

- No weekday rule: "every weekday" has no form here. `every="week"` anchored on a Tuesday is the
  way to say "every Tuesday"; five rules is the way to say "every weekday", which is silly.
  Whether to grow the vocabulary (RFC 5545 has BYDAY) or leave it is an open question — the
  parser stays small on purpose.
- No exceptions to a rule: "every other Tuesday, except the one in August". The record is
  append-only, so a skip would be its own statement subtracted by the derivation; nothing does
  that yet.
- A cyclic entity's repr says nothing about repeating. `entity.repeats()` and the write receipt
  do, and `world.repeats()` lists them, but a host printing an Event sees only the anchor and
  may read a series as a one-off. Fixing it means a query per repr, so it waits for a per-run
  cache.

## Half-open periods are invisible

s20 fails this way twice over: told "from October 1 my dentist is Patel instead of Rao", the host
ends Rao on September 30 and starts Patel on October 1, leaving a day with no dentist. Periods
here are half-open — [from, until) — so the handover is "until October 1", and nothing says so
where the host is looking. Worth a check in code rather than a line in the guide: for a relation
type with `one_of_a_label`, when one ends and another of the same label starts within a day or
two but not at the same moment, say that there is a gap (or an overlap) and what closes it.

## Free text is a type now, and comments are the odd one out

`list[text]` makes a slot hold several free texts, each stated on its own, each with its own
period: `entity.add("descriptions", ..., starts=, until=)`, `entity.drop(...)`,
`entity.spells("descriptions")`. Assigning the whole list goes through the same door. Tags are
the same machinery with one extra rule (one form to compare by), and `list[enum[a, b, c]]` is
the same again, drawn from a vocabulary.

Which leaves comments as a second mechanism for the same thing — free text about an entity, with
a date and a period — kept in its own table with its own words (`when`, `tentative`, `ttl`,
`forget()`, world-wide search). Two things worth deciding:

- Whether a comment becomes a `list[text]` item with `tentative` as a marker on the statement,
  and comments.py becomes a way of reading rather than a place of storage. That would leave one
  answer to "where does free text go", and one set of words for its time.
- What a comment has that a text item doesn't: `when` (the thing happened then) separate from
  the period (it holds from then), a default ttl, and searching across every entity at once. The
  first is real and would have to survive the merge.

## The ladder, as a template for structuring

Prose → vocabulary → value is the same slot growing up, and it is the shape the world should use
when it structures something itself (level 2, `ontology/grown`): a `list[text]` slot whose texts
keep repeating the same few words is a `list[enum[...]]` waiting to be declared, and a slot that
never holds more than one is an ordinary attribute. The world can see all three from the record
alone — count the distinct texts, count how often each recurs, count how many hold at once — and
propose the change rather than make it. Nothing does this yet; properties.py does the equivalent
for relations, and is the model to follow.

## One word, two meanings: Event.participants

`Event.participants` is a plain `list[ref:Person]` attribute, and `participants` is also the
reverse name of the `Participation` relation. They know nothing about each other:
`Event.new(..., participants=[nils])` fills the attribute, `event.related("participants")` reads
the relation, and a host that writes one and reads the other gets an empty list and believes it.
That cost s27 a probe: told to find 1:1s with Nils, the host filtered `event.related("participants")`,
found nothing, and answered "no 1:1 meetings are scheduled" about a world that had one.

The world already solves this elsewhere and the fix is to follow it: `Person.organization` is
declared `derived: relation` with a setter that records a Membership (`relations.DERIVED`). The
same for `participants` — derived from Participation, settable, `add_participant` going through
it — leaves one meaning per word. Knock-on: fixtures and scenarios that pass `participants=[...]`
at construction, `impls.add_participant`, and the APPLY_ORDER for derived attributes given to
`new()`.

Worth doing with the comments/descriptions merge, since both are "two mechanisms for one thing".

## The prompt: inline the few hot classes, name the rest

Measured 2026-09-21. Cutting the class dump out of the prompt halved it (12,004 → 6,949 tokens)
and did not save a penny: cost per scenario stayed at ~$0.19 because the host now spends the
saving on round trips (s01: cache-created −23%, turns 20 → 32). The saving is real, it just moved.

The shape that should win, agreed with the user: carry the few classes a world is actually worked
with **in full**, and the rest as names with `describe_classes` for detail. Which ones are hot is
not a guess — `usage.py` already counts every get/find/ensure per entity, so the world can order
its own classes by how often they come up (instance counts as a fallback in a fresh world).

The effect grows with the number of classes: at nine the dump is 6k tokens, at thirty it is
20k+, while the hot handful stays the same size. That is the case for doing it — not today's
prompt, but the one a grown world would have.

Next, in order: the four steady failures (s04 remembered name choice — our own machinery, not the
model; s11, s18, s20), then this.
