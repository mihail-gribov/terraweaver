# The world, assembled

What the world is, after the rethink of 2026-09-20. This is the picture to build against;
`docs/about.md` is the project spec it serves, and the documents named below each hold one part
in detail. Written before the work rather than after it, so the order below is the plan.

## What the world is for

A tool that helps a model work with a person's data. Two sentences decide almost every argument
about it:

> The world may constrain the data and the structures the data is kept in. It may never
> constrain how the model reasons or writes its code.
>
> Every refusal must name the data it protects. A refusal that can't is a defect.

Measured, not asserted: the most expensive thing the world ever did to a host was refuse
`from datetime import date` — 63 wasted runs, protecting nothing. The checks that hold data
uniform (vocabularies, relation rules, value kinds) cost nothing and prevented junk.

## Two stages: what was said, and what follows

    statements ──assembly──▶ images
    facts.py                 store.py + ontology.py

**Statements** (`facts.py`) are the lower layer and the only thing that is ever *recorded*.
Append-only. A correction is a later statement; a retraction is a statement about a statement.
Each carries whose word it is (`source`: the user, the assistant, a named source), when it was
said, and when it holds from and until. Nothing is overwritten, so nothing can be lost by being
wrong.

**Images** (`assembly.py` → the existing entity store) are what follows from the statements: the
entities as the world currently reads them. They are a *derivation*, not a record, and can be
thrown away and rebuilt at any time. Two rules build them, and both are code, not data:

- **identity** — which subjects are one and the same. Deliberately optimistic: two people called
  Anna are glued into one image, because being wrong costs a rebuild, not data. One
  distinguishing fact — a surname, a second email, or the user saying "those are two different
  people" — pulls them apart on the next rebuild, with each one's statements still attached to
  the right one.
- **resolution** — which of several statements about one slot the image shows. Whose word it is
  first (the user outranks a source outranks the assistant), then the later one. What it beat is
  reported, not hidden: that is where a doubt comes from.

What this buys, all of it structurally rather than as a mechanism bolted on: history (the
statements *are* the history), undo (retract a run's statements and rebuild), provenance ("why do
you think that"), safe merging (`same_as` is a statement like any other, so un-merging is
retracting it), and schema change without data loss (facts don't care what shape the image has).

The literature calls these inconsistency-tolerant query answering, prioritized repairing,
deferred entity resolution and bitemporality — `docs/related-work.md` maps each piece to its name
and to what that work does better than we do.

One more thing the assembler has to know, and the class is what tells it: **how many of a thing
there can be at once.** Two email addresses are two addresses; two employers at the same time are
a disagreement. The class says which by declaring the slot a list or not, so the assembler never
has to guess — and never reports a second phone number as a quarrel.

Names are the case where this matters most. A person is called Michael, and Mike, and Michael
Gribov, and none of those contradicts the others: they are forms of one name. So they are
collected rather than resolved — `image.names` holds every form, fullest first, and the fullest
is the one shown, because it is the one that identifies without context. A nickname stops being
a second-class "alias" and is simply another thing the person is called.

## What was said, and what the world worked out

Not every statement is something someone said. Some are what the world concluded: a hundred
remarks about a person read together into a judgement about their character. Those are expensive
— many statements, a model, sometimes a search, several passes — so they are *kept*, not computed
on every read. That is what separates them from the assembly rules, which are cheap and run
whenever anyone asks.

A conclusion is a statement like any other, with two things added: **what it was drawn from**,
and a digest of that basis. From this follows everything that keeps the layer honest:

- **lowest standing.** The assistant's conclusion loses to anything anyone actually said, by the
  ordinary resolution rule. No special case needed.
- **"why do you think that" is answerable** — `basis_of()` returns the statements, not a retelling.
- **staleness is mechanical.** The basis moved, the conclusion is stale; re-deriving it is work
  for the agenda, not a judgement call.
- **never drawn from other conclusions.** Refused at the API. A world that reasons from its own
  guesses will believe anything by the end of the month.
- **removable wholesale.** Retract everything with source `agent`, rebuild, and the world is
  back to exactly what it was told — the primitive an agent needs to untangle itself.

Rebuilding an image uses both kinds. Numbers, words and vocabulary values are taken as they were
stated; where a slot has only judgements — someone's character, say — the image takes those, and
marks them: `image.judged` says which values were worked out rather than told, `image.stale` says
which of those are due to be worked out again. A host can then answer as what it is — "as I read
it" rather than "you told me" — and one sentence from the user replaces the judgement outright.

## Three structures of classes

    ontology/core/        ours, fixed           what there is
    ontology/grown/       the world's additions what turned out to be missing
    ontology/judgements/  forms of conclusion   what the world knows how to work out

The third declares the *shape* of a judgement rather than a fact: what it attaches to
(`about: Person`), what it is drawn from, what fields the result has, and what work produces it.
Its instances are conclusions, so they carry a basis and go stale; in an entity's image they sit
where any other value would — `person.character` is a derived instance, built by expensive work
and shown like anything else.

| structure | author | how it is checked | how it comes off |
|---|---|---|---|
| core | us | tests, our own reading | it doesn't — it is the ground |
| grown | the world | regression and `pass^k` | delete the file, rebuild |
| judgements | the world, in our shape | the basis is visible, staleness is mechanical | retract the conclusions, rebuild |

## Three levels of change

A world that improves itself changes at three levels. They differ in how freely they change,
what being wrong costs, and how a change is taken back.

| level | where it lives | who may change it | taken back by |
|---|---|---|---|
| **data** | statements | the user, the host, a source | retracting statements, rebuilding |
| **descriptions** | `ontology/core` (ours, fixed) + `ontology/grown` (the world's) | the world, additively | deleting the grown file, rebuilding |
| **methods** | `procedures.py`, in storage | the world | dropping the procedure |

**Descriptions.** The core classes are ours and are never edited by the world. Growth is additive
overlay (`growth.py`): another attribute, another method, another label — never a redefinition,
never a removal, and never a second class for the host to choose between, because a fork in the
description is a fork in the model's reasoning. Every addition carries `because`: the evidence
that earned it. Data survives a removal, because data lives in the statements.

**Methods.** A procedure is code the world keeps because the same work kept being written by
hand. It goes through the same sandbox as host code and is checked when defined, not when first
called. It counts its uses, and the ones nobody calls are named for dropping.

**The middle level is the dangerous one.** Data can't be lost any more; bad code fails loudly.
A description changes how the model *reads* the world: a poorly named attribute raises no error
at all, the host merely starts getting things wrong. So the regression gate belongs there most,
and `pass^k` is the only instrument that sees it.

## Two databases

    var/world.db     statements, images, procedures — the person
    var/agenda.db    tickets, what was tried, what came of it — the world about itself

The agenda is not part of the world and has nothing directly to do with the person, so it lives
apart. Then "export my world", "back it up", "delete everything about me" are operations on one
file, with no exceptions to explain.

One rule keeps the split real: **the agenda refers, it does not quote.** A ticket holds an
entity id and a kind of work — never a name, a number, or what someone said. Otherwise the
agenda slowly accumulates a copy of the world, and deleting the world stops being a deletion.
References point one way: the agenda knows about the world, the world knows nothing of the agenda.

Consequence worth taking: **doubts belong to the agenda, answers belong to the world.** A
question is operational work; "the user said those are the same Olga" is a fact about their life.

## The world's own time

**Ticks** (`ticks.py`) are a procedure cron calls: bounded, recorded, and never touching a fact
about the person. A tick closes doubts whose reason has gone, notices what nobody looked at,
counts what the world isn't using. Anything touching identity or facts is a proposal, not an edit.

**Tickets** are the world's agenda: one unit of work with its own context, so it can be picked
up, worked, and put down without polluting anything else. One ticket is worked in one session,
which is how "without mixing contexts" is enforced rather than hoped for. Sub-tickets exist for
work that genuinely has steps.

Two separations make the agenda trustworthy:

- **stating a task is not solving it.** A ticket is stated with `done_when` — a checkable
  condition — and the solver may not move it. Otherwise the world decides what to do, does it,
  and declares it done, and nobody ever checks.
- **the solver is the model inside the world** (Nemotron, or whichever model is configured for
  it), not the host. The host answers the person; the world builds itself. A ticket's id goes
  into the `run_id` of every statement it produces, so any fact the world wrote by itself traces
  back to the work that produced it — and is undone with it.

## The two parties, and where they come from

Every world holds both of the people it is between — the person it belongs to and the assistant
keeping it — under fixed ids, created when the world opens, and neither is the host's to replace.
Without them there is no "me" and no "you" to hang a relationship on, and every fixture had to
invent its own pair.

What they *are* is configuration, and personal agents keep configuration in files:

    USER.md      who the world belongs to      (or ABOUT_ME.md, ABOUT.md)
    soul.md      who is keeping it             (or SOUL.md, AGENT.md)

`AGENTS.md` and `CLAUDE.md` are deliberately not among them: they describe a project and how to
work in it, not the assistant. A world that read them as "who I am" would file commit
conventions as someone's character. For the same reason the body of `soul.md` becomes the
assistant's character rather than a note about it — that is what the file is for.

Front matter sets attributes, the body is kept as notes, and the world re-reads a file when it
changes. What a file says is **facts with that file as their source** — reliable, because someone
wrote them deliberately, but not a separate kind of truth: they join what conversation and
sources said about the same two entities and are resolved into one image by the ordinary rules.
A line taken out of the file is a statement retracted, not a value deleted. Something the user
says in conversation outranks the file, which is right — the file is last year's intention, the
sentence is this morning's.

## Opening a world

    from terraweaver import open_world

    w = open_world()                      # empty, in memory
    w = open_world(fixture="job_search")  # with something in it
    w = open_world("var/mine.db")         # on disk, with its USER.md and AGENT.md beside it

One line, because most worlds are opened to test something, and ceremony is the whole cost. The
files are looked for next to the world, so a world carried on a stick carries its configuration
with it.

## What can be taken away

The world has to work without its upper floors, and each of them has to come off without
breaking what is under it. This is a design constraint, not an observation — it is what keeps a
"self-improving world" from meaning "a world that only works while its improvements do".

| taken away | what is lost | what still works |
|---|---|---|
| **the agenda and the solver** | the world stops improving itself: growth and procedures happen only when a person writes them | recording, reading, doubts, the three moments to ask — everything a host needs |
| **ticks** | nothing maintains itself on a schedule | doubts still close when read, because that check is lazy by design, not a job |
| **grown descriptions** | the classes are only ours | every statement is still there; the image just stops showing what the added attribute held |
| **procedures** | the shortcuts go | the object model was always the way to do the same work |

So the order in which things are built is also the order in which they may be missing: statements
and images are the world; the rest is a superstructure. Anything that cannot be removed this
cleanly is in the wrong layer, and that is the test to apply before adding to it.

## Doubts, and who settles them

The world takes what it is told even when it doesn't add up, and records what doesn't
(`docs/questions.md`). While a doubt is open there is always one standing reading, the same for
every host, decided by rule — so a host can always answer, by saying which reading it used.

Three things can settle a doubt, and they are not interchangeable: a **rule** (the reason went
away — closes itself), the **user** through the host (anything about whose life this is), or a
**checkable source** (a matter of form: a registered name, a domain, a spelling).

Three moments to put a question to the user, and only these: when the pending read depends on it;
at the end of a task; when the user offers. A doubt that doesn't bear on what is happening stays
quiet — repeating it on every contact is noise.

## How we know it isn't getting worse

- **`pass^k`** on a fixed pool of scenarios, reported with the rollback rate beside it. A single
  run measures nothing: it is one draw.
- **friction** (`scenarios/friction.py`): what hosts stumble on, ranked, across saved transcripts.
  Every rolled-back run is a fork where two attempts of one task diverge, so this is a stability
  metric, not a cosmetic one.
- **rebuild determinism**: the same statements must build the same images. Rebuild twice, compare.
- **replay**: the code hosts actually wrote, in `runs`, re-run against a changed schema — a free,
  deterministic regression suite for the middle level.
- **the description budget**: the host reads ~490 lines before every task. Every grown attribute
  adds a line to every future run. Growth must earn its space, not only its existence.

## Modules

    facts.py         statements: the only thing recorded
    assembly.py      identity and resolution: images from statements
    store.py         the image tables
    ontology.py      classes from specs; how an entity behaves
    describe.py      how the world is explained to the host — the real interface
    growth.py        what the world added to its own classes
    procedures.py    methods the world wrote for itself
    world.py         the verbs: get / new / ensure / find / relate / settle
    relations.py     relation types and what they check
    questions.py     doubts and how they are settled (moves to the agenda)
    ticks.py         the world's own time
    runtime.py       sessions, runs, results as the host reads them
    server.py        MCP
    sandbox.py       what host code may reach
    matching, values, timeutil, conditions, usage   small, single-purpose

To go once the migration lands: `history.py` (the statements are the history) and most of
`questions.py` (a doubt is two live statements about one slot, not a hand-kept record).

## Order of work

1. **Writing through statements.** Every assignment and creation records a statement; images stay
   as they are. The object model the host sees does not change.
2. **Rebuilding.** `rebuild()` drops images and replays statements through assembly. Test: two
   rebuilds are identical.
3. **Delete what became redundant** — `history.py`, then doubts as a view over conflicting
   statements.
4. **Fixture, export, scenarios** on the new base; `pass^k` before and after, on the same pool.
5. **The agenda**: its own database, tickets with `done_when`, the tick stating work instead of
   doing it.
6. **The solver**: the world's own model working one ticket at a time, in its own session.

Nothing in 5 or 6 starts before 4 reads as well as it did before. That is the whole point of
measuring it.
