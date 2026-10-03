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

## How a world serves an agent

Set with the author on 2026-10-03, after a day of reading wrong answers by the stage they were
lost at (`experiments/wrong_answers.py`). Three rules about the two directions information
moves in, and one about where it is kept.

1. **Take it the way the agent finds convenient, and keep all of it.** Words instead of types, a
   bare name instead of a class, `full_name=` where the world says `name`, a string where a
   thing belongs: accepted, recorded, structured afterwards by the world. Nothing the agent said
   is refused or lost — a write that failed is held open until it is made
   (`runtime._settle`), and a task does not close over a fact that is not in the world.
2. **The world reconciles, not the agent.** Copies of one thing, a later telling and an
   earlier one, a link written the other way round, which clock a date is on: the world settles
   them before it answers. What it cannot settle it says *in* the answer — "X; before that, Y" —
   never as two values handed over to be sorted out. Measured: handed two values and a hint
   beside them, the host saw the hint in 3 of 10 cases and broke the tie with what it knew of the
   real world.
3. **Give it back the way the agent asks, not the way it is stored.** "Who runs Microsoft now" is
   the question; relation classes, directions (`ceo` or `ceo_of`), ids and `valid_from` are the
   world's own language, not the agent's. The world's ongoing work — reading, placing, merging —
   is building such views. The quality of the views is measured by the *answering* stage: the
   world held the answer and the agent did not get it.
4. **The image is a cache of the record.** Nothing the agent says is written into an image; an
   image is assembled from the statements, and kept assembled because assembling it on every
   read would cost too much (the next section). *Where the code still departs from this:*
   `World.save → store.save_graph → store.save` writes images from objects in memory. Every
   image that disagreed with its record on 2026-10-02 came through there — names nulled while
   the record held them, a `died_in` snapshot showing a link the record had ended — and
   `World._with_its_name` is a patch on that door, not a fix.

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

Names are the case where this matters most, and the one place the world is deliberately strict. A person is called Michael, and Mike, and Michael
Gribov, and none of those contradicts the others: they are forms of one name. So they are
collected rather than resolved — `image.names` holds every form, fullest first, and the fullest
is the one shown, because it is the one that identifies without context. A nickname stops being
a second-class "alias" and is simply another thing the person is called.

But a name is not an ordinary value: names decide who is who, so a form counts only if someone
vouched for it. The user said it, or a source did — then it is a name. What the world worked out
for itself waits in `proposed_names` and takes part in nothing, because "Sota is probably that
Sasha" would merge two people on the next rebuild and be very hard to unpick. The exception is
knowledge about language rather than about the person: "Mike" is how English says "Michael", and
that holds for everyone called Michael (`nameforms.py`), so it needs nobody's permission.

The host carries the language side of this: it is asked to look people up by the fullest form of
the name it knows, because it is the one that knows "Миша" and "Михаил" are one name. The world
keeps every form it was given, so either will usually find him — but canonicalising is the
model's job, and the table in the world is only the net underneath.

## Two identities, and why both

An entity carries two: `id`, the image built from statements, and `subject_id`, the identity in
the record that new words about it attach to. They are the same until two subjects turn out to be
one person; then the image speaks for both, while everything said from that point lands on one
subject rather than on the cluster.

That is what makes a wrong identification cheap. Say the world joined two people it shouldn't
have. Because every statement stayed with the subject it was made about, splitting them puts each
back where it belongs — including what was said during the time they were joined. Had new words
been attached to the image, they would have nowhere to go on a split, and the mistake would be
permanent in exactly the way this architecture exists to avoid.

Three sources, and only three. Everything arriving through the assistant — the person's own words
and whatever the assistant concluded from them — is one source, `agent`. The world cannot tell
those apart and does not try: what the assistant passes on is the assistant's responsibility. A
named source (a file, a register, a site) is checkable and outranked by the person's own account
of their life. `world` is what this world worked out for itself, the weakest of the three, and it
lives in the `reasoning_` tables rather than the `facts_` ones.

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

## The first thing the world does for itself: giving a new link its rules

This is the shape every self-improvement takes, and it is worth following once in full.

A link appears that no type covers — the host records it as `related` with a label, because that
is what `related` is for: the world admitting it has no rules for this. Nothing happens yet; one
godfather is an event, not a pattern.

The same label comes back a third time. A tick notices (`ticks.py`, *loose-links*) and states a
task. From there the questions are in order, and each has a different answer-giver:

1. **Do we already have this?** "My physio" is a `service`; "my brother-in-law" is `kin`. The
   world can check the labels and roles every type declares; where that is silent, the model
   knows. If it is an existing type, the answer is not a new type — it is pointing the label at
   the one that fits, which is a change to that type's labels.
2. **If it is genuinely new, what is it like?** The formal properties, the same ones every core
   type declares: one at a time per person, reads the same from both ends, never a cycle, and
   what roles it has with what limits. Two things answer this together —
   - **the world in general**, which the model knows: a person has one mother, a company one
     chief executive. This is knowledge about life, not about this person, so it is kept once and
     used for everyone;
   - **this world's own data** (`properties.py`), which measures what the links have ever done:
     how often there was a chance to break a rule, and whether it was ever broken. Rarity is not
     evidence — three mothers in the world says nothing about how many a person has; eleven
     people with several relatives and never two mothers says something.
3. **Does setting it break anything?** A property is a check, and a check can refuse what is
   already recorded. `properties.findings()` answers this directly: it lists the rules a type
   declares that this world's own data breaks. A proposed property that would put existing data
   in violation is not applied — it becomes a question about the data instead.

Only then is the type written, into `ontology/grown/` with its `because`, and the world starts
checking the new link the way it checks the old ones. Which is the point: the world does not get
cleverer by knowing more, it gets stricter by knowing what holds.

The same measurement runs the other way round, and that is the more valuable half: a rule we
wrote by hand that this world's data breaks is either a wrong rule or a bad record, and both are
worth somebody's attention.

## When the world doesn't know the word

A person says "she's my doula", "he's at Quantinuum", "we met at YC". The world may have no idea
what any of those are, and guessing is how a world fills itself with nonsense. So it can look
them up — that is the third way a doubt gets settled (a rule, the user, a checkable source), and
the one that costs nobody's attention.

What it may look up, and what it may never:

- **Kinds of thing, and public facts about public things.** What a doula is, and therefore what
  kind of link it is. Whether Quantinuum is a company and what it does. The registered name
  behind a trading name; a city; a job title's usual shape. These are questions about the world,
  the answers are checkable, and asking them reveals nothing.
- **Never the person, and never through their data.** Not "who is Sofia Bergmann", not an email
  address, not a phone number, not what someone said. A search is a sentence sent to a stranger:
  whatever goes into it has left this world for good. The rule is simple enough to hold: the
  search terms are concepts and public entities, never anything the person told us in confidence.

What comes back is a statement like any other, with the source it came from — a named source,
which outranks what the assistant worked out for itself and is outranked by the person's own
account of their life. It carries its URL, so it can be checked; it can be retracted, so a bad
source can be undone; and it goes stale like anything else.

What may be asked is decided in code, not by judgement (`lookup.py`): a short list of purposes
we named in advance — what a kind of thing is, how a kind of link behaves, the registered name
behind a trading name — plus anything the person asked us to look into, in their words. A query
for one of our own purposes is read against what this world holds, and if a name, an address or
a number from it turns up, the lookup doesn't happen.

The work of reaching out is deferred and belongs to the agenda (`docs/ideas-research.md`): a
ticket, one at a time, on a budget — not something that happens in the middle of answering
someone.

## Tags

The loosest way to tie things together, and the first thing in any world to rot. A tag costs
nothing to add, which is its virtue and its problem: a month in there are `job-search`, `job
search`, `jobsearch` and `work`, and none of them finds the others.

It is also the place for a tie too vague to formalise: a relation type has to say what the tie
*is*, and sometimes there is no answer — everything about the move, everyone from that
conference, what matters this month.

The world does four things and refuses a fifth. It **holds them to one shape**, so a tag typed
three ways is one tag — data uniformity, which is its business. It **counts them**, keeping every
spelling, because the spellings are the thing worth reviewing. It **says which are worth another
look**, and that is driven by new material rather than by a calendar: what is recorded is how much
a tag covered when someone last considered it, and when that has grown by half again, the tag
comes back on the list. New information is what makes a judgement stale, not time.

And it **does what it is told**: `merge_tags` makes two words one, as an ordinary write — stated,
reversible, visible in the record — and `suggest_tags` offers candidates from whatever reads like
this one, applying nothing.

What it refuses is deciding. Whether `job-search` and `work` are one idea, whether a tag
covering forty things has become two, whether one nobody has used since March should go — those
are judgements about what a person means by a word. The world measures and points; the model
proposes, on the agenda; somebody decides.

## Descriptions

Every class has `descriptions`, and it holds several. People describe the same thing differently
— "quiet, precise, hates being rushed" and "the one who rewrote the billing pipeline over a
weekend" are both true of one person — and neither replaces the other. On the statements layer
that costs nothing: several tellings are several statements on one slot, which is what a list
slot already means.

A telling may come from the person, or from a source: a company's own account of itself, what a
place is known for. The first is private knowledge, the second public, and the record keeps whose
telling each one was, so they never blur — the person's word outranks a page, as everywhere else.
Nothing about a *person* is ever looked up (`lookup.py`).

This is what fuzzy searching runs on. "Someone who dislikes being hurried" finds the description
that says "hates being rushed" — no word in common — which is exactly the kind of question that
has no attribute to be asked against.

## Three derivations, one record

The statements are the only thing recorded. Everything else in this world is derived from them
and may be thrown away at any time:

    images     the entities, by identity and resolution rules        (assembly.py, rebuild.py)
    periods    when things held, coalesced into one row per stretch  (periods.py)
    meanings   an index over what was said, for finding by sense     (meaning.py)

Each is rebuilt by a deterministic pass, states nothing, and outranks nothing. Change a rule —
who counts as the same person, how stretches are folded, which embedding model — and the world
is derived again from exactly what it was told. That is the property the whole design exists to
keep, and each new derivation has to earn its place without touching it.

## Finding by meaning

Most of a world is structured and needs no help. Some of it is deliberately prose — a remark
about someone, a note on an idea — because the host writes a remark exactly when the class has
no place for the thing. There, matching words finds nothing: "who works on batteries" misses
"does cell chemistry at a startup".

So there is an index over what was said, by meaning (`meaning.py`), with the local model where
one is served and a deterministic stand-in where none is, so every path works offline. Three
things about it are settled:

- **it is an index, not a source.** It states nothing, outranks nothing, never reaches an image.
  Change the model and it is rebuilt; the world is exactly as it was — the same relation to the
  record that images have to statements.
- **it suggests, it does not decide.** Above all it takes no part in identity. "Anna Petrova" and
  "Anna Sokolova" sit close together in any embedding, and who someone is is settled by names
  people vouched for and facts that disagree.
- **it is used where it is good.** Retrieval, and finding what is plainly the same thing said
  twice. Grouping remarks by topic was tried and measured: on real remarks, one topic spreads
  0.46–0.61 while different topics sit at 0.49. There is no threshold, so that job is not done
  this way — naming the kind of a remark is a judgement, and it belongs to the model
  (`docs/TODO.md`).

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

## The basic world

Two things, and the world works with nothing else present:

    statements              facts.py      what was said, never changed
    the entities built      rebuild.py    assembly's answer, written into the image tables

`world.rebuild()` throws the entities away and builds them again from the statements. It is
always available and always safe, and two properties of it matter more than any feature:

- **the same statements build the same entities.** Rebuild twice and nothing differs.
- **rebuilding states nothing.** It is a derivation, not a conversation: the record is exactly
  as it was afterwards.

So a rule can change and the world follows it — the same statements, a stricter rule, two people
where there was one — and a wrong guess costs a rebuild rather than data.

Everything above this is an improvement: doubts, ticks, growth, procedures, judgements. Each can
be absent and the world still records, answers and rebuilds.

## Order of work

1. ~~Writing through statements.~~ Done: every assignment and creation states, under the same
   object model the host already knows.
2. ~~Rebuilding.~~ Done: `world.rebuild()`, with both properties tested.
3. **Delete what became redundant** — `history.py`, then doubts as a view over conflicting
   statements.
4. **Fixture, export, scenarios** on the new base; `pass^k` before and after, on the same pool.
5. **The agenda**: its own database, tickets with `done_when`, the tick stating work instead of
   doing it.
6. **The solver**: the world's own model working one ticket at a time, in its own session.

Nothing in 5 or 6 starts before 4 reads as well as it did before. That is the whole point of
measuring it.

## An answer to a question put wrongly

A world that answers "nothing matched" to `Organization.find(full_name="CloudNine")` is telling
the truth and doing harm. The host reads it as "CloudNine isn't in the world", says so to the
user, and goes looking elsewhere — and nothing in the exchange suggests the question itself was
the problem. The same silence came back three times in one day: a constructor that reported a
missing required attribute without mentioning the unknown ones beside it, a relation asked from
an end that had none, and a lookup by an attribute the class hasn't got.

So it is a rule here, not a series of fixes: **when there is no answer, work out what was meant
and say it.** Name what is wrong with the question, name the nearest thing that would have
worked, and stop there — a suggestion said out loud, never a substitution made quietly.

It has to be deterministic. The world does not ask a model what a host probably meant: it is
spelling distance, singular against plural, and a small table of words people use for each other
("name" where this class says "title"). One function does it for everything —
`ontology.did_you_mean(word, options, extra)` — so the same mistake gets the same answer twice,
and a test can hold it to that. Places that use it: an attribute set or given to a constructor,
an attribute looked up by, a relation type, a value outside a vocabulary, a list of texts
written into. Each of them used to answer with silence, an empty list, or a bare refusal.

And where the correction is unambiguous, the world does not refuse at all: it answers the
question that was meant and says what it read as what. `Organization.find(full_name="CloudNine")`
comes back with CloudNine and an `[assumed]` line saying `'full_name' taken as 'name'`. A refusal
there costs the host a turn to learn something the world already knew, and the turn it spends is
paid by the person waiting. The line between the two is not confidence but ambiguity: one close
word and no other is applied; two candidates, or none, is refused. Reads carry no risk in this;
writes are announced the same way and are as easy to correct, because the host reads the answer
before it speaks.

The same rule shapes refusals that are correct but useless. "One at a time — end that one first
(its `.expire()`…)" is sound advice and the wrong advice for a move announced ahead of time:
`.expire()` ends it today, the new one starts in March, and the host loops. A refusal names the
call that would work *here*, with the date in it.

## What the world is for: less entropy than it found

Everything here is one job said in different ways. A world takes what arrives — a person's
words, an assistant's reading of them, a page from somewhere — and leaves it more ordered than
it was. Not more complete, not cleverer: **more ordered**. Every mechanism in this repository is
an entropy operation, and every defect worth the name is an operation that quietly added some.

That makes a test any change can be held to. *After this operation, is there less disorder than
before?* It is not rhetorical — the failures all answered it out loud:

- **A conclusion read before a statement.** Slots have always been resolved by trust and then by
  time; relations were resolved by time alone. So a link the world guessed for itself came back
  ahead of one the person had stated, because it was newer. The restructuring pass then made a
  world measurably worse than it found it — 9/20 to 7/20 on an unchanged world — by doing its
  job. It was not adding wrong facts; it was adding unranked ones to the one channel where rank
  was never consulted.
- **A value that cannot supersede.** A fact in prose has no slot, so nothing overrides anything
  and both readings stand for ever. Order in time is order; prose has none.
- **One thing recorded four times** — rugby as a Place, an Organization, a Work and a SportsTeam
  — because identity is declared per class and nothing looked across them.
- **A discarded run**, which threw away order wholesale: not one reading lost, but everything the
  host had established in that block.
- **A silence** where a question was put wrongly, which leaves the host to invent the missing
  order itself, usually differently each time.

And it tells you what the world must never do to buy order cheaply: guess. Merging two people
because their names look alike, deciding which Annie was meant, reading a sentence to decide
whether it states a fact — each of those is order bought with a lie, and the lie has to be
carried by everything downstream. The world reduces entropy by **saying what it knows, ranking
what it holds, and naming what it cannot settle** — never by picking.

