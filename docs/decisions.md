# Why the world is the way it is

One entry per decision that changed how the world behaves. Not a changelog — the commits carry
that. This is the reasoning: what was seen, what was done about it, and what was rejected. A
decision without its evidence is an opinion, and an opinion cannot be revisited when the evidence
changes.

The shape of an entry, in order:

- **Seen** — the observation, with the number. Counted in a run, not imagined.
- **Done** — what changed, in a line.
- **Why this** — the reasoning, including what it costs.
- **Not this** — the alternative that was rejected, and why. Leave it out only if there was none.
- **How we would know it was wrong** — what would have to show up for this to be reopened.

Newest first.

---

## 2026-09-22 · Five natures, and any number of types that name one

**Seen.** A host built four independent relation types for one idea — `ceo`, `chairperson`,
`head_of_state`, `prime_minister` — because there was no way to say "this is a narrower kind of
that". And `define_relation` asked for cardinality *and* `over_time`, which are the same question
in OWL's terms (a functional property *is* a cardinality constraint); multiplying them together
silently switched supersession off for most types the host defined.

**Done.** Relation types now declare a **nature**, one of five, taken with their names from
EvoOntology (arXiv:2609.15779): association, hierarchy, composition, equivalence, derivation. The
set is closed — a host picks one, and names its own type freely. `Kind` was added for the
hierarchy we had no way to express at all. `PartOf` is composition; everything else of ours is an
association, which is what a person's world is mostly made of.

**Why this.** A small fixed set of natures with everything particular as a named type is the
shape we already used for labels inside types, and now it has somebody else's experiment behind
it rather than our taste. The nature carries behaviour the world would otherwise have to ask
about: composition and hierarchy are transitive, acyclic and many-to-one; equivalence is
symmetric. What it does *not* carry is cardinality for associations — and that is where nearly
all of a personal world lives, so the question stays open there and is answered by declaration or
by observation.

**Not this.** Relation types for equivalence and derivation. Both already exist in this world
below the level of links — `same_as` is a slot in the record, a derivation is a conclusion with
its basis — and a second way to say them is the duplication this whole day was spent undoing.
They remain natures a type may name; they do not become mechanisms twice.

**And noted, not done.** A relation type is a class: the same `define_class` builds it, with two
required ends and a nature. Then `define` and `define_relation` are one call with different
arguments, and having two is the same redundancy as cardinality and `functional` were. Worth
merging, not at the end of a long day.

**How we would know it was wrong.** Hosts naming `association` for everything because the other
four never fit what they are recording — which would mean the set is right for an ontology of
terms and wrong for an ontology of a life.

---

## 2026-09-22 · One bad line must not cost the forty behind it

**Seen.** A second base run answered 8 of 20 where the first answered 14, while every count of
structure improved — 318 typed links against 299, 95 prose facts against 128, 26 types against
31. Six of the twelve wrong answers said the same thing: "X exists in the world but is not
recorded as …". The entity was there; the link was not.

Traced to the end: the host writes entities in one block and links in the next, forty or more to
a block. A statement raises, and every statement after it in that block is never run. Counted
over the run — **26 blocks of relations failed, holding 109 links, and 65 of those links were on
lines after the break.** Written by the host, never executed, never retried.

**Done.** A failing statement no longer ends the block. Each still runs in its own transaction
and a failure still rolls its own statement back; the rest of the block runs. The first failure
is raised as before, the others are counted and named in one line, and after three failures the
block is given up.

**Why this.** Per-statement transactions were half the answer and we have been treating them as
the whole one since they went in. They keep what happened before the break — and the loss was on
the other side, in what the host had already written and the world simply did not do. Three
failures is where carrying on stops paying: beyond that it is one misunderstanding repeated, and
running it forty times buries the one error that explains the rest.

**Not this.** Carrying on past a timeout. Out of time is out of time, and the statements after it
would not have run anyway.

**How we would know it was wrong.** A block whose later statements depend on the one that failed
producing a cascade of errors that hides the first — which is what the give-up after three is
there to prevent, and what to watch in the next run.

---

## 2026-09-22 · The looking happens on the way in

**Seen.** Two channels reach this host: the description it is handed every turn, and what comes
back from `run`. Counted over the base run — 393 calls to `run`, 39 to `describe_world`, 2 to
`describe_classes`, 0 to `classes_like`. Anything it has to ask for, it does not ask for.

**Done.** Before a block executes, the world reads it. Where it declares a class or a relation
type, the world looks for what it already holds under another word and says so — on the result
of that very call, with `describe_classes([...])` named.

**Why this.** Said afterwards it is a post-mortem; put in the prompt it is an instruction, and
the instruction was there and was ignored 46 times. On the way in it arrives attached to the line
that would make the duplicate, through the one channel that works. It also catches what the
check inside `define_relation` cannot: classes, and matches too weak to act on but worth naming.

**Not this.** Checking attributes the same way. Tried and measured: "given names / other names
they go by" reads 0.701 like `aliases` and 0.684 like `full_name` — seventeen thousandths between
the right answer and an unrelated field of the same class. Attribute names are short and their
descriptions formulaic, so everything on one class reads alike. A reminder that names the wrong
twin half the time is worse than none, so attributes are left out until something separates them.

**How we would know it was wrong.** Reminders on every second declaration. Three defences now
stand between a host and a duplicate — this one, the hand-back inside `define_relation`, and
`verify()` afterwards — and if the first is noisy the other two are enough.

---

## 2026-09-22 · The world looks, because the host does not

**Seen.** In the base run the host defined 46 relation types. It called `classes_like` or
`anything_like` **zero** times, in 392 code runs. The tool counts say the same thing about
studying at all:

    393  run                 393 times it wrote code
     39  describe_world      twice a batch, the description it is handed anyway
      2  describe_classes    twice, in the whole run
      1  describe_methods

The primer told it to look before inventing. It did not, and three of its types were another
type said twice.

**Done.** `define_relation` does the lookup itself, against the descriptions of the types the
world already has. Where the match is plain it hands back the existing type and says so, instead
of making a second. `define` has done this for classes since it was written; relation types had
nothing.

**Why this.** An instruction in a prompt is not a guarantee — the rule this project keeps
relearning. And the counts say something larger: anything reachable only by asking does not reach
this host. Two channels do — the description it is given every turn, and what comes back from
`run`. Knowledge belongs in those, which is where every hint added today went.

**Not this.** Warning on a loose match. At the threshold that catches near-misses, "married to"
reads like "associated with sport", and a warning that cries wolf stops being read — which costs
more than the duplicate it was meant to prevent. Only the plain case acts; the rest passes.

**Not yet.** Merging two types that are already there. It is written and works — 6 links moved
between the run's real duplicates — but it stays out of the host's reach for now, on the user's
call: with merging available the duplicate count gets cleaned up, and then there is no way to see
whether prevention works.

**How we would know it was wrong.** A host prevented from defining a type it genuinely needed,
visible as a type whose links mean two things at once.

---

## 2026-09-22 · Choose who to compare before building them

**Seen.** Identifying one entity built every entity of its class in order to score it. On the base
run's world — 709 entities, 195 of them people — a block of twenty `Person.new` calls took 13.9
seconds and was stopped at the sandbox's ten. Thirty-five of the ninety-four refusals in that run
were that timeout, the largest single group.

**Done.** Candidates are chosen from the image table before any of them is built: the same
similarity function on the same names and aliases, plus anything whose strong key equals the one
given. Only what could match is loaded. The same block now runs in 0.5 seconds.

**Why this.** The scoring was never the cost — building the objects was, and most of them could
not have matched. Narrowing by the same function that does the scoring is safe in the one way
that matters: it cannot drop anybody the full scan would have accepted. That mattered more than
the speed, because the failure mode of a wrong narrowing is not a slow world but two records of
one person, which no later telling repairs.

**Not this.** Narrowing by shared words or an index of names. Name matching is fuzzy on purpose —
"Wilma" and "William" share no word and must still be compared — so a word index would quietly
lose exactly the cases the matching exists for.

**Not this either.** Raising the ten-second limit. It is not the limit that was wrong; a world
that costs six tenths of a second to add one person is wrong, and at ten thousand entities the
raised limit would be reached again.

**How we would know it was wrong.** A twin created where the world used to ask — checked directly:
an exact name, a part of a name and a typo all still return a question, a different person with a
shared surname is still recorded separately, and a matching email still lands on the same person.

---

## 2026-09-22 · Classes are not fixed on a relation

**Seen.** The end classes were enforced twice: in `relate`, where a mismatch diverted the link to
the free type, and again in the `subject`/`object` attributes generated from the declaration,
which raised. The second is the one that fired in the base run, because the host reached the
relation through `take_in` rather than `relate` — and a host told
"affiliated_with_religion.subject must be a Person instance" defined
`affiliated_with_religion_thing_to_thing` on its next turn.

**Done.** The ends take anything. `relation["from"]` and `["to"]` stay in the spec — they
describe the type and give `verify()` something to measure an odd link against — but nothing
refuses a link for them. A link between other ends is recorded as asked, with a note saying what
the type has run between until now.

**Why this.** Which classes a relation runs between is the world's own bookkeeping: it holds the
links and can count them, where the host had to guess from the first example it saw. A guess is
not a promise to enforce. The host sets it up as it sees fit; the world records, counts and says
what it notices. Two enforcement points for one declaration was also how the first fix missed —
the fallback covered one door and the run went through the other.

**Not this.** Dropping the declared ends altogether. They are the only statement of what the type
is *for*, and `verify()` needs something to compare against; kept as description they cost
nothing.

**How we would know it was wrong.** Links arriving between ends so various that nothing can be
said about a type's shape — then the declaration was carrying weight we have just thrown away.

---

## 2026-09-22 · A role says who stands where; a class only says what it is

**Seen.** Every relation type in the core names its ends in prose — "the owner is the subject",
"the member is the subject" — and `Kin` tells a mother from a father by role, not by class, since
both ends are a Person. Types a host defines got `"a <kind> b"`, which says nothing, and the ends
declared as one class each. In the base run the host wrote `authored by` starting from the book.

**Done.** `define_relation` takes `subject_is` / `object_is` — what each end *is* in this link —
and generates the sentence from them. A side may also be several classes or left open, where
before it had to be exactly one. And the world can now say what it has actually seen at each end
(`ends_seen`), which is counted rather than promised.

**Why this.** A car is not barred from driving because it is a Car but because nothing that
drives is a vehicle: the role carries the meaning, the class only carries the kind. Roles also
hold what classes cannot — an inverse, synonyms, a limit — which the core already uses. And which
classes stand where is the world's own bookkeeping: it has the links and can count them, where
the host had to guess from one example.

**Not this.** Going further now — verification by role, and a world that corrects its own declared
ends from what it sees. Both follow from this and both were left, on the user's call, until there
is more evidence of how it goes in practice.

**How we would know it was wrong.** Hosts naming roles that are just the class again ("person"
and "thing"), which would mean the distinction is not reaching them.

---

## 2026-09-22 · The world checks its own links and refuses none of them

**Seen.** End types were doing one useful thing — catching a link written from the wrong end —
and one harmful thing: refusing facts at the door, which cost 51 facts to prose and two duplicate
types in one run.

**Done.** `world.verify()`: three findings over what the world holds, none of them a refusal —
a link running against the direction the rest of its type runs, a type narrower than the links it
holds, two types of the same shape whose names read alike. On the base run's world it names the
three duplicate pairs the host built.

**Why this.** The same declaration is worth keeping and not worth enforcing: as a gate it loses
facts, as evidence it answers questions nobody could ask. Each finding says what was seen and what
would settle it, because every one has an innocent reading — a relation that genuinely runs both
ways is not a mistake. The arithmetic picks the few; reading them is for the model, which is the
same division `restructure` uses.

**How we would know it was wrong.** Findings nobody acts on. A report that is never settled is a
report nobody reads, and it should then be a refusal after all or nothing.

---

## 2026-09-22 · A type declared from the first example may not reject the second

**Seen.** In the base run the host defined `affiliated_with_religion` as Person → Thing, from the
first fact it saw. Then "Kingdom of Ireland is affiliated with Zoroastrianism" arrived, the world
refused on the ends, and the host's very next move was to define
`affiliated_with_religion_thing_to_thing`. The same happened with
`associated_with_sport_person_thing`. Two of the 31 types the host built were duplicates of
another one, named after the classes that did not fit.

The refusal came through `take_in`, whose end check used one unordered set of both sides, so a
Thing → Thing link passed a Person → Thing type and failed where it was written rather than where
it was chosen.

**Done.** Each end is checked against its own side, in the direction it would be taken in. Links
that say the word but do not fit the ends stay free, and the world says which type they were
reaching for and that the type is probably narrower than the facts.

**Why this.** End types are worth having — they are what a relation's checks are made of, and our
core types encode real behaviour that derived attributes depend on. But a type the host declared
five minutes ago from one example carries no such knowledge: it is a guess, and the second
example is evidence about the guess, not a violation of it. Refusing there does not protect the
data; it costs a turn and buys a duplicate, which is worse than the narrow type was.

**Not this.** Widening the type automatically. A type whose ends grow to fit whatever arrives
stops checking anything, and the one case an end check really catches — a link recorded backwards
— would go through silently.

**Still missing.** A host cannot widen a type it has declared: `define_relation` refuses the name
and there is no `widen`. The world now names the problem and offers no call for it, which is the
state we criticise everywhere else. That call is the next thing owed here.

**How we would know it was wrong.** Types accumulating with ends so wide they never refuse
anything — then the check has become decoration and should be removed rather than kept as ritual.

---

## 2026-09-22 · The base earns its keep; our classes have to earn theirs

**Seen.** The same 455 facts recorded twice by the same model. Once against our twenty fixed
classes, once against the base alone — Thing, Related, Person, Agent, and the calls to define
what turns out to need defining.

|                              | our classes | the base |
|------------------------------|------------:|---------:|
| entities                     |         530 |      709 |
| nothing said about them      |    75 (14%) |  60 (8%) |
| typed links                  |         114 |      299 |
| facts written as prose       |         212 |      128 |
| host runs ending in a refusal|         31% |      24% |
| questions answered           |       12/20 |    14/20 |

The host on the base defined 31 relation types of its own, and the count settled — 3, 7, 9, 13,
16, 18, 19, 19, 20, 20 — with the turns per batch falling from 41 to 8 as it did. By the end the
world was asking for one type it had not got.

**Done.** Nothing yet, beyond the measurement. What this settles is the standard: our fixed
classes are filling, not foundation, and each of them has to show it makes the work easier than
the base alone.

**Why this.** The accuracy is the one number that cannot separate them — twenty questions at
p≈0.6 is one sigma of 2.2, so 14 against 12 is the same number. Everything that can be counted
deterministically moved one way: two and a half times the structure, forty per cent less prose,
fewer refusals. A pre-made class is only help if it saves the host work, and on this material
ours cost it work — turns spent fitting facts into classes meant for something else, which is
how seventy things ended up inside `Idea`.

**Not this.** Reading 14 against 12 as the world getting better. It is not distinguishable, and
saying so would be the same mistake that had us "fix" a restructuring pass on a 9-against-7
difference earlier the same day.

**How we would know it was wrong.** A base run on material where the classes fit — a job search,
a move, a household — losing to the fixed set on the same counts. This was one benchmark of
encyclopedic facts, which is the case our classes were least designed for.

---

## 2026-09-22 · A word the world took is a word it answers to

**Seen.** A host wrote `a.relate(b, "related", label="plays position")` and then read it back with
`goalkeeper.related("plays position")`. The world refused: "no relation type 'plays position'".
It had accepted the word on the way in and would not answer to it on the way out.

**Done.** A read by a word that is not a type looks through the free links by their label. A word
that is neither a type nor a label anybody has used is still refused, with the nearest label
suggested.

**Why this.** Acceptance that cannot be read back is worth nothing: the fact is in the world and
the host cannot reach it, which is indistinguishable from not recording it. The refusal for an
unknown word stays because answering "none" to a word the world has never heard reads as "there
are no such links", and a typo would pass for an answer.

**Not this.** Making every free link's label a real relation type on the spot. A label is a word
somebody used once; a type carries cardinality, direction and whether it holds one at a time.
Promoting every word to a type fills the vocabulary with types nobody checked.

**How we would know it was wrong.** Hosts reading by label instead of defining types at all —
the vocabulary would stop growing while the free links kept piling up.

---

## 2026-09-22 · A gap is not a refusal

**Seen.** `Idea` declares `content` required. Of seventy things a host tried to record in a
455-fact run, ten were lost outright; the rest got through by filling the field — "Novel by
Robert A. Heinlein" for one, an empty string for eight. Those inventions went into the record as
`source=agent`, indistinguishable from what the person actually said.

**Done.** A required attribute that is not the one identifying the entity no longer blocks
creation. The entity is made without it and the host is told not to invent one.

**Why this.** A required attribute the host has not got is an invitation to invent one, and an
invented value is worse than a missing one: the record cannot tell it from something the user
said, and every later answer inherits it. The identifying attribute stays required, because an
entity nothing can identify breeds duplicates, and that is a defect no later telling repairs.

**Not this.** Holding the creation as a question for the user. The user does not know the content
either — it is the host's to supply when it has it. A question here would be work moved to the
one person who cannot answer it.

**How we would know it was wrong.** Entities accumulating with nothing but a name, where the host
had the information and simply did not write it.

---

## 2026-09-22 · A link the world cannot type is still a link

**Seen.** 600 host runs in one 455-fact run, 258 with an error. 72 were "this relation type does
not take these ends" and 22 were "no such relation type". In 51 of those the host's very next
move was `describe(...)` — the fact written out as a sentence.

**Done.** A relation whose declared ends do not fit, or whose type does not exist, is recorded
under the free type with the host's own word as its label, and the host is told so.

**Why this.** Prose cannot be superseded: a later correction settles beside the old sentence
instead of replacing it, so the question stops having an answer. A refusal is only worth making
when it protects the data; a type mismatch protects nothing and costs the fact. The label is not
waste — a word that keeps coming back is how the world finds the type it is missing.

**Not this.** Widening the type to fit. The type's ends are what its checks are made of, and
widening them silently would turn one wrong link into a licence for all of them.

**How we would know it was wrong.** Free links accumulating under labels that already have types
— the world would be accepting sloppiness rather than absorbing novelty.

---

## 2026-09-22 · One word for one place

**Seen.** Three slots held free text: `descriptions` (dated, in the texts table, supersedable),
`notes` (a plain string on four classes) and `description` (a plain string on two). A host wrote
into whichever it remembered.

**Done.** `descriptions` is the only place it is stored. `notes` and `description` read the
latest of them and write one more. Statements recorded under the old names are read as
descriptions, so worlds written before this keep what they said.

**Why this.** Only one of the three carried a date, a source and a period — the other two could
not be superseded and could not be crystallised out of. Three names for one thing also means
three places to look, and anything that reads free text had to know all three.

**How we would know it was wrong.** Hosts wanting a single summary line that is not the latest
description — then `notes` is a real attribute and not a spelling of this one.

---

## 2026-09-23 · A time is said, never assumed

**Seen.** Superseding a one-at-a-time relation wrote `valid_until = today`. Today is when
somebody *mentioned* it, not when it ended, and the two are stored in the same field — so a
fabricated date became indistinguishable from a known one. The evidence: across 392 runs the
host passed a date zero times, and 0 of 1319 statements carried a `valid_from`.

**Done.** Nothing is dated unless a date was given. What holds is decided by what was said
last, as it always was for an attribute. `starts=` takes words — `'now'`, `'yesterday'`,
`'3 years ago'`, `'in 2006'` — and takes a bound where only one edge is known:
`before(now())`, `after(date(2006, 1, 1))`, the same words the host already asks questions
with. A bound is stored as its date plus `from_is` / `until_is`, so "before" survives storage
instead of collapsing into a date that looks certain. `holds_at()` has three answers, and the
third is *nobody knows*. An unreadable time is refused with the vocabulary in the message.

**Why this.** Writing a date the world was never told is the one error that cannot be found
later: it reads exactly like a fact. Refusing the statement would lose it; taking words keeps
it at the precision it was said at.

**Not this.** Requiring an exact date — most of what people say about time has no exact date,
and the requirement would be met with an invented one.

**How we would know it was wrong.** Hosts writing `starts='now'` on everything to get past the
ask — then the ask has become a toll rather than a question, and it belongs only where the
missing date changes which fact holds.

---

## 2026-09-23 · What the world guessed outlives the run that guessed it

**Seen.** A type invented for an unknown word, and a handover decided by statement order, were
announced as hints. Hints live for one run. The assumption lives in the world for good, and the
next task had no way to learn one had been made.

**Done.** Both raise a question, which persists: once per invented type (its nature, the
options listed), and on the link where a missing date decided which of two holds.

**How we would know it was wrong.** The open-questions list filling with the same shape faster
than anybody answers it — then the world is talking to itself.

---

## 2026-09-23 · A pinned name lives for the task, or past it, and says which

**Seen.** Names were kept for three turns and then dropped, so a host could pin something on
purpose and get a `NameError` for it mid-thought. Meanwhile `world_variables` held 0 rows
across 392 runs — the channel existed and nobody used it.

**Done.** The term in turns is gone. `world.pin(name, value, "...", keep=...)` has no default:
`keep=False` lives as long as the task, `keep=True` until it is unpinned. Nothing is promoted
on its own.

**Why this.** The world cannot see a conversation start or end — the session key comes from a
header the host sets once in its connection config, or from the client app's name. So the
boundary has to be one the host states, and what survives it has to be a judgement somebody
made, not one the world inferred from a name having been useful once.

**How we would know it was wrong.** `keep=True` on everything, or on nothing — either means the
question is being answered by reflex instead of judgement.

---

## 2026-09-23 · A task is the only boundary the world can see

**Seen.** Everything that needs to know where one piece of work stops — which pinned names are
still yours, what was left unanswered, what a fact was recorded for — was hanging on the
session, and the session is not a conversation: its key comes from a header the host sets once
in its connection config, or from the client application's name. It outlives conversations and
is shared between windows.

**Done.** `Task` is an entity, marked `own: true` — the world's own bookkeeping, listed apart
from the person's life in the catalogue. `start_task(stated, mode)` opens one at the tool
level, before any `run`: `stated` is what the work is, in a sentence, and `mode` is *recording*
or *answering*. `finish_task` closes it and works out how it closed rather than taking the
agent's word: **done** when nothing is open about what it touched, **left_open** otherwise,
with what is open named back. The task keeps `runs`, `touched` and `closed_as`, and stays
readable after it closes.

**Why this.** The world had no way to ask "did that work finish cleanly", and no way to know
why it was being written to. A stated task gives it both, and a computed close makes the answer
something it checks instead of something it is told.

**Not this.** A `tasks` table beside `runs` — cheaper, and it keeps the user's world purely
about the user, but then a task cannot be reached with the same means as everything else and
needs an API of its own. `own: true` gets the separation without the second vocabulary.

**How we would know it was wrong.** Tasks opened per `run` rather than per piece of work, or
`stated` filled with the same sentence every time — then it has become a ritual, and the
boundary it marks is not a real one.

---

## 2026-09-23 · A task does not close over what it left undecided

**Seen.** `finish_task` reported what was still open and closed anyway — which is the failure
the entry above warned about, one paragraph after writing it down. A batch of facts raises a
doubt per fact, and each one is read while the agent is already writing the next; by the
fortieth nobody remembers the third was raised. Reporting is not checking.

**Done.** `finish_task` refuses while any doubt about what the task touched is still nobody's
decision, and names them with how to settle each. Every run carries `[undecided N]`, so the
count is in front of the agent as it works rather than only at the end.
`world.undecided()` reaches them — they hang on the links the task made, not on one entity, so
no single entity finds them. Three ways past, all of them somebody's decision on the record:
`q.answer(said)`, `q.for_the_user(why)`, `q.drop(why)`; and `finish_task(abandon="why")` for a
task that cannot be done, which keeps what was recorded and the reason with it.

**Why `for_the_user` is a third state.** An agent sent to record facts often genuinely cannot
know whether two people with one name are one person. Guessing files a fabrication under the
user's name; dropping pretends the doubt was never real. So the question stays open and visible
to the user, and stops blocking — because somebody looked at it and said it was not theirs to
settle. A task closing that way is `for_the_user`, not `left_open`: handing one on is not
failing, and the world should not name it as if it were.

**How we would know it was wrong.** `q.drop` used on doubts that were real — the reason is kept
with each one, so this is checkable. Or tasks abandoned rather than settled, which would mean
the check has become a wall instead of a question.

---

## 2026-09-23 · What the first batch of facts showed

**Seen.** Ten facts to a recorder agent, against a base world. The result: 11 Things, 10 People,
**8 free links, 0 types made, 0 tasks recorded**. None of the machinery built that day fired.
Three separate causes, each invisible on its own:

1. **`Task` was not in `BASE_CLASSES`**, so `start_task` raised `KeyError` — and the MCP tool
   reported `Error executing tool start_task`, with no reason. The agent called it twice, got
   nothing back either time, and sensibly carried on without a task. Then `finish_task`
   answered *"Task closed"* over a task that had never existed.
2. **The primer taught the wrong default.** It showed `relate(x, "related", label="created in")`
   as the way to write a link with no type — an instruction written when free links were the
   answer, and left standing after unknown words began making types. The agent followed it
   exactly, so no type was ever made and no question was ever raised.
3. **The census counted rows, not entities.** Image tables are key-value, so ten facts read as
   "100 people" and the first run could not be read at all.

**Done.** `Task` is in the base — the boundary has to exist before any work does. A failing
tool says what failed and what it means for the work. `finish_task` returns `None` rather than
`""` when no task was open, and the tool says so plainly. The primer says: write the word you
would say, and the world makes the type; `relate(..., "related", label=...)` is the escape
hatch for a link that genuinely has no word, and it buys nothing.

**Why this is worth an entry.** Every one of the three was a default nobody chose — the class
list, the error text, the old example — and all three pointed the same way: the agent did
exactly what it was told, and what it was told was out of date. The lesson is not about tasks.
It is that a run which produces *no* failures is not evidence that the machinery works; only a
run where the machinery visibly fires is.

**How we would know it was wrong.** A second batch that still makes no types — then the primer
is not the reason and the type-making itself is unreachable from where the agent stands.

---

## 2026-09-23 · The world asked for a thing it had no name for

**Seen.** Eight runs of the same ten facts, each fixing what the last one exposed. Run 5 and 6:
the recorder made every type correctly, then spent ten runs trying to amend them —
`BornIn.nature`, `born_in.nature`, `Person.born_in.nature` — and finally handed all eight
questions to the user. It was right to give up. Nothing it could have written would have
worked:

- **A class the world grows mid-session is never put in the namespace.** It is filled with the
  classes that existed when the session opened, so a type invented from the host's own word
  could not be reached by any spelling. Two spellings gave `NameError`.
- **The third spelling was worse than an error.** `Person.born_in` is the lent relation
  *method*; setting `.nature` on a function succeeds and does nothing.
- **An amendment was never written back.** `nature`/`changes`/`one_per_subject` mutated the
  spec in memory only, so a ruling survived until the process ended and then quietly reverted
  to the world's guess.

**Done.** Every class the world holds is put into the namespace after each run, under its class
name and under the word the host says it with. Amending a type marks it `said_by_hand` and
writes the spec back to the grown directory.

**Also: a prose answer is repeated, not refused.** Answering "one spouse at a time, can change"
used to be rejected outright, and the recorder responded by handing every question to the user
rather than working out the call. Now the words are read for what they imply and the question
comes back with the line they mean — `married_to.changes = True` — so the agent edits one line
instead of rereading the manual. The type must still be amended; only the tone changed, and the
tone was the difference between a recorder that settles eight questions and one that punts all
eight.

**Where it got to.** 0 free links, 10 typed, 8 types made, all 8 ruled on and kept, task closed
`done`, 14 runs, $0.18. From: 0 types, 10 free links, 0 tasks.

**Still standing.** Every type came out `functional: True` — nobody set `changes=True` on
`married_to` or `worked_in`, so a second spouse reads as a correction of the first rather than
one that ended. It gives the right current answer and the wrong history, and it is the next
thing to look at.

**How we would know it was wrong.** A recorder that amends types it has no opinion about, just
to clear the question — the ruling is kept with its answer, so this is checkable.

---

## 2026-09-23 · Reading ten facts one by one, which counting could not do

**Seen.** The counts said the batch was clean: 0 free links, 10 typed, 8 types, task closed
`done`. Read fact by fact, one in ten was recorded as something else — "The director of the
BBC is Tony Hall" went in as `ChairpersonOf` — and two more were backwards: the world itself
printed *"Fatah is Mahmoud Abbas's chairperson"* and nobody read it. A later run had Amy
Winehouse **born** in Camden Town and Pedro Pierluisi **born** in Washington, from a recorder
that wrote `died_in_city` and `worked_in_city` correctly four times each.

**Cause — the world's own reasoning, in two places, both silent.**

1. `define_relation` handed back the nearest existing type instead of making the one asked for.
   The auto-description is a template — "one person *director* of one thing" — so every type's
   description is the same sentence with a word swapped, which inflates every comparison:
   "director of" against "chairperson of" is 0.708 as words and **0.853 inside the frame**,
   over the 0.82 bar.
2. `resolve_kind` fell back to `did_you_mean` and took the near word as the type:
   "worked_in_city" scores 0.769 against "born_in_city", "died_in_city" 0.667. Four correct
   writes, four silent rewrites.

**Done.** Neither substitutes any more. A word with no type makes its own type, and where
something similar exists the world *says so* and offers `take_in` — the agent has the sentence
the user said, the world has a number, and the number was wrong twice out of ten. The
type-made question now quotes the sentence the world read it as, so the direction is something
to answer rather than something printed past.

**Measuring it.** `experiments/first_batch.py` reads each fact against the world every run:
both ends joined, the type's word against the fact's own words, and the direction where the
sentence shape makes it plain ("The <role> of <A> is <B>" — B holds the role). It catches
exactly the three failures above and nothing else on this material.

**What is not settled.** Direction errors and whether a task gets opened vary run to run, and
a single run of ten facts cannot tell an agent's bad turn from a world's defect. The two world
defects above are settled because they are in the code path, not in a score.

**How we would know it was wrong.** Types multiplying for one idea — "born_in", "was_born_in",
"birthplace" all held apart with nobody merging them. `world.wanted()` and `take_in` exist for
that, and the near-neighbour hint points at it; if they go unused, the merge belonged
somewhere after all — but later, and said out loud, not inside the write.

---

## 2026-09-23 · The world's own description was the evidence it judged by

**The case, kept because the shape of it will come back.**

An agent wrote `relate(tony_hall, bbc, "director_of")`. The world recorded Tony Hall as the
BBC's **chairperson**. Nothing failed; every count said the run was clean.

The world invents a description for a type it makes, from a template:

    f"one {subject class} {word} one {object class}"

So the two strings compared were:

    A: director of. one person director of one thing
    B: chairperson of. one person chairperson of one thing

Nine words, eight of them identical. The embedding measures the whole string, so the shared
frame carries the score and the one word that differs barely moves it:

| | similarity |
|---|---|
| the two framed sentences | **0.853** — over the 0.82 bar, so: merge |
| the two words alone | 0.708 — under it |

**The template was that morning's fix for the opposite failure.** Descriptions used to be built
from the entities in front of the world — "Thomas Kyd is to London" against "Amy Winehouse is
to Camden" — which read as far apart, because they are, so one idea got four types. Taking the
names out fixed under-merging by making every description the same sentence, and created
over-merging in the same stroke. One threshold, two opposite errors, hours apart.

**The general fault.** The world was comparing text it had written itself. There is no
independent evidence in an auto-generated description — only a restatement of what the world
had already assumed — so the number measured the template, not the words. A threshold over
self-generated text cannot be tuned into correctness; it can only be moved between the two
failures.

**The rule taken from it.** Where the world would decide something from a similarity, check
what the text being compared is made of. If the world wrote it, the number is about the world.
Say what was noticed and let whoever has the real evidence — the agent, who has the sentence
the user said — decide.

**Where it is written down.** `terraweaver/initiative.py`, one switch per thing the world does
on its own, all off — this one as `MERGES_MEANING`, and the spelling-distance substitution in
`resolve_kind` as `TAKES_NEAR_WORD`. Both were deleted first and put back behind switches on
the user's point that a switch costs nothing and deletion throws away the ability to reproduce
the failure. `tests/test_initiative.py` does exactly that: with `TAKES_NEAR_WORD` on,
`worked_in_city` lands in `BornInCity`; with it off, the write is refused and the agent is
handed the `define_relation` call to write. The argument against turning them on stands; it was
never an argument for having no switch.

---

## 2026-09-23 · Nothing automatic, so that adding facts can be watched

**Seen.** Every defect found reading the batch fact by fact was the world acting on its own,
and each was invisible in the counts. Debugging them together is guesswork: an error can be the
agent's turn, the world's refusal, or something the world did quietly in between.

**Done.** `terraweaver/initiative.py` holds every action the world takes unasked, one named
switch each, **all off**:

- `MAKES_TYPES` — an unknown word makes a type. Off: `relate` raises and names the
  `define_relation` call to write.
- `REROUTES_BY_LABEL` — a label moves a link to the type that label belongs to.
- `LEARNS_NAMES` — a name settled once is applied later without asking.
- `MERGES_MEANING` — two words read as one idea by embedding similarity.
- `TAKES_NEAR_WORD` — an unknown word read as the nearest one by spelling distance.

Each test that exercises one turns that switch on for its own block and puts it back, so both
the plain world and the automation stay covered.

**Why this order.** Recording facts by hand is the thing everything else is measured against,
and there is no baseline for it yet. Automation goes back on one switch at a time, against a
world already read fact by fact, so what each one changes is attributable.

**How we would know it was wrong.** Hand recording that cannot be made to work at all — then
the automation was carrying something load-bearing and the order should be reversed.

---

## 2026-09-23 · The world answers structural questions; semantic ones are the host's

**Seen.** Asked why the world could promise to work out what a word meant, the answer is that
it held a model to do it with: `authoring.install` puts `world.meanings.model` within reach of
the write path, so at the moment of recording a fact the world had semantics to hand and used
them. Both fact-rewriting failures came from there.

**The rule is not "deterministic only".** The worse of the two was `difflib` — wholly
deterministic, no model, and it turned "worked in" into "born in" four times without a sound.
The fault is not the method but the question: a semantic question answered by a deterministic
method is still a semantic question the world had no standing to answer.

So the line is drawn by what is being decided, not by how:

- **Structural, the world's own, decided in the write** — does this type exist, does this value
  fit what was declared, do these periods overlap, is this end of the right class, is this link
  already here. Deterministic, checkable, and the world holds the evidence.
- **Semantic, never the world's** — are these two words one idea, is this the same person, is
  this word a misspelling of that one. The evidence is the sentence the user said, and the
  world does not have it. The agent does.

**Done.** Every remaining call to the meaning model is now either advisory or asked for:
`_one_idea` and `look_alike` (listings), `_reads_like` (the pre-run reminder), `classes_like`
and `take_in` (the agent calls them), and `_relation_like` inside `define_relation`, which with
`MERGES_MEANING` off only says what it noticed. None of them acts unasked inside a write.

**What this does not change.** The world still says everything it notices. With every switch
off, defining `birthplace` next to `born_in` still answers: *"'birthplace' reads a lot like
BornIn — I have made birthplace as you asked; if they are one idea, `world.take_in(BornIn,
"birthplace")`."* Noticing is not deciding, and only the deciding was taken away.

**How we would know it was wrong.** The world unable to refuse something it plainly should —
if a real data check turns out to need semantics, the line is in the wrong place and the check
belongs to the agent with the world stating the constraint.

---

## 2026-09-23 · A world was writing down the types it grew and never reading them back

**Seen.** The second batch of ten facts, into the world the first had built, recorded a
marriage as `Kin` while an unused `MarriedTo` sat in the same world, and made `Plays` beside
`PlaysPosition`. Twenty facts, sixteen types, twelve of them holding a single link. The agent
had called `describe_world` and the catalogue it got back did not contain `married_to`,
`plays_position`, `died_in` or `chairperson`. It could not reuse what it was not shown.

**Cause, in two parts.** `--base` built the world from `base_specs`, which loads with
`grown_dir=Path("/nonexistent")` — right for making a base world, wrong for reopening one that
had grown. And underneath that, `growth.apply_growth` only understood an *extension* of a core
class (`extends: "Person"`); a whole new class, which is exactly what `define_relation` writes,
was refused. So types were saved on definition and **never read back by anything**: reopened,
the world held the tables and the files and none of the classes.

**Done.** `apply_growth` takes a whole class as itself, and `--base` starts from the base specs
plus whatever that world was taught. "Base" is what the world ships with, not an instruction to
forget.

**Measured, same two batches, same agent.**

| | types for 20 facts | holding one link | duplicate ideas |
|---|---|---|---|
| before | 16 | 12 | `Plays`/`PlaysPosition`, `Kin`/`MarriedTo`, `WorksFor`/`ChiefExecutiveOfficerOf` |
| after | 14 | 9 | none |

and the facts themselves went from 8/10 to **10/10**, with batch one at 10/10 both times.

**How we would know it was wrong.** A world that cannot be given a genuinely fresh base because
an old `grown/` beside the database keeps being picked up — the directory is chosen from the
database path, so a new database in an old folder inherits its vocabulary.

---

## 2026-09-23 · Two refusals that cost a run each, and a success reported over an empty world

**Seen.** `define_relation` refused one missing argument at a time. A recorder that gave none of
`nature`, `cardinality`, `over_time` spent **forty-one runs** collecting them one refusal per
run, gave up on links, and finished by reporting "all ten facts have been recorded into your
world — the world kept everything." The world held eight bare names: no links, no attributes,
no remarks. Every count agreed with the agent.

**Done.** Two things, both the world's own business and both deterministic:

- `define_relation` names everything missing in one refusal and writes out the call to send.
- `finish_task` will not close a **recording** task that recorded nothing — entities and their
  names are not facts about anything. It says so and offers `abandon="why"` instead.

**Why the second one matters more.** A refused write is visible; a task that recorded nothing
and said otherwise is not. The world cannot check whether what was recorded is *true*, but it
can always check whether anything was recorded at all, and that is the difference between a
failure and a silent one.

**How we would know it was wrong.** A recording task that legitimately records only names —
if "add these six people, I will say what about them later" is a real request, this refuses it,
and the check should look for the entities being new rather than for statements about them.

---

## 2026-09-23 · Required attributes: a check that was there, and a word that was not

**Asked.** Does the world check that required attributes are filled when a relation or an
entity is created — a deterministic check, nothing to do with the reasoning that was switched
off?

**It does, and it always did.** `Entity.__init__` collects every declared `required` attribute
that was not given, for relations as for entities, and none of it goes through
`initiative.py`. What varies is not whether the check runs but what it does:

| | on a missing required attribute |
|---|---|
| the attribute that names the thing (`name`, `full_name`) | **refuses** |
| `Related.label` | **refuses** — a free link nobody can name is unidentifiable |
| everything else | **left empty, and said out loud** |

The last row is a measured decision, not a lapse. On a 455-fact run `Idea` required `content`:
of seventy things the host tried to record, ten were lost outright and the rest got through by
inventing one — "Novel by Robert A. Heinlein" for one, an empty string for eight — and the
inventions entered the record as `source=agent`, indistinguishable from what the person said.
A field that must be filled to get past a check gets filled with the host's own knowledge.

**What was actually missing.** `Authoring.attribute()` had no `required` parameter at all, while
`_attribute_spec` took one. A host building its own vocabulary could not say that a thing must
have something — the word was accepted by the call and silently dropped. Now it passes through.

**How we would know it was wrong.** Hosts declaring everything required and reading the hints
as noise — then "required" has come to mean nothing, and the ones worth refusing over need to
be said differently.

---

## 2026-09-23 · A task does not close over things it never described

**Seen.** Twenty facts landed correctly and left three universities filed as a place, an
abstraction and an agent, and three football positions as objects and an abstraction. Nothing
in the world could have caught it: the only thing it knew about any of them was a name, and a
name is a handle, not an account.

**Done.** `finish_task` will not close a recording task while something it put in the world has
no description — entities and links alike — and names what is bare. The primer and the refusal
both say what the line is for: *what it is here and why it turned up*, not what the agent
happens to know. "the capital city of the United States" is an encyclopaedia entry nobody said;
"the city Pedro Pierluisi worked in" is the reason it is in this world.

**Why a task check and not a required argument.** `new(...)` and `relate(...)` are called from
268 places in this repository alone, and a refusal at the write would have meant rewriting all
of them for an unvalidated change. The evidence also says a hint would be ignored — the date
hint fired in 392 runs and was answered in none — while what blocks `finish_task` gets
answered: a recorder settled eight of eight questions when it could not close without them.

**What it bought, measured on the same ten facts.** With descriptions required, the agent's own
classification came out more consistent unprompted: BBC and University of Minnesota both
`agent` (before: agent and abstraction), goalkeeper and wide receiver both `abstraction`
(before: object and object against `center` as abstraction). Having to say what a thing is
makes one classify it the same way twice.

**And the remaining error became visible.** `Fatah — abstraction — "a Palestinian political
party"` beside `BBC — agent — "a major British broadcasting organization"`. Two organisations,
two natures. Before, there was nothing to compare; now there is text the world did not write,
which is the only kind it can honestly judge by — see "The world's own description was the
evidence it judged by".

**How we would know it was wrong.** Descriptions that restate the name ("London is London") or
fill with general knowledge — then the check is being satisfied rather than answered, and what
it buys is nothing.

---

## 2026-09-23 · `Agent` the class and `agent` the nature are two things with one name

**Seen.** `Thing.nature` is `enum[place, agent, event, object, abstraction]`, and `Agent` is a
base class holding exactly one instance — the assistant, the second of the two parties a world
is between. A host reading `describe_world` sees both, and nothing distinguishes them. In the
run measured, `nature="agent"` was given to the BBC and the University of Minnesota, correctly;
putting them in the `Agent` class instead would have been just as well supported by what the
world says about itself.

**Done.** The class is `AIAgent`. The nature keeps its five readable words, and the bound name
`agent` still means the assistant in every namespace — what changed is the one thing that read
as both: a class called `Agent` sitting in the same catalogue as a nature called `agent`.
Renaming the nature instead would have meant arguing about `organisation` (too narrow for
anything that acts) against `actor` (wider and vaguer), for a word the EvoOntology set gives us
plainly.

Worlds written before it keep the assistant in an `Agent` table; opening one moves it and its
statements into `AIAgent` rather than building a second assistant beside it and leaving the
first behind looking like a class of its own.

**How we would know it matters.** A host putting an organisation into the `AIAgent` class, or a
question about "agents" answered with the assistant and a broadcaster in one list.

---

## 2026-09-23 · "Now" is when you are being told, not when it began

**Seen.** Two facts about one thing, recorded in one breath — the shape of 143 of the
benchmark's statements. With no date, the handover works: the later one holds and the first
stays in the record. With `starts="now"` on both, **the second was refused and was nowhere in
the world afterwards.** The fact was lost.

Two things built the same day collided. "Time is said, never assumed" tells a recorder to say
when; "a dated link is not ours to end" refuses to supersede one that carries a date. Between
them, a recorder that does as it is told destroys every supersession — which is the whole
subject of the material.

**And the deeper fault is mine.** `starts="now"` is the same invented date the world stopped
writing, moved one step out. I took the fabrication away from the world, which at least knew it
was guessing, and handed it to the agent, which states it as fact. A default nobody chose is no
better for having been typed by somebody else.

**Done.** Two fixes, and they are different in kind:

- **`"now"` is the telling time.** It answers "when are you telling me this", which the record
  keeps anyway in `stated_at`; it is not a claim about when the fact began, so it no longer
  becomes a `valid_from`. The world says what it did and what to write instead —
  `starts="today"` if the fact really began today, `starts=before(now())` if it began earlier
  and nobody knows when. `"today"` and a plain date are claims and still stored as such.
- **Equal dates are not evidence of an overlap.** When the new link starts at the same moment
  as the standing one, the dates carry no ordering at all, and refusing over them loses the
  fact. Statement order decides, exactly as it does undated. Both the `functional` and the
  `inverse_functional` branch of `_check_functional` had this, and only one of them was fixed
  first — the second was found by the test, not by reading.

**Pinned.** `tests/test_time.py` runs the handover three ways — no date, `starts="now"`,
`starts="2020-01-01"` — and requires the later one to hold and the first to stay in the record
in all three.

**How we would know it was wrong.** A host that means "it began this very moment" and finds no
start recorded. It has `starts="today"`, and if the instant matters it has a datetime; what it
cannot have is the word that also means "I am telling you now".

---

## 2026-09-23 · When a link began is said, and the nature decides which links must say it

**Seen.** Requiring a start wherever the cardinality said "one at a time" reached `part_of` and
`kind_of` — a department is part of a company and nobody states the day that began — and
refused facts nobody had a date for. The requirement was inferred from the wrong thing.

**Done, and the shape of it matters more than the rule.** `starts_required` is a `BY_NATURE`
entry, beside `transitive` and `symmetric`, which is what the natures were introduced for:

| nature | start required |
|---|---|
| `part_of`, `kind_of`, `same_as` | no — an arrangement, not an event |
| `derived_from` | no — it holds from the moment of what it was drawn from |
| `related_to` | when the type holds one at a time |

**And the old refusal had to go with it.** "A dated link is not ours to end" was written when
ending one meant inventing its end date. With starts required, every handover carries two dates
and the rule refused every one of them. It no longer has to invent anything: **the new link's
own start is where the old one ends**, and that is a date the host gave. A start *earlier* than
the standing one is still refused — that is a claim about a stretch already spoken for, and
which of the two is wrong is not the world's to pick. Symmetry is checked first and no date
overrules it: ending a partnership is a claim about both people.

**Measured, all seven cases at once:**

| | |
|---|---|
| `related_to` that changes, no date | refused, with the call to write |
| one moment taken once, passed to both | hands over, both kept |
| two separate `now()` calls | hands over — the second is later |
| the second starts later | hands over at the new start |
| the second starts earlier | refused |
| `part_of` with no date | recorded |
| symmetric partner, both dated | refused |

**How we would know it was wrong.** A `related_to` type that genuinely has no beginning worth
stating — then `over_time` is doing two jobs and the type needs to say this one itself.

---

## 2026-09-23 · A correction that announced itself and changed nothing

**Seen.** Asked what still needed fixing, the answer turned out to be the largest thing of the
day, and it was a regression introduced that same morning. Removing the invented end date from
`_correct` left it printing *"taking the later as a correction — what was said earlier stays in
the record and is not what holds"* while doing nothing at all. Measured:

    org.relate(Dublin,  "hq_in")
    org.relate(Tallinn, "hq_in")
    holds: ['Tallinn', 'Dublin']        # one organisation, two head offices

Every type the recorder declared `over_time=False` — eight of nine in the run measured — did
not supersede at all. Only `over_time=True` types, which end the previous one at the new one's
start, worked. The counts agreed with the agent that ten facts were recorded, because ten were.

**Done.** What holds is decided on the way out, where a slot has always decided it: for a type
with one value and no more, the latest telling, the rest read as history. No date is written,
because a correction is not a change — being told "its head office is Tallinn" after "…is
Dublin" is not news that it moved. `history=True` and `any_time=True` still give everything.

    holds: ['Tallinn']
    any  : ['Tallinn', 'Dublin']

**The second shape, and what the world can do about it.** Supersession also fails when the
changing part is the *subject*: "the chairperson of Fatah is Mahmoud Abbas" then "…is Yasser
Arafat" are two different subjects, and `functional` constrains only the object. The world
cannot know that an organisation has one chairperson — that is what the word means and it has
only the shape — but it can count, so a second holder of the same object now raises a question
naming the fix (`chairperson_of.one_per_object = True`), once per type and object.

**And two smaller things found while measuring it.** Grown classes were bound into a session's
namespace only after a run, so a session opening onto a world full of types could not name one
until it had written something — while the world was asking it to amend a type by a name that
raised `NameError`. And `relate` returns `None` when an end is an unsettled question, which is
silent: a fact goes nowhere and only a host that happened to use the return value finds out.

**How we would know the first one was wrong.** A host that wants both readings current —
but that is what a type with more than one value is for, and saying `one_per_subject = False`
gets it.

---

## 2026-09-23 · A nature is not a name

**Seen.** Batch three fell to 4/10. "The capital of Germany is Berlin" went in as `PartOf`,
"is a citizen of" and "was performed by" both went into `AssociatedWith` — a type whose own
description was about a football team and a sport. The type had become a dump, the way free
links used to be, and the predicate was gone: `part_of` is not functional, so Paris and Harare
would both stand as parts of France and "what is the capital" could not be asked at all. Across
the slice that is 24 facts and 8 superseding pairs.

**And the diagnosis I reached for was wrong.** Berlin *is* part of Germany — the nature was
right. The only fault was that the link had no name: `capital_of` with `nature="part_of"` is
the correct record, and it keeps both readings. Measured on the benchmark's own pair: Paris,
then Harare supersedes, the record keeps both, and Paris is still part of France.

**Two mechanisms measured and rejected first.** Comparing a link's description with its type's
description does not separate — the two are different genres, a statement against a definition,
and "Thomas Kyd's birthplace" against a correct type scores 0.348 while "Berlin is the capital
of Germany" against `PartOf` scores 0.420. Comparing link descriptions with each other inside
one type does not separate either: the dump averaged 0.308 and a coherent type 0.368. No
threshold divides them, and no more embeddings were tried on it.

**Done — with words, not machinery.** The world's guide and the primer now say it plainly: a
nature says how a link behaves, its name is the fact's own word, and reaching for a type made
earlier because it is roughly the area is the same mistake. One text change, one run:

| | batch three, clean world |
|---|---|
| before | 4/10 — `PartOf` for capitals, `AssociatedWith` for citizenship |
| after | **9/10** — `CapitalOf` (nature part_of, one per object), `CitizenOf`, `PerformedBy` |

**And then supersession worked, for the first time on real material.** Facts 41/44 and 49/50,
two superseding pairs in one batch, recorded by the agent with no help:

    founded in, holds : ['Taipei']                     founded by, holds : ['Philippe']
    founded in, all   : ['Taipei', 'Jerusalem']        founded by, all   : ['Philippe', 'Ben-Gurion']

**How we would know it was wrong.** Types multiplying per phrasing again — the pendulum has
swung both ways in one day, and this is the wording that has to hold both ends: one word, one
type, and a word that is already there is the one to use.

---

## 2026-09-23 · The world noticed every duplicate and told nobody

**Seen.** The whole slice, ten facts at a time into one accumulating world. After 237 entities
there were **23 duplicate names**, and the important ones were duplicated across classes:

    University of California, Berkeley   →  Thing, Place, Organization
    Australia                            →  Place, Place, Place

Fact 115 ("the headquarters of UC Berkeley is in Botevgrad") landed on a different entity from
fact 13, so it superseded nothing. That is the shape of most of the benchmark's superseding
pairs — a hundred facts apart, and each landing wherever the agent's naming happened to fall.

**And the world had already worked it out.** `world._note_named_elsewhere` looks across every
class for the name and was written for exactly this, with a comment about "rugby" ending up
four times over. It emitted a **hint**. Across the run the world held three questions and not
one of them was about identity.

**This is the third time in one day.** The date hint fired in 392 runs and was answered in none;
`world_variables` offered a channel and held 0 rows; and now this. The lesson is not about any
of the three: **what the world says in a hint, it says to nobody.** What holds a task open gets
answered — a recorder settled eight of eight when it could not close without them.

**Done.** A name already in the world under another class raises a question, on the new entity,
naming the other one and what it costs to get it wrong: *"everything said about the other one
will otherwise be about somebody else, and a later telling will supersede nothing."*

**What it is not.** Not a refusal and not a merge. Two things can share a name — a town called
after a sport is not the sport — and which it is depends on what the user said, which the world
does not have.

**Measured before the change,** so there is something to compare against: 150/200 facts joined
by the fourth batch of twenty, $0.19–0.65 a batch, and the world no worse at 200 facts than at
20 — the self-description grows 8% (8.7k tokens to 9.4k), not the explosion I expected.

**How we would know it was wrong.** Tasks held open over names that genuinely belong to two
things — Chanel the person and Chanel the company are both in this slice, and both are right.

---

## 2026-09-23 · The whole slice, measured

455 facts, ten at a time, into one accumulating world, with a recorder agent and no help.

    356/455 facts joined          78%
    1378 turns, $11.44, 107 min

And the slice's actual subject, the 51 pairs where one fact replaces another:

    holds the later telling       33   64%
    holds the earlier              0    0%
    holds neither                 18   35%

**Nothing holds a superseded value.** The correction and handover work; what the world gets
wrong, it gets wrong by not having the fact at all. That is the whole of the 36%: 18 pairs
where the second telling never landed. Of those, exactly one is the duplicate-entity problem
fixed earlier — the theory that explained the day's most visible defect accounts for a
eighteenth of this one.

**Two hypotheses tested and dropped.** The world's self-description was supposed to swell as
the world grew and crowd the agent out: it grows 8% (8.7k tokens to 9.4k) and the late batches
score as well as the early ones. And the lost facts are disproportionately the second of a
pair, whose replacement values the benchmark makes deliberately absurd — "Christianity was
founded in the city of Taipei" — so the recorder might have been refusing what it disbelieved.
Reading everything it said: one "incorrect" in 455 facts, and that about its own slip. It was
not censoring; it was running out of turns.

**Where the facts go.** Batch scores ran 9, 8, 4, 5, 0, 9, 10, 7 … and settled at 7–10. The
bad batches are runs where the agent lost its footing on the API — `world.add`, `world.all()`,
`world.describe_world()` — and spent forty turns recovering. One batch cost 72 turns and
recorded nothing at all; the check that refuses to close a recording that recorded nothing is
what caught it, and its own words in that run were "The world says nothing was actually
recorded."

**What this measures.** Recording only. No questions were asked of the world, so this is the
floor: whatever the answering side can do, it can only do with what is here.

---

## 2026-09-23 · What the agent actually got wrong, counted

**Seen.** 358 errors across 455 facts — almost one per fact, and every bad batch was a run that
lost its footing and spent forty turns recovering. Counted rather than guessed at:

    110×  NameError          87×  ValueError      73×  AttributeError
     56×  TypeError          22×  KeyError         7×  IndexError

**The largest is not a mistake.** The names it tripped on — `shingon`, `alan`, `fact4`, `rel2`
— are its own, and the shape is always the same:

    things["Kūkai"] = Person.new(...)      ← this fails
    shingon = things["Shingon Buddhism"]   ← KeyError: the dict was never filled
    shingon.describe(...)                  ← NameError: never bound

One broken line, three errors, reported as peers — *"the others: KeyError …; NameError …"*. The
agent reads three problems and looks for three causes. Now the world separates them: the ones
that failed on a name the first statement never bound are named as the same failure, not as
others. That is 132 of the 358.

**And two calls that were reached for and refused.** `world.all()` with no class was a TypeError
about a missing argument — which says what the signature wants, not what the caller does; it
now means everything in the world. `world.new("Kūkai")`, a name where a class belongs, came
back as a bare `KeyError: 'Kūkai'` from somewhere inside; it now says what the first argument
is and writes out `Thing.new(name="Kūkai", nature="place")`.

**Not changed:** `world.all("Person")` was the single most common call, thirty-odd times, and
works — it was never a failure, only my reading of the count.

**How we would know it was wrong.** The same count, run again, with NameError still leading —
then the cascade was not the cause and the agent is losing its variables some other way.

---

## 2026-09-23 · Expectations folded from the facts, and what they then measured

**Asked for.** A check per fact of what the world should look like, run automatically — because
what was here asked only whether *some* link joined the two things a fact names, which passes a
world where the director went in as the chairperson and where a later telling sits beside the
one it replaced.

**Built.** `experiments/expected.py` reads each sentence into (subject, predicate, object) —
52 predicates cover 440 of the 455 — and then **folds them in order**: what is owed is the last
telling for each thing and predicate, the ones before it owed as history.

The folding is the part that matters, and it was learned by getting it wrong twice:

- Checking every fact against the final world called the world wrong about fact 1. *"Thomas Kyd
  was born in the city of London"* is superseded by fact 307, *"…the city of Leeds"*, and the
  world holding Leeds is right.
- "the city of London" is not the name of anything; the frame belongs to the predicate. Left
  on, 44% of the slice read as missing from a world that held it.

And one claim had to be narrowed: `Chanel -> FoundedBy -> Coco Chanel` and
`Coco Chanel -> Founded -> Chanel` say the same thing, and only the type's name tells them
apart, so "backwards" is claimed only where the name does not carry the direction. That alone
moved 16 findings out of the wrong column.

**What it then measured,** three worlds, same hundred facts, same expectations:

| | as owed | backwards | no link | missing |
|---|---|---|---|---|
| before the day's last fixes | 45 (52%) | 2 | 24 | 15 |
| mid-fix, with the read-back looping | 47 (54%) | 7 | 23 | 9 |
| **after** | **70 (81%)** | **0** | 12 | 4 |

261 turns and $2.26, against 369 and $3.22 for the middle state.

**The loop that cost the middle state.** The read-back marked only the types it had shown, so a
host that recorded more between close attempts was asked again about the new ones — seven
refusals to close in one batch, fifty-three turns, nothing recorded. It is asked once per task
now.

**Said plainly, because it undercuts most of the day's readings:** one batch of ten facts,
21-30, scored 4, 9, 10, 0 and 3 out of 10 on unchanged code. The agent's variance is wider than
most of the differences I attributed to changes. What makes 52 → 81 believable is its size —
larger than a whole batch — not the fact that it was measured once.

---

## 2026-09-23 · The recorder was reading our notes

**Seen.** A batch of ten facts scored 4, 9, 10, 0, 3 and 0 out of ten on unchanged code, and I
had written the variance down to the agent. Digging into the last 0, its answer to the primer
began:

> "I've read the memory files: the project pivoted to an MCP world server in September 2026,
> recent work measured 78% fact coverage and 64% supersession accuracy, and I know about the
> working principles…"

Those are this session's own notes, written between runs of this very measurement. The host's
working folder sat under `experiments/results/batches/…/host-batch`, inside the repository, and
Claude Code walks up from its working directory, recognises the project and loads its memory.

**So the contaminant was moving.** Runs early in the day saw nothing; runs after each write of
`docs/decisions.md` and the memory files saw more, including the numbers they were producing.
Every comparison made across the day has that in it.

**Done.** The host runs in a temporary folder outside the repository, and its per-folder memory
is dropped after as before. The same batch, same code, uncontaminated: **10/10**, and no mention
of any memory file in the transcript.

**What it costs to believe.** One run. The batch's history is 4, 9, 10, 0, 3, 0, 10 — the last
being the clean one — so this is the best of the seven, and could be luck. What is not luck is
the transcript: the recorder said it had read the project's notes, and now it does not.

**How we would know it was wrong.** The same spread on repeated clean runs — then the variance
is the agent's after all, and the contamination was only noise on top of it.

---

## 2026-09-23 · Stabilising the measurement, and the guide that could not be read by reading it

**The instability was ours.** A batch of ten facts had scored 4, 9, 10, 0, 3 and 0 out of ten
on unchanged code, and it was not the agent: the recorder's working folder sat inside this
repository, so Claude Code recognised the project and loaded its memory — including the numbers
this very measurement had written between runs. Moved outside, and run three times:

    1-10   10  10  10   median 10   spread 0
    11-20   8  10  10   median 10   spread 2
    21-30  10  10  10   median 10   spread 0

The contaminant was the variance. `full_run.py --repeat 3` now runs the whole thing into
separate worlds and prints the spread, because one run cannot tell a change from a bad
afternoon.

**And a check that had been defeated by another.** `finish_task` refuses a recording task that
recorded nothing — but a description counts as something said, and the world now asks for one
on every Thing and every link, so every entity had one and the check always passed. A recorder
created forty-three entities, four relation types, **no links at all**, and closed reporting
"all ten facts are successfully recorded". `descriptions` is a mark now, like a name.

**The guide, audited by running it.** Asked to look for stale instructions, grepping found one
line; running the examples found what grepping could not. `tests/test_the_guide_runs.py` takes
every line the world offers a host — indented in the guides, or quoted in the prose — and runs
it in a world. It caught the primer telling hosts, twice, to call `classes()` for the list of
what this world holds now. No such name was ever bound. The one call that would have shown a
host its own new types raised `NameError`, and it is `world.classes_here()`, which existed on
the runtime and was never put where the host could reach it.

**How we would know it was wrong.** The guide's examples passing while a host still cannot
follow them — the test runs each line alone, and a sequence that only works in order would slip
through.

---

## 2026-09-23 · Reading the facts that did not land, and finding the check had lost them

**Looked at the 68 the check said were missing.** Fourteen were "the author of X is Y", the
largest group by far, and the world had them: `WrittenBy: The Birth of Tragedy → Friedrich
Nietzsche` sat there while the check reported the book missing from the world.

**The check reads `name` and `full_name`.** The recorder had defined `ArtisticWork`, whose
things have a **title** — thirty-six of them — so every fact about an author, a performer or
what somebody is famous for read as a fact the world had lost. It reads whatever each class
declares now, from the class's own spec.

**And two predicates read right from either end.** "The official language of Australia is
Arabic" and "Australia's official language is Arabic" say the same thing; the type is named
`OfficialLanguage`, which does not settle it. Picking a side and calling the other backwards is
the expectation being wrong, not the world. Fifteen expectations are marked as either-way, by
hand, in the files that exist to be corrected.

**What the whole slice actually came to:**

|  | as owed | backwards | no link | missing |
|---|---|---|---|---|
| as first reported | 249 (78%) | 9 | 31 | 27 |
| once the check could read the world | **286 (90%)** | 1 | 25 | 4 |

**And the story about where facts are lost was wrong too.** I had said the losses concentrate
in the few runs where the agent loses its footing. On the corrected reading they are spread:
21 of 46 batches miss one to three, and only one batch (41-50) is a total failure. The
citizenship misses — Henry Ford, Elton John, Bob Iger — are plain omissions, one fact each,
in batches that otherwise went fine.

**Four times in one day my own measurement was the thing that was wrong**, and every time I
looked at the world first. The pattern is always the same shape: the check knows less about the
world than the world does, and reports the difference as the world's fault.

---

## 2026-09-24 · The record did not rebuild the world it recorded

**Asked whether a world saves and restores correctly.** Rebuilt a real 455-fact world from its
statements and counted: **twelve names gone from the world entirely**, though every one of them
had its statements in the record. Berkeley, Paris, Buddhism, Australia, Bucharest, rugby.

**Two rules, both looser in the rebuild than in the running world.**

- `assembly.same_name` compared names across everything. A city called Paris and a person
  called Paris became one, and the city was the one that went. The world had spent the day
  learning to *ask* about a name it already holds under another class; rebuilding it merged on
  exactly that. The class a statement was recorded under is carried by its own id, so it is
  now a distinguishing fact: two things recorded as different kinds are not one thing for
  answering to one name.
- A name inside another name scores exactly `PART_CEILING`, which is what makes "Anna" and
  "Anna Sullivan" one person. Applied to everything it made Berkeley the University of
  California, Berkeley; rugby, rugby union; Australia, the Australian Open; Bucharest,
  Bucharest Municipality. `matching.PART_MATCH_CLASSES` has always said where that holds, and
  the live world has always consulted it. The rebuild did not.

**Now:** 411 of 412 names and all 468 links survive a rebuild. The one that does not is
"Walter Chrysler" merging with "Walter Percy Chrysler Jr." — the person rule doing what it is
for, and what the live world would raise a question about.

**Worth saying plainly.** This is the promise the whole two-layer design rests on — the image
is a reading of the record, and the record is what is true. It had not been checked against a
world anybody had actually built, only against fixtures. `tests/test_rebuild.py` checks it
against a world with the names that broke it.

---

## 2026-09-24 · One of everything, then take the world apart three ways

**The rebuild had been checked on the names that broke it, and on nothing else.** So: fill one
maximally-loaded instance of every structure the world keeps — every value type the ontology can
declare, every entity class, every relation type, descriptions dated and tentative and ending,
tags with periods, questions open and answered, a procedure, pinned names of both lifetimes, a
name choice settled by hand, both self files, a task abandoned part-way — and then do the three
things that can lose it: **rebuild** the images from the statements, **reopen** the database,
**move** the files elsewhere. `tests/test_round_trip.py`.

Four things did not survive, and each was invisible until the whole thing was filled at once.

**The world forgot whose world it was.** `person:user` and `agent:self` are fixed ids because
everything hangs on them. The moment the host records a person under the name the user's own
file gives, the two are one — correctly — and the merge kept whichever id sorted first. An id is
a hex string, so that was a coin toss. Lose it and `world.owner` returns None, the assistant
belongs to nobody, and the person is under an id no lookup reaches. The two parties now lead any
cluster they are joined to (`assembly.clusters`), and `ensure_selves` re-ties them afterwards —
the tie is not a statement, so a rebuild, which knows only statements, cannot put it back.

**Tasks came back as the note that dropped them.** A task is the world's own bookkeeping, and
the world clears every class table before rebuilding. An abandoned task's one statement is the
sentence saying why, so it rebuilt into that sentence and nothing else: no `stated`, no mode, no
work. A class marked `own: true` is now left out of the rebuild on both sides — its table is not
cleared and no image is built for it. Fifty-eight tasks in the frozen world, two of them wrecked.

**A tag read differently after a rebuild than before it.** The record keeps a tag as it was said
and the world keeps one form of it; writing one tidied it and the rebuild put the raw form back,
so `looked-at` became `looked at`.

**The history table grew a past that never happened.** A rebuild sets each attribute to its empty
form and puts the record's value on top, and a relation's class carries its own kind — so the
"previous value" it wrote down was scaffolding. Two rows per rebuild, on the one table whose job
is to say what really stopped being true. `ontology.filling_from_record()` names the difference.

**What the test states rather than checks.** A rebuild reconstructs the class images and nothing
else. Comments, questions, variables, name choices, procedures, meanings, value history, access
counts, self-file digests and the run log are not statements; they survive because the rebuild
does not touch them, not because it can restore them. That is the boundary, and the test asserts
which side each table is on instead of assuming.

**Where it stands:** 471 of 472 names and all 468 links survive a rebuild of the frozen 455-fact
world, the owner with them. The one loss is still Walter Chrysler merging with Walter Percy
Chrysler Jr. — the person rule doing what it is for.

---

## 2026-09-24 · A time belongs to an event, and an event is a class

**Measured first.** A full 455-fact run on the code as it stood: 303 joined, against 371 and 366
for the two runs before it. The whole loss was one category — links that never landed went from
26 and 23 to **82**. Entities arrived as before, direction improved, naming did not move.

**The first diagnosis was wrong and is worth recording as wrong.** The losses looked like they
sat on types that demand a start, and the shape seemed to confirm it: capitals 2 → 22, citizens
4 → 13, chief executives 0 → 5. But `CapitalOf` in that world is `functional: True` and
`CitizenOf` is not `at_any_time` — **neither demands a date**. The demand can account for at most
sixteen of the eighty-two.

**Two real causes, found by reading the record.**

*A link with no ends.* All twenty-two capital facts became **two** `CapitalOf` rows holding a
description ("Berlin is the capital of Germany"), an orphan attribute named after the link's own
kind, and neither a subject nor an object. Nothing refused them. Reading either end raised
`AttributeError: CapitalOf has no 'subject' — did you mean 'subject'?`, which took every other
link of that type down with it, so the check reported them missing and was right. `World.new`
now refuses a relation class without both ends and says to use `a.relate(b, kind)`.

*A raise stops the block.* Host code runs statement by statement, and statements after the one
that raised never run — the world reports `28 after it never ran`. So one un-dated marriage on
line 5 of a 33-line block cost the whole rest of the batch. There were 52 such refusals.

**The rule, after three attempts at it.** Refusing without a way to say "no date" turned away
sixty facts. Taking `now()` silently put a date on a fact nobody dated. Refusing while offering
`now()` turned away the same facts again, because of the paragraph above. What all three missed:
**a link that merely holds has no beginning worth insisting on.** Supersession does not need one
— measured, an undated pair hands over by which was told last. What does have a time is an
*event*, and an event is a class with `start_time` required.

So `starts_required` is gone from `BY_NATURE`, and **`Event` joins `BASE_CLASSES`**. A world is
three kinds of thing — entities, the links between them, and events — and the recorder could
only see two of them: neither built world contains a single Event, because the class was never in
the base world at all.

**And because nothing is demanded on the way in, the world speaks on the way out.** When a
one-at-a-time type has two tellings and neither carries a date, the answer rests on the order
they arrived. That is right more often than not and is not the same as having been told, so
`_only_what_still_holds` now says which telling it took and what that rests on. Uncertainty is
an outcome, not a refusal — and this is the read where the host can still go back and ask.

**`long_ago()`** joins `now()` as something a host can say: `timeutil.NEVER`, the honest answer
for a standing fact nobody dated — already so before this world began.

**Where it stands.** Answering the same hundred questions of the two worlds: 77/100 for the world
this run built, 81/100 for the frozen one. Published numbers on the task: Zep 7%, Mem0 18%,
BM25 48%, HippoRAG-v2 54%, and a deterministic `max(serial)` recipe at 78% / 94.8%. At n=100 our
interval is 68–84%, so clear of every memory system and both retrieval baselines — the first time
that gap is wider than the interval — and not separable from `max(serial)` on gpt-4o-mini.

---

## 2026-09-24 · A sentence that names something else is a link

**Where twenty-two capitals went.** Two became `CapitalOf` rows with a label, a description and
neither end — `retype` carries the attributes both specs declare, and a link's ends are declared
by neither, so a free link taken into a type lost them. The record held both ends throughout and
a rebuild put them back (Berlin → Germany, Chang'an → Tang Empire), so nothing was lost; it was
unreadable, and reading one raised and took every other link of that type with it. Fixed, with a
test that fails without the fix. `take_in` also now answers to the word a type was defined with,
not only to the class it became — the host wrote `take_in("capital_of")` and was told there was
no such type.

**The other twenty went into prose, and that is the finding.** `capital_of` did not exist when
the run began: the recorder builds its own vocabulary as it meets the words, which is the design
working. It defined the type at turn 599 of 1143. Fourteen of the lost capitals arrived before
that. With no type to put them in, the host wrote the fact as a description — Tokyo holds "the
capital of Japan" and "the capital city of Japan" and no link at all.

**And every check we had passed it.** The thing is described, so `_undescribed` is satisfied;
something was said, so the emptiness check is satisfied; the task closes and reports success.
Our own rule — describe everything, or the task will not close — is what makes prose a legitimate
place for a fact to land. A description written to let the world check its own structure became
the way around it.

**So the world now reads what a description says about.** `_facts_hiding_in_prose`: a description
this task wrote that names another entity the world holds, with no link between them in either
direction, stops the close. The test is narrow on purpose — "the city Thomas Kyd was born in"
names Thomas Kyd and there *is* a link, so it is what it looks like, an account of why the thing
is here. The same sentence with no link is a fact nobody recorded. Caught at `finish_task`, not
at `describe`, for the reason everything else moved there: a raise stops the block.

**What it does not do**, and is in docs/TODO.md: go back over prose already written when the type
for it finally arrives. `take_in` offers free links to a new type and nothing offers descriptions.
`world.wanted()` counts untyped words across links only — counting them across descriptions would
have named `capital_of` around fact 30 rather than fact 225.

---

## 2026-09-24 · A refusal that sends you to prose, and advice you cannot follow

**Two messages, found by asking what `AttributeError: CapitalOf has no 'subject'` was for.**

*The first was wrong about what happened.* `__getattr__` fires both when a class has no such
attribute and when this one instance has no value for one it does declare, and both raised the
same sentence — so a link whose ends were missing from its image was reported as
`CapitalOf has no 'subject' — did you mean 'subject'? It has: subject, object`, which says it
has it and has not got it in one breath. A host read that eighteen times in one session and
stopped using the class. The two cases now say different things, and the second says where the
value has gone: the class declares it, this one lacks it, `world.rebuild()` reads the image
again from what was said.

*The second pointed the wrong way.* Writing an attribute the class has not got is refused — it
used to be accepted and lost on save, a write that looked fine and never happened — and the
refusal offered one way out: `entity.describe(...)`. That is prose, and the same day's work
established that prose is where a fact goes to stop being one. In an open ontology the answer is
to give the class the attribute: the message now leads with `world.attribute(Cls, name, "…")`
and says what a description is actually for.

**And then the advice turned out not to work.** `world.attribute` rebuilt the class, and a
rebuilt class is a *new* class object — so the instance already in hand, and the name bound in
the run's namespace, still carried the old spec. A host that did exactly what it was told got
the same refusal a second time, with nothing available from inside the run to get past it. That
is a refusal that repeats itself, and the way out of one of those is prose.

So a class that grows is now the **same class**: `define_class` updates the standing one in
place when the base is unchanged, instead of building a replacement. What was made before the
growth keeps working, `isinstance` keeps meaning what it says, and the sentence the world prints
can be typed straight back in. Tested as the three steps a host takes: refused, told, works.

**A class lives in two places, and growth reached only one.** The class object carries `_spec`
and the generated properties, and that is what `__setattr__`, `__getattr__` and saving consult.
`world.specs` is a separate dictionary the world opened with, and two readers prefer it: `find`
and `get` check an attribute name against it, and the assembler asks it whether a slot holds one
value or many. Growth updated the class and the file on disk and not that dictionary — so an
attribute a host had just declared was writable and **not findable** in the same run
(`Person.find(salary=...)` → "no attribute 'salary'" while `person.salary` held 140000), and a
grown `list[...]` slot was read back on a rebuild as a single value, the last one said. That
second one is the same fault that made a test of mine earlier today report every list attribute
on a grown class as a scalar. `Authoring._register` now puts the spec in both.

---

## 2026-09-24 · What a class can become while the world is running

Settled with the user: **intercept the call and say so** — no removing, no renaming, no
redeclaring. What growth does is add.

    add an attribute      yes — writable, readable, searchable, saved to grown/*.json
    add a class           yes
    add a relation type   yes
    declare it again      refused
    change its type       refused (the same thing as declaring it again)
    remove, rename        no such call, and none wanted

The reason is not caution about schemas: everything already recorded under a word was recorded
*meaning* it. A word whose meaning can be changed afterwards makes every statement written
before the change unreadable in the way it was written, and no later telling repairs that —
the record cannot say which meaning was in force. Adding a second word costs a word; changing
one costs the record.

So the refusal now says what the word already means — its type and its description — because a
host that wanted something else needs exactly that in order to write the value in the form the
world has or to pick a name of its own. "Person.salary is already declared" on its own is a
door with nothing behind it.

---

## 2026-09-24 · Take everything the situation offers, then ask for what is missing

The user, after the third time this shape turned out to be the answer, stated it as a rule:
**take all of it rather than refusing, and ask for the rest.** It is now how the world behaves
in three places, and each one was a refusal first and cost something measurable.

    a link with no date        refused  →  sixty facts turned away, then the same again
    a fact written as prose    accepted →  the close asks for the link
    a word nobody declared     refused  →  the close asks what it means

**Why a refusal costs more than it looks.** Host code runs statement by statement and a raise
stops the block: everything after it never runs, and the world says so — `28 after it never ran`.
One un-dated marriage on line five of a thirty-three-line block cost the rest of the batch. And
a host that keeps hitting a wall does not keep trying; it writes prose, which passes every check
and puts the fact where nothing can supersede, count or find it. A refusal does not hold the line
on structure, it moves the failure somewhere the world cannot see.

**Why asking later works.** The close is the one moment the world knows the host is free and the
user is still there. Everything hard to answer mid-block is easy there: what a word means, which
of two tellings came first, what this thing is. `finish_task` already refused to close over
undecided questions, undescribed things and links against their type; dates, prose and undeclared
words join a list, not invent a mechanism.

**What the world must never do instead** is fill the gap itself. It took `now()` for a missing
date once and that is the version this one replaced: a date nobody could question, indistinguishable
in the record from one somebody knew. Taking the *value* is not the same as taking the *meaning*.
An attribute taken on the fly gets its type guessed and is marked `provisional`; what it means and
whether it supersedes stay empty until somebody says, because no value can tell you either.
