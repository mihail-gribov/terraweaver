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

---

## 2026-09-24 · Two ways of asking, and a link is read once

The user's rule, and it decides the shape of everything below: **there are two ways to get
intelligence, open questions and closed ones, and two tools for them.** A closed question — one
of these options — is an order of magnitude cheaper, so anything that can be reduced to options
is reduced and goes to Jev; what is left, where a word has to be invented, goes to Nemotron.
Decompose hard, make it concrete, and ask for a reading of the world rather than a piece of
reasoning.

**The link inspector** (`terraweaver/inspector.py`) is that split made into a thing. A link is
handed to a reader with everything the world holds about it — the type's word and description,
what each end is, both ends by name and class and whatever was said about them, and the link's
own description. It is read **once**: the mark is over the link's own content, so a link whose
end has moved is read again and one nobody has touched is not.

Three questions, and only the first is the world's business:

- **Which way it runs.** Not whether it is true. This record deliberately holds claims that
  contradict common knowledge and they are what it exists to keep — "Rome capital of Japan" is
  well formed and false, "Japan capital of Rome" is malformed. The user's distinction: semantic
  correctness is *can this be so*, substantive correctness is *is it so*, and the world acts on
  the first only. A fact may be refuted later; a capital really does get moved.
- **Whether the type is the right word**, and whether the world already holds one meaning the
  same (`twins`, by meaning over name and description).
- **Whether the word says plainly what it is** (`naming`), with a clearer one offered. Nothing
  is renamed: the honest rename is a new type and `take_in`, which moves the links across and
  leaves the record saying what it always said.

**Measured, and the measurement is the point.** Asked four ways over the links of a hundred-fact
world:

    a plain English sentence         5/5 on a picked set — but rejects the deliberate falsehoods
    "can this be so at all"          9/12 — keeps them, misses reversals
    "which of A or B"                7/12 — and inverts correct links at p=0.93
    the ends named, four yes/nos     12/14 — and every miss an abstention

The last is the one, and what makes it work is the thing none of the twenty-six grown types had:
**names for its two ends**. With `roles` empty the inspector found nothing at all in 115 links.
With the ends named by Nemotron (26 calls) and the links judged by Jev (115), it found 13
written backwards, including all three the checker knew about, and left 90 alone. Two tools,
twenty times fewer open questions than closed ones.

**So the recorder is asked for them** — asked, not made to. `define_relation` without
`subject_is` says what cannot be checked without them and hands back the call to write; the
close adds one line listing the types still unnamed and closes anyway. A type without named ends
works perfectly well. It is only the checking that cannot be done, and that is worth a line
rather than a wall.

**Still wrong, and worth naming:** a role written too narrowly turns into a false alarm.
Nemotron called `affiliated_with` an organisation-to-organisation link, so
"Princess Alice affiliated with Anglicanism" came back impossible. The link is fine; the role
is too tight. The verdict is kept as a question on the link and never applied, which is the
reason that costs a question rather than a fact.

---

## 2026-09-24 · The inspector's checklist, and what it is never allowed to check

Settled with the user over the course of building it. The inspector now carries its checklist
in one place (`inspector.CHECKLIST`), so what it looks at is read rather than reconstructed, and
each entry says the thing that decides its cost and its authority:

    on     how             what
    type   deterministic   twin_type             two types read as one idea
    type   deterministic   ends_named            the type never said what its two ends are
    type   open            ends_could_be         what each end is, in checkable words
    type   open            name_says_direction   the word does not say which end starts
    link   deterministic   against_the_run       this link runs against the rest of its type
    link   closed          ends_fit_their_roles  is each end the kind of thing that belongs

**Deterministic** is worked out from the world's own record: free, certain, and the only kind
that may ever correct anything by itself. **Closed** is one question with named options to an
outside reader — cheap, calibrated, and where the volume is, one per link. **Open** is where a
word has to be invented: expensive, so once per type and never per link. On a hundred-fact
world that came to 26 open questions against 115 closed ones.

**And one thing it is never allowed to check:** whether the fact is true. The world holds what
the person said; a benchmark of it holds deliberate absurdities on purpose; a capital really
does get moved. Read from outside, the truth of a fact is kept as a remark and is never grounds
for anything. The user's line: semantic correctness — *can this be so* — is the world's
business, substantive correctness is not.

**Timing decides where each check runs.** A host's run is stopped after ten seconds. Measured,
a naming answer comes back in four or five seconds and one in several takes twenty — so nothing
that waits on a reader may be called from inside a run, or the run dies of the check. What the
world can do for free it does at the moment the type is defined, while the host is still holding
the pen and the correction is one more argument on the call being made; the reader runs at the
close, where nothing is waiting, with `TTL = 10` seconds and whatever it does not answer marked
unread for a later pass.

**`can_ask=False`** is for a pass with nobody there — a sweep over an old world, a nightly run.
The finding is written down either way, so the same link is not read twice; it simply is not put
to an agent that is not listening. A question nobody is there for is not caution, it is a queue.

---

## 2026-09-24 · Take it all without loss, then lower the entropy

The user's summary of the whole shape, and the one line the rest follows from:

> **Record everything that can be taken without loss. Then lower the entropy — build the
> structure. And if there is time, ask the host, while the window of interactivity is open.**

Three stages, and each has a cost and a deadline of its own:

**Take it.** `world.say(a, b, "Paris is the capital of France")` — two things and the fact in
words. The link is made at that moment, untyped, carrying the host's own words. Nothing waits in
a side table: a sentence kept until somebody can type it is a fact nothing can find, and if the
reader never runs it is a fact nobody recorded. An untyped link is a poor link — it cannot
supersede, cannot be asked about by type — and it is a link.

**Lower the entropy.** At the close of the task, where no run is waiting on a ten-second limit,
the untyped links are read: what relation, which end holds which role, how many at a moment,
when it began. The typed link is written and the bare one is ended where it begins — not erased,
because what was said is never unsaid.

**Ask, if there is time.** The close is the one moment the world knows the host is free and the
user is still there. What could not be read, what was read thinly, what turned out to be two
words for one idea — all of it is put then, and closes the task or does not.

**The reader's task is concrete, and that is what made it work.** Not "describe this relation"
but: here are two things and their classes, here is what was said, here are the relations the
record already holds, and here are seven numbered things to return. Measured on four sentences:

    Paris is the capital of France    capital ↔ country, subject Paris, one/one
    London is the capital of France   the same, subject London        <- false, placed identically
    Anna has worked at Brightwork     person ↔ organisation, "since 2019", one employer at a time
    They are brothers                 brother ↔ brother, many/many    <- symmetry, undeclared

The second is the test that matters: a falsehood is placed exactly as the truth would be. A
record that took only what it agreed with would be an encyclopaedia.

**And in the battle run the host did not use the new door at all.** Ten facts, 10/10 — the best
batch this project has recorded — and every one of them through `define_relation` and `relate`.
`world.say` appears four times in the dialogue, all four in the primer it was given. Offered two
doors, a host takes the one it already knows. Whether the sentence door is better is therefore
not yet measured, and saying so is the point: the mechanism works, and its worth is unmeasured.

---

## 2026-09-24 · The host tells a story; the world is the knowledge engineer

The user's framing, and the best one this project has had for what the two sides are:

> **The host is like a person telling a story. The world is a knowledge engineer who takes the
> story apart and turns it into a formal representation. So it is odd to ask a person about the
> transitivity and cardinality of a relation.**

That is exactly what the primer had been doing. `define_relation` asks a storyteller for
`nature`, `cardinality` and `over_time` — three questions about the shape of a relation, asked
before the second fact of its kind has been heard, and every one of them was answered badly in
a measured run: two ideas under `Speaks`, three links written backwards, `over_time` guessed.
None of that was carelessness. It was a storyteller doing an engineer's work.

So: `world.link(a, b, "Anna has been an employee of Acme since 2019")`. Two things and the fact
in words. The engineering — roles, how many at a moment, what follows, when it began — is read
afterwards, by a reader whose whole task that is, at the close where nothing waits on it.

**The primer halves.** 1651 words to 824, and what went is not reworded, it is gone: natures,
cardinality as a question, `over_time`, "a nature is not a name", "do not reach for a type that
is roughly the area". What stays is what a storyteller needs, including what a link *becomes*,
because the host has to read its own facts back:

    paris.capital_of  -> France          each end reads by its own role
    anna.mother_of    -> [Boris, Vera]   several at once, so a list

**The experiment did not run, and reporting it as 8/10 would be wrong.** Hiding
`define_relation` is not hiding the type-first door: `relate` is a method on every entity, so
the host wrote `relate(a, b, "related", label="born_in")` — labelled free links, untyped —
three `world.link` calls against five of those. Worse, nothing got typed at all: typing happens
at `finish_task`, and two of the three tasks it opened were left with `runs=0 closed=null`. The
`Related[born_in]` in every row is a bare link that was never read.

What that measures is a mixture, not a mechanism. To try the claim, the surface has to have one
way to write a link, and the task has to close.

## 2026-09-25 — identity is settled once, at the start, and never in the middle of a write

**What broke.** `Thing.ensure(name="France")` came back a question: "did you mean Acme?"
`SequenceMatcher` counts matching characters wherever they fall, so "france" and "acme" score
0.6 on the `a`, `c`, `e` they happen to share in that order — exactly the threshold where the
world asks. The run stopped on its fourteenth line. Two spellings of one name share a run of
characters, not scattered ones ("anna"/"anne" share "ann"), so a match that never runs longer
than a couple of characters is now worth nothing.

**The deeper thing that fix exposed.** Matching *during a write* is the wrong shape whatever
its threshold. It asks the same doubt again on every mention and settles none of them; it stops
a block half-written; and it asks at the one moment the host has least to answer with.

So a task has two halves, and they want opposite things:

    who = world.identify(Person, full_name="Anna Weber")      # settle who — a search, you pick
    anna.relate(acme, "Anna has worked at Acme since 2019")   # record — no questions, no matching

`world.identify` hands back who could be meant, best first, and never chooses between them. The
host has the conversation and the world does not, so the choice was never the world's to make —
and a question machine here would be a machine for asking about what the host could already see.
Two or five are read by eye; twenty means say more and look again.

A name nobody here has is recorded, and the list comes back holding it. There is no second
branch for a host to take — the user has just spoken about a city, and a city the world has
never heard of is a city to record, not a refusal — so making the host say it in a second call
is ceremony. The one thing that is not that is a search the host narrowed itself: if the name
found people and the extra attributes ruled all of them out, nothing is made and the list is
empty, because the host was choosing among the ones already here.

`new` and `ensure` still recognise a strong key — the same email is the same person and costs
nothing to see — and otherwise record what they are given. Two records that turn out to be one
thing are merged over the record, with the whole world in view.

This is the same division as the sentence door: take what the host can say now, do the
engineering later where nothing is waiting.

**`basis` is gone from the relation path.** `world.relate(a, b, kind, basis=[statements])` made
a link the world's own conclusion. It did not fit: the world does not conclude links — a link is
what somebody said. With it went `_supersede_own_conclusions` (a later conclusion closing an
earlier one of its own kind), which nothing could reach any more. The conclusion machinery in
`facts.py` stays and is still used for attributes; `relations.retract` keeps its refusal, which
now always fires, and that is the honest answer: what was said stays.

## 2026-09-25 — a thing that came in as a bare name is described in words, and read at the close

The twin of the sentence door, for one thing instead of two, built on the same division.

`world.identify(Thing, name="Rome")` finds nobody of that name and records Rome. What comes back
is a `Thing` with a name and nothing else — no class worth the word, no nature, nothing to find
it by later. The host knows what Rome is; it has just heard about it from the user. Choosing a
class for it is a different job, and one a reader with nothing else to attend to does better.

So the run's reply carries a line of code to run next:

    [to fill in] the block ran. Run these next, with real words in place of the dots:
        rome.describe("...")   # rome is only a name so far — what sort of thing, where, whose

**The variable, not the name.** The question is put together after the script has run, where the
world can see what the host bound the thing to, so it asks about `rome` and not about "Rome".
A host told to describe "the thing" describes the wrong one often enough that this is the whole
reason the asking happens there and not at the close.

**A clarifying question, not a failure.** The block ran; nothing is wrong. It is kept apart from
`[open questions]` (doubts about what is in the world) and from an error (the block stopped).

**It closes itself.** `describe` is the answer — there is no `q.answer(...)` to make. The
question's reason is that nothing is known about the thing, so the moment there are words on it
the reason is gone and it closes, the way a doubt about two current relations closes when one of
them ends.

**Then the close reads it**, with the entity handed over and never read out of the words: the
reader says what this is, never which this is. Measured on four bare names —

    Rome       -> Place  {capital_of: Italy, population: 2800000}
    Berlin     -> Place  {capital_of: Germany}
    Kreuzberg  -> Place
    pesapallo  -> Sport  {origin_country: Finland, invention_period: 1920s}

— two classes crystallised out of what was said, and the attributes came with them.

**`Thing` is not offered as an answer.** It is described as "anything the world has no better
class for", which describes everything, so a reader asked to pick a class picks it every time and
nothing is ever defined. It is the absence of a class, so it is not among the classes to choose
from; a reader that finds none of them fitting defines one.

**Nothing refuses the reading.** The first prompt had an `ill_typed: "relation"` escape for an
account that turns out to be about two things — and "Rome is the capital of Italy" went straight
into it, because an account of a thing names other things. That is how these words say Rome is a
city. The mirror was drawn wrong: in the sentence door `ill_typed` stops a *link* being made from
words about one thing; here there is nothing to stop, because `describe` is about this thing by
construction.

## 2026-09-25 — the asking line belongs to the class, and finding a class is a walk down the tree

**"Describe it" means different things.** A person is described so they can be recognised when
the name is said differently next time; an event so it can be placed in time; a link so it can
be read as the fact it is. Asked all the same thing they all give the same answer, which is the
encyclopaedia entry nobody wanted. So the line lives in the class:

    Person   their full name as the user says it, who they are to the user, where they live…
    Event    when it is or was, where, who was in it, and what it was for
    Related  what this link is, in the words the user used — what one of them is to the other

Written for all 23 classes the record has.

**And it is inherited.** There was no class inheritance in this world — `base = Entity`, always.
Now there is a declared parent, and two roots: a thing **is**, an event **happens**. Person and
AIAgent are kinds of Thing; so are Place, Organization, Project, Vacancy, Idea. Task is a kind
of Event. A relation type with nothing of its own falls to the base relation whose nature it
carries. `ontology.what_to_say` walks that chain.

**Finding a class is a walk, and most of it is closed questions.** One procedure for everything,
starting from the class the thing already sits under (or a root):

    Thing → [AIAgent, Person, …, "none of these: it needs a class of its own"]
      ↓ Place
    Place → [City, District, …, "none of these"]
      ↓ none of these
    a class is invented under Place

Every level is a list of named options — a closed question, answered by a model built for those
and an order of magnitude cheaper than one answering in words (`docs/decisions.md`, open and
closed questions). Only the last step is open, and only when nothing fitted. `outside.AsChoices`
puts a closed question to an open reader for a world with no such model configured; Jev drops
into the same place.

The new class is defined **under the parent the walk stopped at**, which is the whole of what
makes it reachable: a class with no parent is a leaf nobody ever descends to. This is how the
world's own description grows.

**Three things the reader is not asked.** What identifies one of these — it went wrong the one
time it was asked, a `City` identified by `population` with "Rome" written into it; these things
arrive under a name and are known by it. Whether what was said is true. And what to ask about
one of these: a new class inherits its parent's line, because a line invented from the single
example that caused the class is a line about that example.

**Writing those lines is offline work** (`inspector.write_the_questions`). A class is born in the
middle of reading one thing, and one thing is an example; what a kind is shows in several of
them. So the world waits until there are three and writes the line from all of them at once,
and until then the class honestly says what its parent says.

**The world description shows two levels**, roots and their children, with a third folded into
its parent's line. A flat list does not say that a Person is a Thing, so a host looking for
somewhere to put a city reads past Place and reaches for Thing.

### The same day, what the live runs corrected

**The walk never moved, and two runs reported that as behaviour.** The option standing for "none
of these" was named `— none of these: it needs a class of its own`, and a reader asked to echo a
name echoes it nearly — different case, a trailing stop, the name inside a sentence. Insisting on
the character-for-character match threw away every answer: `choose` came back empty, the walk
returned where it started, and four things in a row were reported as staying `Thing`. Option
names are now short and plain, and `outside._one_of` matches on the letters.

**One attribute cost a whole class.** `define` wants a sentence per attribute and a reader writes
labels — "Land area" — so `City` was refused over `area_sqkm`, the thing stayed a bare `Thing`,
and every later city had nowhere to go. An attribute nobody described is now simply not taken;
it can be declared later, when something is written into it. The class is what is being made.

**What identifies one of these is not the reader's to choose.** Asked, it answered `population`
for a `City` and wrote "Rome" into it. These things arrive under a name and are known by it, so
the class gets `name` and the reader is told not to put the thing's name anywhere else.

**A class is not named after its parent.** "A kind of Thing" called `Thing` is the walk handing
back where it began, dressed as a new class.

**Still wrong, and worth stating:** "Kreuzberg is a district of Berlin" was placed under `City`.
The walk prefers an existing class to a new one and there is no threshold saying when it should
not — with no `Place` in that world, `City` was born directly under `Thing` and `District` had
nowhere to be except beside it.

### A class is described in prose, by somebody, more than once

`brief` is the one canonical line — how the class appears in the list every host reads. The
account in sentences is a prose-fact among however many accumulate:

    [{"text": "A populated place with a permanent community and defined boundaries.",
      "source": "world"},
     {"text": "Cities here are mostly ones the user has lived in or visited.",
      "source": "world"}]

One canonical sentence per class was a shape used nowhere else in this world, and it lost what it
replaced: the first account is written when one of a kind has been seen, the next when there are
twenty, and neither overrules the other. `source` is the word every statement here already
carries (`ontology.stating`) — "agent", "world", "given" — rather than a second word for it.

## 2026-09-25 — the reading returns a class and the code to fill the thing in

The portrait reader used to return a shape — values here, links there — and something in this
file had to interpret it. Two things were wrong with that. A hand-written translator can express
only what its author thought of, so everything else the reading found was quietly dropped; and
it was a second door into the world, with its own idea of what is allowed.

So the reader returns what a host returns: **a class description, and the code that fills this
one in.**

    {"class": {"name": "City", "brief": "…", "attributes": […]},
     "code": "it.population = 2800000\n"
             "italy = world.identify(Thing, name=\"Italy\")[0]\n"
             "it.relate(italy, \"capital_of\")"}

`it` is bound before the code runs. Identity is handed over here as everywhere else in this
world and never recovered from words — the reader says what this is, never which this is.

**The code runs by the door a host's code runs through** (`runtime._the_world_writes` →
`run`): the same sandbox, the same statement-at-a-time commits, the same refusals. Its writes
are the world's own (`stating("world")`), which is the lowest standing there is.

**And the loop is the same loop**, with Nemotron where the agent usually stands. The code fails,
the world hands back exactly what it would hand a host — where it stopped, what is done, what
was rolled back — and asks for the continuation. Three goes, the same bound a host has.

Measured on three prose-facts: 3 read, 3 placed, 2 classes defined, 3 ran, 0 gave up.

**What the loop got wrong, and the prompt now forbids.** `it.capital_of(italy)` failed — there
was no such relation type — and the reader recovered by declaring an attribute:
`world.attribute(City, 'capital_of', …)` then `it.capital_of = italy`. A link became a slot with
a thing in it: nothing can ask it by type, nothing can supersede it, and everything that reads
links is blind to it. The prompt had shown the typed short form as if it were the ordinary way
to write a link. It says now that `relate` is always how a link is written, that the short form
exists only for words the record already has, and that a link is never an attribute.

**A class grown under Person is identified like a Person.** `_make_one` hardcoded
`identified_by="name"`, so a `Colleague` was known by a `name` nobody writes: "Anna" and "Anna
Weber" two people, one email two accounts. Identity is declared per class here and nothing looks
across classes, so a child now starts from what its parent declares — the name key, and those
strong keys and distinguishing attributes it actually has.

**The reader is shown the classes that exist.** Given an example naming `Place` in a world whose
classes were Thing, Person, Event and AIAgent, it copied the example: `world.identify(Place, …)`
three times, three NameErrors, nothing written.

**A thing the world named while reading is asked about too.** "Rome is the capital of Italy"
makes an Italy, and the question belongs to the agent — it is the one who brought Italy up. It
has no variable for it, so the line looks the thing up by name:
`world.identify(Thing, name="Italy")[0].describe("...")`, which anybody can run.

### What five minutes of Nemotron caught and the suite did not

Six corrections in one branch, and all six the same mistake: **the code said something other
than what was so.**

To the reader — an example naming a class this world has not got (`world.identify(Place, …)`,
three NameErrors, nothing written); the typed short form `it.capital_of(other)` shown as the
ordinary way to write a link, when it only works for words the record already has, so the reader
recovered by making the link an attribute; a promise that `relate` would make a missing type,
when `initiative.MAKES_TYPES` is off by design; and no word about a record refusing any
description shorter than a few words, which it does for attributes and relation types alike.

To itself — `_ask_about_bare_things` kept asking `portraits.unread` for things with nothing said
about them, after that table was changed to hold prose-facts, which are the opposite: accounts
somebody has already given. So the one case the branch exists for — a thing the world named
itself, Italy out of "Rome is the capital of Italy" — was never asked about. And the clarifying
line was only printed when `raise_` returned a new question, so a doubt raised inside the world's
own reading was never mentioned to the agent again.

None of the six was a logic error a test would catch by running the same path twice. Each needed
a second party — a model reading what we wrote and doing something else — and each took a
five-minute live run to find. That is the argument for a fake reader in the suite: the same
circuit, answers fixed in advance, seconds instead of minutes.

### The party that formalises is the engineer, and the circuit has a test

**`world.reader` is `world.engineer`.** "Reader" said nothing about the work and the word was
already doing two jobs in one file. The name is the project's own: the host tells the story, the
world does the engineering. It says the role rather than the model, so Nemotron is replaceable in
it without a line changing. The closed one is `world.jev` — named options, the walk down the
tree. That name is a role here too: a Jev is a system-one model answering a question with named
options, and which weights are behind it (`outside.Jev`, `outside.TypecastLM`, `AsChoices` over
an open reader when there are none) is a deployment question and not the world's.

**Neither is required, and that is what lets the circuit be tested.** The world constructs no
model: `server.py` puts them on at startup and everything takes them as arguments, so a world
with none simply does not run these passes. `tests/test_portraits.py` passes two plain objects
with the same two methods and answers fixed in advance — and keeps what it was asked, which is
the other half. Three of the six defects of that day were the world *asking* the wrong thing,
and there is no other way to see that than to read the question back.

**`tests/test_portraits.py` stands both of them in.** Answers fixed in advance, the whole circuit
in seconds: a bare name noted and asked about, the question closing itself when something is
said, the walk, the class made under the parent it was found from, the code run, a refusal handed
back and the next answer run, a reading written against the prose-fact rather than the thing.

It earned itself twice on the day it was written, on two things no live run had shown:

**The world was reading its own writing.** The engineer's code calls `it.describe(...)` for what
no attribute can hold. That lands as a prose-fact like any other and joins the queue to be read —
the world taking apart a sentence it composed itself, and setting the circuit off again each
time. Only what came from outside is an account of anything now.

**A retype was undone by the next line the agent wrote.** `retype` builds the thing afresh under
its new class, and every variable still pointing at the old one points at something the record no
longer agrees with. The host's next save wrote that back: Turin, read into `City` at the close,
was a `Thing` again after one unrelated assignment, with nothing anywhere to say so. What changed
class is now handed back to whoever is holding it.

Neither is a logic error a test would find by walking the same path twice, and neither shows in a
live run — the second one looks like the reading simply not having worked.

## 2026-09-25 — one word, two members: an end reads, a call states

A relation end is now on the class twice, and they are deliberately not the same name:

    rome.set_capital_of(italy)      states the link, one at a time
    rome.capital_of      -> Italy   reads it back: a value where only one can hold
    anna.mother_of       -> [Boris, Vera]   a list where more can
    italy.capital_of_of  -> [Rome]  the other end reads by its own word

**Assignment was tried and refused.** `=` claims replacement, and writing a link is addition
wherever the type allows several: `anna.mother_of = vera` reads as though Boris were gone. The
one place `=` would be honest is a single end, and there it gains nothing over saying it. What a
second statement does — corrects the first, ends it, or stands beside it — is the type's rule,
not the syntax's, which is the other reason nothing about it belongs in an assignment.

**`relate` keeps the words.** Two ways to state a link and both are calls: the word when the
record has one, the fact in words when it does not, read at the close.

### The controlled six, both doors

`experiments/story/` holds the benchmark's own facts with the code an ideal host writes and what
each must change. `new_doors.py` says the same six through the door that takes words and checks
them against the same table. Four things had to be fixed before either number meant anything:

- the table's code was a two-word kind (`"born in"`), which is now a *sentence*, so every fact
  went in as prose and the old door measured nothing;
- it relied on unknown words making their own type, which `initiative.MAKES_TYPES` turns off;
- the check compared the class name (`BornIn`) to the type's word (`born_in`);
- and it read `valid_until`, which is only half of superseding. A type that holds one at a time
  hands over and the old link is given an end; a type that holds one value is *corrected* and the
  row keeps standing, because what was said was said. So the measure is what the world **reads
  back** — the question anybody asking this world would ask.

With that, the type-first door is **6/6**. The door that takes words went 0 → 2 → 3 → 4 over three
fixes, each a defect the run exposed:

**The reading came after the close's checks.** A task that said six facts in words could not
close, because the things it named had nothing said about them — and so was never read, and so
never closed. Readings are marked, so doing them first costs nothing on a second attempt.

**The type's word was derived, not asked for.** `_one_word(subject_is) + "_of"` gives `capital_of`
for a capital and `person_of` for "Thomas Kyd was born in London", because a person is what the
subject is. A type nobody would write is a type nobody looks under.

**The type was matched by its pair of role nouns.** Being born somewhere and dying somewhere are
both person → city; chairing something and playing a position are both person → thing. Three of
six facts came out under a word that meant something else — and a fact under the wrong word cannot
be told from a right one afterwards, because both read the same. The word identifies a type; the
roles describe it.

One of six still misses: a reading that came back empty, so the link was never made and the one
it should have superseded still stands.

### The controlled six: level on the facts, one word apart

    type-first door (the host writes the word)   6/6 facts   6/6 words
    said in words (the world reads it)           6/6 facts   4/6 words

**Two numbers, because they are two questions.** The fact is whether these two things are joined
and whether a later telling put the earlier one out — what anybody asking this world gets back,
and it does not depend on the spelling of the type. The word is whether the world called it what
the table's host called it. A world that grows its own vocabulary will differ there by design:
`plays_position_of` beside the table's `plays_position` is another name for the right fact, not
a wrong one, and the engineer gave it twice the same way, from the examples it is shown —
`capital_of`, `mother_of`, `part_of` all carry that tail. So the measure was changed, not the
engineer.

Both supersessions fire through the new door: the correction (born in London, then Leeds) and
the handover (plays wide receiver, then cornerback).

**The last fix was the `kind` escape.** "Hines Ward plays the position of wide receiver" was
called a statement about a class rather than a link, so no link was made and the next statement
had nothing to join or supersede. The escape had been written around the word "of" — and `part_of`,
`capital_of` and `mother_of` all have it. Both ends are handed over as things, so the test is
checkable: "kind" is right only when the second of them is one of the record's classes. "wide
receiver" is a thing.

**What this does not say.** Six facts, one run, and the spread is real — three different outcomes
were seen on the same input across the day. And each fact here has a task to itself, so the
engineer reads one sentence at a time; in the full slice it is ten facts to a task, where the
list of words already held is longer and so is the chance of collapsing two ideas into one.

## 2026-09-25 — a live host, and what a run measures when a door is switched off

Ten benchmark facts, one to a task, through a live host (haiku over MCP) — the first time an
agent rather than a hand-written script has used these doors. It came back 9 of 10, and the
number was worthless: **the world had no engineer.** The server only sets one when
`NEBIUS_API_KEY` is in its environment, says nothing when it is not, and simply does not read.
Every sentence in that world came back unread, and what the run measured was the door that was
still switched on. `start_base_server` now carries the key in, and says so loudly when it cannot.

**What the host actually wrote is the finding worth keeping.** Five of its six sentences were
not facts but the names of relations:

    tony.relate(bbc, "director of")          chairperson of / married to / plays the position

Those name neither of the two things, so there is nothing in them to read. The primer says to
say the fact; the host still thinks in the word for the link. Its `Thing.identify(full_name=...)`
is the same habit — it reached for Person's key.

**The placeholder label is gone.** `sentences.say` made its link with `label="said"`, because a
free link demanded a word, and `relations.relate` then composed a description out of that word:
"Mahmoud Abbas said Fatah" went into the record as a statement nobody had made, beside what the
host really said. An untyped link now carries the words it was said in and nothing else; a free
link must say what it is with either a word or the fact, and reads by its words while it waits —
`Tony Hall — "director of" — BBC (not yet read)`.

**The reading can be late, and the record does not care.** `experiments/catch_up.py` opens a
world as it stands, gives it an engineer, and goes over everything unread. On the world built
without one it found six sentences and eighteen accounts of bare names, all intact: the words
are in the record, the marks are open. It crashed partway through on a missing import, and the
three it had read stayed read — which is what the mark is for.

**Three of the day's defects were found only by a live model**, and all three lived in the code
that talks to one: a branch with no import, a prompt naming a class this world has not got, and
a server that reads nothing without a key. The suite cannot see any of them.

## 2026-09-25 — one door per kind of work: the portrait door stops writing links

Ten facts through a live host, with the engineer on, produced twenty-five links. Half were
facts nobody had stated: `Washington, D.C. capital of United States`, `Camden Town part of
London`, `Bengaluru located in India`, `North America contains United States`.

The source was exact. London, recorded as a bare name and described by the host as "the city
Thomas Kyd was born in", went to the portrait engineer, which wrote:

    world.define_relation("birthplace_of", "a city that is the place where a person was born", …)
    it.set_birthplace_of(Person.identify(full_name="Thomas Kyd")[0])

The same fact the sentence door had already recorded as `born_in` — from the other end, under a
second word. And the rest followed the same path: the host describes a thing the way anybody
describes a thing, encyclopedically, and the engineer faithfully formalises that description.
The prompt's "everything comes out of those words and nothing else" was obeyed to the letter.
The words were there. They were in the description.

**The first fix was to stop the portrait door writing links at all, and it was wrong.** An
account of a thing says what it is to other things — "the capital of Italy" is a fact worth
having, and dropping it leaves it as prose, which this world's own primer calls the worst place
for a fact. What was wrong was never that the engineer wrote links. It was how, and there were
three separate faults, each with its own guard:

**The other end was made, not found.** `identify` records a name nobody here has, so the
engineer's own spelling became a second thing: `BBC` beside `British Broadcasting Corporation`,
with nothing afterwards able to tell them apart. It is `get` now, which finds what is here and
raises when it is not — which Italy is meant is the business of whoever said the words. A line
that raises costs that one link and nothing else, and the loop carries the rest.

**It could not see what was already there.** London, described as the city somebody was born in,
came back as `set_birthplace_of` beside the `born_in` that already held: one birth, two words,
and nothing afterwards can tell they are one fact. The prompt now shows what this thing is
already joined to, and the words this record already has.

**And the encyclopaedia.** `Washington, D.C. capital of United States` was never stated by
anybody; it came out of a description the host wrote from its own knowledge. That is the host's
doing and the world has its own answer to it — a task does not close while a description is a
fact about two things written about one. That check's advice was itself stale, telling the host
to define a type and use the old door; it now says the one thing that is true, which is that
saying which two things is all the host is asked for.

**And the counterexample came out of the prompt too.** Naming the forbidden call, even to forbid
it, is how a model picks it up — the same way an example naming a class this world has not got
had it writing `Place.identify(...)` three times.

**The two doors now:**

    sentence door    two things and the fact in words    →  a typed link
    portrait door    one thing and an account of it      →  a class and its own values

## 2026-09-25 — the old door closed in the code, and what that showed

The texts had taught only the new doors for hours — primer, guide, the engineer's prompts — while
the old ones stayed open in the code. That is not a tidy state, it is two designs running at once,
and a live host found the old door a primer never mentions and wrote most of a run through it.

`a.relate(b, "born_in")` now refuses and names `a.set_born_in(b)`. Closing it touched eleven of
twenty-five test files — in setups, in refusal checks, inside `exec` over a built string. Nothing
was in the wrong place; the door was simply everywhere, and the size of that only became visible
when the change went into code rather than into prose.

**Three things broke that no prompt edit could have shown.**

*Held writes were lost.* A write against an unsettled question used to wait — refusing raises, and
a raise takes the whole block down, so one unidentifiable Anna in a list of four took the other
three with her. That machinery hung off `relate`. Moving the word onto the class made
`q.set_membership(...)` a plain missing attribute. `NeedsResolution` now holds every `set_` too.

*The ends became a refusal.* They are declared per type and the code says why they are evidence
and not a promise: a type declared from its first example refuses its second, and the host answers
that by defining a second type for one idea. Attaching `set_<word>` only to the declared ends
turned that into `Organization has no 'set_kin'. Did you mean 'set_kinds'?` — which reads as the
class being wrong, and in one earlier session a host that was told that stopped using the class.
The word is now visible on the declared ends and refuses nowhere.

*A word the world has not got has no `set_`.* Three tests say what the world does with an unknown
word, and those belong on `relate` — which is exactly the split: `set_` for a word the record
holds, `relate` for a fact it has no word for.

### Every prompt in one file

They lived in five modules beside the code that sent them, which reads well and hides the one
thing worth seeing: what does this world ask, altogether? Three defects in a day were the world
telling a model something other than what was so, and none is visible from inside the module that
holds it. `terraweaver/prompts.py` has them all. A prompt for a door that no longer exists is now
a line nothing imports — `restructure.ASK` is one, in a module nothing has imported for weeks.

Gathering them found a collision that living apart had hidden: the sentence door and the portrait
door both called their system prompt `SYSTEM`.

### A naming rule, and it is in the code

Who invents a relation's word: the engineer, from the fact. What the world does with it was
nothing but a lowercase-and-underscores pass, and the same idea came back as `born_in`,
`birthplace_of`, `plays_position`, `plays_position_of`, `plays`, `chairperson`, `chairperson_of`.

The rule is **a name and a preposition, exactly one**: `capital_of`, `born_in`, `married_to`,
`headquarters_in`. A bare noun or a bare verb reads as nothing between two names; two prepositions
is a word with two endings. `_a_word` settles it rather than asking for it, and `_the_same_word`
treats `chairperson` and `chairperson_of` as one, so no second type is made for one idea.

### The list of words is narrowed by the classes at the ends

A fact about a person and a place is read against the words that have run between a person and a
place; `chairperson_of`, which has run Person → Organization, is a line of list it can only be
distracted by. Narrowed, not hidden — the ends are evidence, and a word whose ends were written
down from one example must stay reachable for its second. The rest follow, said to be what they
are.

### A word lives on the classes it was declared between

The setter and the reader for a relation's word are attached to the ends the type names, and
nowhere else. For a while today they were everywhere, because `Organization has no 'set_kin'.
Did you mean: 'set_kinds'?` reads as the class being wrong — and a host told that in an earlier
session stopped using the class altogether. The answer was the wrong one: the message was the
problem, not the confinement.

    techcorp.set_kin(anna)
    → kin has run between Person → Person, and this one is a Organization. If that is the
      fact, say it in the words it came in — techcorp.relate(other, "…") — and the word for it
      is found here; the ends a type names are what it has seen, not a rule about what it may
      see.

**The rule that the ends are evidence and not a promise is kept, and moved to where it does
something.** A link between unexpected ends is news about the type — so it is said the way any
fact with no word is said, in words, and the world finds the word. What is gone is the silent
version: recorded with a note nobody reads. Twenty such notes in a run leave a world full of
backwards links, each with an honest remark attached.

It paid for itself immediately. Two cases in the suite were writing a link from the wrong end —
`where.set_authority(first_seat)` had an Organization managing a person, when the word says a
manager manages — and both had been passing for months under a note. A note changes nothing; a
refusal changes the line.

## 2026-09-25 — the agent was never told what it had made

Walking the path from the agent's own call, step one: `anna.set_kin(darren, label="mother")`.
The link is made, it reads as a sentence from both ends, and the run came back saying:

    [updated] Kin «A One is B Two's mother (kin)»: descriptions, id, label, label_reverse,
              object, role, subject, tags, valid_from, valid_until

Nothing was ever reported as created — not a link, not a person. `Person.new(...)` twice gave
`created: []`. Every write a host made came back as *changed in every slot it has*, which reads
as "you altered something that was already here".

The cause is mechanical and had been there since statements became one transaction each: the
store's list of what got an id is cleared when a transaction ends, statements are committed one
at a time on purpose, and the run asks for that list afterwards — inside a further transaction,
which clears it again. It was empty every time.

The store now keeps what it made for the *run*, and the runtime clears that at the start of one.

    created: ['Person «A One»', 'Person «B Two»']
    created: ["Kin «A One is B Two's mother (kin)»"]
    created: ['Person «C Three»', 'Related «A One — "A One is C Three mother" — C Three (not yet read)»']

This is the loop the agent learns from — what it did, said back to it — and it was wrong on
every write. No test could see it: the tests read the world, and this was about what the world
*said*.

## 2026-09-25 — walking the agent's own path, on the core it actually starts with

**A methodical mistake first.** Every observation of the day was made against the `job_search`
fixture, because it has people and links already and writes nice examples — and conclusions
about "what the world is by default" were drawn from it. The fixture holds fifteen classes the
core has not got, including `Kin` with its fourteen labels. The minimal core is five.

### What the core holds

    Thing, Related, Person, AIAgent, Event     the world's picture
    Task                                       the world's own record of work done on it

**`PartOf` and `Kind` are out of it.** They were two links every world was thought to need, and
they are not: a part and a whole is a relation like any other and the word for it comes from
what was said. Standing in the core they were two words a reading could reach for instead of the
one the fact used — "the capital of France" went in as `part_of`, true and unanswerable.

**`Task` is out of the agent's sight.** It is the world's own bookkeeping, written about the
agent by the world. It was in the namespace and listed in the catalogue under a line saying it
was the world's and not the person's — and being listed is being offered: a host asked what is
in this world read its own task record as somewhere to put things. The test that checked the
task record did so by running `Task.all(...)` as the host, which is exactly the thing that
should be impossible; it reads from the world now.

### Two names that rhyme are not one name

On the bare core, the first line written found it:

    Person.identify(full_name="Sasha")[0]  ->  Masha

`Sasha` against `Masha` scored .80 — higher than `Anna` against `Anne`, which is one name spelled
two ways — because four of five letters are shared. The measure was ranking rhymes above
variants. What tells them apart is where the difference falls: a variant differs at the end, two
names differ at the start, and the first letter of a name is the one nobody misspells.

    Sasha ~ Masha  .80 -> 0        Anna ~ Anne        .75 kept
    Boris ~ Doris  .80 -> 0        Kate ~ Katherine   .62 kept
    Kate  ~ Nate   .75 -> 0        Dr. Rao ~ Arun Rao .90 kept

### An untyped link has neither a label nor a nature

Both were asked for and neither can be answered. `Related` declared `label` required, so the
world nagged for a word about a link whose whole point is that nobody has one yet; and it
declared a `nature` attribute, so the world asked what *sort of thing* a link is. Both are
residue of the design that had natures. What an untyped link is, is the fact in its own words.

### The classes a world starts with hold no privilege

Stated as a principle: **a class that was there when the world opened exists on exactly the same
terms as one the world grew for itself.** Nothing marks it, nothing is forbidden to it, nothing
is forbidden *because of* it.

`BASE_CLASSES` is a starting set, not a rank. It names the five a world cannot begin without —
`Thing` to put anything at all, `Related` for a link with no type yet, `Person` and `AIAgent` so
there is a "me" and a "you", `Event` for the one kind whose time is part of what it is — and
that is the whole of what the tuple means. After the world opens, `Thing` and a class the world
made last night are the same kind of object: both are read from a spec, both can be extended,
both can be wrong, both are judged by what has accumulated under them.

Where the world still breaks this, and it is one place: `growth` refuses to extend anything that
is not in the base (`extends 'City', which isn't a core class`), and refuses to redefine an
attribute a base class declares. That is two privileges — only the shipped classes may be built
on, and only their attributes are beyond correction — and it means a world cannot deepen its own
vocabulary past the first step it took away from ours.

What may honestly differ is **maturity**, which is read from the world and not from provenance:
how much has accumulated under a class, how long it has stood, how often it has been corrected.
Where a class came from is a *fact about it*, recorded beside it, of the same kind as any other
fact — never a category that changes how it is treated. This sharpens the rule of 2026-09-24,
that the inspector must look at every class and not only the ones a world grew: that said don't
*judge* by source, this says don't *mark* by it either.

## 2026-09-25 — experiments are numbered, and the first one types a relation from words

**`sketch/` is gone; experiments are numbered directories the user starts.** The sketches were
fifteen files at the top level, all about one question, and the last four of them were written
against stand-in classes — which is what a sketch is for and also what stopped them settling
anything: a vocabulary converging over eight facts in a dictionary of fake types says nothing about
a world with a store, refusals and periods. They are now
`experiments/01_relation_formalisation/earlier/`, kept whole rather than summarised, and the
convention is written down in `experiments/README.md`: one question per numbered directory, the
README before the first run, the real world driven through the host's own doors, the base as the
starting world, and the trace of every run kept beside it.

### The mechanism: two entities, a description, and the code that records the link

    look    is there already a word for this kind of link? A closed question over what the record
            holds, narrowed by the classes at the ends, "none of these" among the options — the
            picker. Nothing is defined and nothing is named twice.
    make    only on "none of these": one open call to the engineer for **the lines**, not for a
            description the world renders.
    run     through `runtime.run`, with the two things bound before the code starts. It fails, the
            world says what it would say to a host, and that goes back to the writer. Three goes.
    end     the bare link stops where the typed one begins, and is not erased.

**Nine facts, three runs, and the third typed all nine** — seven words for nine facts, `capital_of`
made once and joined twice, nothing left bare, and the employment handover dated from the words:
Acme from 2019 ending 2023-03-01, Brightwork from 2023-03-01. Asked who she works for now the record
says Brightwork; asked about 2020 it says Acme.

That answers the question the entity door raised and the relation door never settled: **asked for
code, a reader records a relation as well as it records a thing.** The argument for asking for data
— the shape of what is written is ours — is real and is not worth what it costs here, because every
refusal the world makes of a host is then a refusal it cannot make of the reading.

### A date degraded is worse than a date refused

`starts="March 2023"` was refused: the record read `'in 2006'`, `'3 years ago'`, `'2006-01-01'` and
not the commonest way anybody says a date. What the writer did next is the whole lesson — it gave
the year alone, which the record *took*, and a month somebody named went in as **1 January**. A
refusal costs a line; a degradation costs the fact, because nothing afterwards tells it from a day
somebody knew. `timeutil.told` reads a named month now, with a month and no day being the first of
it, which is exactly what `'2006-03'` and `'2006'` already came to.

### Facts are read in the order they were said

Everything the world does with a second fact about the same two ends assumes the second one arrived
second — a new employer ends the standing one, and the line the world offers when it refuses, *end
that one where this one begins*, is written for a fact that starts later than what is there. The
reading was going newest-first, because `sentences.unread` returns whatever order the tables give,
and against a 2023 employment the 2019 one had no honest line at all. One fact in nine was lost to
that, and it is sorted by the moment the host said it now.

### Measured against the working code

**The reader answers `over_time` correctly** when asked in the words that say what it does: True for
an employer and a spouse, False for a birthplace, a part, a sibling, a kind. `sentences.formalise`
does not ask — it passes `over_time=False` on every type it declares — so that defect is the
world's, not the reader's, and it is worth exactly one argument to fix.

**`over_time=True` overrides the cardinality on both sides, and it fires people.** The engineer said
`works_at` is many-to-one; the world stored one-subject-at-a-time too, because
`one_subject_ever = over_time or one_subject`. In the world this run left behind, hiring Boris at
Brightwork ended Anna's employment there — a correct answer destroyed by the mapping, rewriting a
fact about a third party with nothing but a hint to say so. The two axes have to be per side:
`functional` from `one_object`, `inverse_functional` from `one_subject`, `over_time` deciding only
whether the second one ends the first or corrects it.

**And `_correct`, the branch a one-ever type takes, only prints.** Its docstring says the earlier
link is "marked as no longer held" and nothing marks it, so two links stand and "which now" has two
answers. Found by reading, not by the run — the run never reached it, because the reader answered
`over_time` well enough to stay out of that branch.

## 2026-09-25 — `over_time` is gone: cardinality says how many, and it says it about a moment

Decided long ago in `docs/relation-properties.md` (part three) and carried out now, because
experiment 01 measured what it cost. One axis, per end, about one moment:

    cardinality="many-to-one"    this thing has one of those at a time   -> functional
    cardinality="one-to-many"    that thing has one of these at a time   -> inverse_functional
    cardinality="many-to-many"   neither is limited, they accumulate
    cardinality="one-to-one"     both ends

**What a limited end means, and it is the whole of it:** adding a link never removes one. The
standing link's period is closed where the new one begins, both stay in the record, and if only one
can hold then the periods do not overlap. That is all "supersession" is here — there is no separate
act, and no category of "correction".

### Why the second axis had to go

`over_time` was a boolean beside the cardinality, and the two cancelled each other in both
directions. Measured in experiment 01, on a type the world had just read out of a host's sentence:

    over_time=True    made **both** ends one-at-a-time whatever the cardinality said. `works_at`
                      was declared many-to-one — many employees per employer — and came out with
                      one employee per employer too. Hiring Boris at Brightwork **ended Anna's
                      job there**, with a hint to say so and nothing else. A fact about a third
                      party, rewritten, because a boolean overruled the thing that was asked.
    over_time=False   put the type in the withdrawn "one ever" category, where a second telling
                      was called a correction. That branch only ever printed a note: nothing was
                      ended and nothing marked, so two links stood and "which now" had two
                      answers. Its own docstring said the earlier one was "marked as no longer
                      held", and nothing marked it.

And "one ever" is not a category. A record only ever accumulates, and nothing in it is one forever:
a birthplace changes in the record not because anybody moved but because sources disagreed or
somebody was wrong. Forever is a property of the world, not of the record.

### An undated second telling ends the first *before now*

The case that was never reachable, and the reason it was not. `relate` computed
`start = period.get("valid_from") or timeutil.now()`, so a link nobody dated arrived at the check
looking like one dated today — the standing link was ended today, exactly, and the hint said "the
date this one starts" about a link with no start. A day nobody said, indistinguishable later from
one somebody knew: the rule the substitution was quietly breaking.

The start is now passed as it was said, `None` and all, and the undated case ends the standing link
at the one boundary that needs no day: **some time before now**, `until_is = before`. Asked whether
it holds now the answer is no; asked whether it held in 2020 the answer is *nobody knows*, which is
true and which a host can act on. `_not_ours_to_end` used to refuse here — "nothing to end it at but
a date nobody gave" — and there is something to end it at after all.

### What went with it

- **`_correct` and the `functional is True` branches** in `_check_functional`. The question the
  second of them raised — two subjects holding one object, worth asking about once — stays, under
  the per-subject side.
- **`_only_what_still_holds`** and `_note_it_rests_on_order`. That filter decided what holds on the
  way *out* of a read, by which telling arrived last, because the "one ever" category had no periods
  to decide with. Periods decide now, so a read cannot answer differently from the record.
- **`kind.changes`**, the switch that chose between the two categories, and with it the line in
  `questions._SAYS` that mapped "at a time", "over time", "current" onto it — those words mean
  `one_per_subject = True` now.
- `True` in a spec on disk is read as `at_any_time` when the class is built. Nothing to migrate:
  the branch it named printed a note and ended nothing, so no world loses behaviour it had.

### Where a test was measuring the bug

`tests/test_time.py` declared `chairs` as many-to-one and relied on `over_time=True` to limit the
*other* end — the organisation's. Written honestly it is `one-to-many`. `tests/test_superseding.py`
had a whole section for "a correction", which is now the undated handover: the earlier link is ended
before-now, and the checks are that no day was invented and that the world says so and asks when.
All 25 test files pass.

### The core's own types say how many, on both ends

Written into `ontology/core/*.json`, with a gate in `tests/test_relations.py`. Seven of the twelve
relation types the core ships said **nothing at all** about how many may hold; five said something
about one end and nothing about the other. In code an absent field and `false` behave identically —
both read through `.get()` — and to a reader they are not the same thing at all: absent says nobody
thought about it, and a side nobody thought about is a side that limits nothing by accident.

    Authority        —            one at a time     one manager per report; a manager has many
    Ownership        —            one at a time     a thing has one owner; a person owns many
    PartOf           one at a time  —               a part has one whole; a whole has many parts
    Partner          one at a time  —               symmetric: the two ends are one, said once
    Kin, Kind, Located, Membership, Participation, Related, Service, Social — neither end

Each also carries `how_many`, a sentence saying why, because the reasoning is the part that cannot
be recovered from the two booleans. The rule behind every line: **limit a side only where the word
itself means one at a time.** An under-limited side keeps both facts and the world can ask; an
over-limited one rewrites a fact about a third party, which is what hiring Boris did to Anna.

Two of these are new claims rather than transcriptions. **Ownership** gains one owner at a time on
the thing's end — ownership transfers, and two owners of one thing over one stretch is a handover.
**Located** gains `one_of_a_label`: a person has a home and an office at once, so the type limits
neither end, but one *home* at a time is true and the limit belongs to the word the user said.

### A link that arrives where something stood begins today

The other half of the same rule, and the user's: if the new link says nothing about when it began
**and something was standing there**, it begins today — marked `before`, because the change happened
at some point before today and nobody said when. The standing one ends at the same moment, from the
same `now()`, marked the same way.

    Acme Corp hq in Tallinn   starts 2026-09-25 (before)   —
    Acme Corp hq in Dublin    —                            until 2026-09-25 (before)

Left with no start at all, as the first cut of this had it, the pair read as two links that both held
from the beginning of time and only the end of one said otherwise. **A fact with no start and nothing
before it keeps having none**, which is −∞ and means what it says: held as long as anybody knows. An
event is not this case — an event's time is `start_time`, a required attribute, not a period.

## 2026-09-25 — a claim is put to the picker before it is written, and "reader" is gone

**The engineer wrote a date nobody said.** Given "Rome is the capital of Italy", which carries no
date, it wrote `starts="1792"`, and the record then held `Rome capital of Italy from 1792-01-01`,
indistinguishable from a date somebody gave. The question already said *nothing is worked out from
elsewhere*, in the words that say why. An instruction is a hope.

*Corrected the same day:* the date did not come from the Paris fact, as first written here, nor from
anything the model knew. It came from **the question's own example** — the definition was shown as
`capital_of` with `a.set_capital_of(b, starts="1792")`, which for Rome is the right line whole, so it
was copied whole. See "an example is copied, not read" below; the check stays, because a claim the
sentence does not bear out should never be written whatever planted it.

So every claim the lines make is put to the **picker**, one closed question each, all in one call —
**before the lines run**. Measured over nine facts: 17 claims, one refused, and it was the invented
one at 1.0; every date that was really in a sentence passed (1792 in the Paris fact at 1.0, "since
June 2015" at 0.99, 1558 at 0.94), and every link claim came back borne out at 0.92 upward.

**Before, not after, and that is the whole shape of it.** A check that reads the record afterwards
has to delete what it finds: the write is committed, whoever holds the instance holds a stale one,
and a link taken back leaves the fact it came from unrecorded. Asked first, a claim nobody made is
never added — the lines go back to whoever wrote them with what is wrong, through the loop a refusal
already uses, and the three goes are the three goes.

Two boundaries, both deliberate. **Only what came from the sentence is asked about** — the link,
which way round, and every attribute the line writes onto it as a literal: when it began and ended, a
label, a role. Those are the only places a claim nobody made can get in, because they are the only
places filled from the text; the rest of a line is the world's own structure. And **the doubt goes
to the line, not against it**: below 0.6 the verdict is not acted on, because a false alarm spends a
go out of three and takes the fact with it, while a missed claim is still there for a later pass.

### "Reader" named three different things, and now names none of them

The word meant the engineer in `sentences`, `portraits`, `runtime` and `timeutil`; the picker in
`outside.Closed` and `portraits`; either of them in `inspector`; and *whoever reads the record later*
in a dozen honest places. Asked what a reader was, the only true answer was "it depends which line".
Every use that meant one of the two parties now names the role — including `server._give_it_a_reader`,
which sets `world.engineer` and nothing else — and the uses that mean a later reader of the record
stay, because that was never the ambiguity. What keeps the word: two columns in the inspector's own
side tables, where renaming it would want an ALTER on every world already on disk.

**A NameError fell out of it.** `inspector.write_the_questions` guarded on `if reader is None` in a
function whose parameter is `engineer` — nothing bound that name, so the call raised every time it
ran. Offline work, run rarely, and nothing in the suite reached it.

## 2026-09-25 — the reading moved into the world, in modules, and the old one is gone

**The boundary.** Storage takes structured facts and it works: links, periods, statements, the
image, the sandbox. What was rebuilt is the part in front of it — from a host saying two things and
a sentence to the lines of code that create the facts. That part was designed and measured in
experiments/01 and then not carried in: for a day the work went into patching the storage side
instead (`over_time`, `nature`, a half-started rewrite of `relations.py`), each patch finding the
next layer of an older design. The rewrite of `relations.py` was reverted before it went anywhere.

**`terraweaver/formalise/`**, one module per question, because each is asked of its own party and
each has been wrong in its own way:

    look.py      the picker — is there already a word for this kind of link?
    make.py      the engineer — the lines that record the fact, declaring a word if none
    check.py     the picker — is every attribute that came from the text borne out? before running
    write.py     run through the host's door with the two things bound; confirm what landed;
                 end the bare link where the typed one begins
    __init__.py  every bare link, in the order it was said

The questions are in `prompts.py`, where every prompt lives. The code is the experiment's, moved,
not redesigned; the experiment now runs the world's module and keeps its own old copy in `earlier/`.

**What was replaced, and why it had to be.** `sentences.formalise` asked the engineer for data and
rendered the call itself — and the renderer is where `nature` and `over_time` survived long after the
structure had dropped them (`nature=CLAIMS_NOTHING`, `over_time=False` on every type). Worse, it had
**not run at all since commit 7c15f16**: it referred to `SYSTEM` and `ASK`, which that commit removed
from the module, and the close caught every exception and returned an empty dict. Every task since
closed with its sentences unread and nothing to say so. The close now reports a failed reading in its
reply instead of swallowing it.

**One change on the storage side, at the boundary itself:** `define_relation` no longer requires a
`nature`. A structured fact is the word, what the kind is, what each end is and how many hold at a
moment; a nature is not part of it, and the door had been passing a stand-in only to get past the
refusal. Given, it is still read; not given, the type claims nothing beyond the link itself.

**Under a gate:** `tests/test_formalise.py` drives the whole pipeline with both parties scripted — a
word made once and found again, an invented date refused before anything runs, facts read in the
order said so the later employment hands over, and the close reading through the same path.

### An example is copied, not read

The first run through the world's module read Rome, wrote `starts="1792"`, was refused by the check,
and wrote it again — three goes, three refusals, and the link stayed bare. The stubbornness was the
clue: the definition's example in `NO_WORD_YET` was `capital_of` with `starts="1792"`, which for "Rome
is the capital of Italy" is the correct line in every other respect. The engineer was not inventing a
date; it was copying the one line it had been shown that fitted.

Examples in the sentence door now name a word no fact in sight is likely to need (`mayor_of`) and carry
no date at all, and every date in the question is a placeholder — `starts="<the time the words give,
in their words>"` — which the record refuses if it arrives unfilled. Copied, it fails loudly at the
door instead of landing quietly in the record. The lesson is the one `_classes_here` already carried
for classes: an engineer given an example that names something copies the example.

### Everything after the description is said by name

The next run through the world's module lost "a dog is a kind of mammal" three goes running, and the
record's answers showed why. The engineer wrote the call in order —
`define_relation("kind_of", "…", "many-to-many", "a dog", "a mammal")` — and the storage call still
had the slots of its older shape in those positions: subject class, object class, nature. "a mammal"
landed as a nature, the refusal said what a nature may be, the engineer added `nature="kind_of"`, and
the third go failed on a duplicate argument. A structured fact walked into the positional layout of the
design it replaced, and the refusal pulled the dropped field back into the conversation.

After the word and the description every argument is now said by name, and a call that gives more in
order is refused with the form written out. Nothing in the code called it positionally, so nothing
else moved.

## 2026-09-25 — the road to submission: a picker of our own on Nemotron, research as "pick it for me", and a world for each search

Five weeks to the deadline, and four decisions that shape them. The plan itself is in `docs/TODO.md`,
"Road to submission".

### The picker becomes ours, on Nemotron, hosted on Nebius

Jev is TypeSafe's closed model. Keeping it means a judge needs a TypeSafe account to run the world,
and it is not an NVIDIA model, which is what the hackathon asks for. The replacement is the recipe
already built for it: `typecastlm` is a Jev-class decision model — a Qwen3.5-4B trunk fine-tuned for
sequence classification, a verdict head over the last hidden state (`true`, `false`, `unsure`), mark
rows taken from the vocabulary for `choice` and `scale`, and a calibration temperature per mode. One
forward pass, nothing generated.

Moving it onto Nemotron takes two steps, because Token Factory serves only the large Nemotrons
(`Nano-30B-A3B`, `Super-120B-A12B`, `Ultra-550B`, `3.5-Lightning`) and cannot serve a custom head:

- **Day one:** a picker on `Nano-30B-A3B` through Token Factory, reading the probability of each
  option from the logprob of its letter. Token Factory returns `logprobs` — checked. Weaker
  calibration, no infrastructure, and Jev leaves the world at once.
- **Then:** the `typecastlm` recipe on a small dense Nemotron trunk from Hugging Face (the Nano 4B
  class, which fits a 16 GB card as Qwen3.5-4B does), served from a Nebius AI Cloud GPU machine in the
  container `typecastlm` already ships. The world does not change: `outside.TypecastLM(endpoint=...)`
  already speaks that protocol.

### Research is one mechanism: "pick it for me"

Tickets, housing, products, things to do — the same loop on different data. Any assistant with web
search can find a flat in Berlin; what it cannot do is what this world is for:

1. **Build the query from the person's world, not from one sentence.** "Moving in March", "up to
   1400", "we have a cat", "never the ground floor again" were said on different days to different
   assistants, and the world already holds them as structure. The query carries the requirements and
   not the person.
2. **Record the findings as checked facts, not as prose in an answer.** A page is text like anything
   a host says, so it goes through the same `formalise` pipeline with the page as its source — and
   `check.py`, which refused an invented date today, refuses a price the page does not bear out.
3. **Outlive the conversation.** "That flat is gone" and "the price dropped" are handovers by period,
   with dates and an as-of; tomorrow another assistant opens the same world and knows what was looked
   at, what was dropped and why.

Preferences need no class of their own for this: "Anna likes jazz" becomes a typed link through the
same door as any other fact.

### A world for each search

The author's idea, and the shape the spec already allowed for — several worlds loaded into one
namespace. Candidates do not go into the person's world: forty events or listings would bury it. They
go into a research world of their own, and there the host picks, ranks and filters them with code, as
it does everything else; the person's world is loaded beside it for the criteria. What moves into the
person's world is the choice, and why. Still open: whether a research world is kept, dated — so "why
not that one" can be answered later — or discarded once the choice is made.

### The demo: "where to go on Saturday"

Of the three cases it shows most of what this world is made of — people, the links between them, and
time: who is going, what she likes, when both are free, what went wrong last time. Event pages are
also what search finds well; listing sites mostly do not open to it, which in a three-minute video is
a risk worth not taking. Housing and products are the same code and get a line at the end and a
paragraph in the write-up.

## 2026-09-26 — the old core is gone, and a preset class is made like any other

The core had grown to twenty-odd classes — Organization, Place, Membership, Kin with fourteen
labels, Vacancy, Idea, Preference — each written by hand for a job-search fixture, each with its
own branches in `relations.py` and `impls.py`. None of them is in the base any more. A world opens
with `Thing`, `Related`, `Person`, `AIAgent`, `Event` and the world's own `Task`, and whatever
else it holds it was told, through the same doors a host uses: `define`, `define_relation`,
`attribute`.

**Why delete rather than keep them as a preset.** A preset is only honest if it is built the way
a grown class is. These were not: they carried natures (`part_of`, `kind_of`) that no word the
host defines can have, derived fields (`organization`, `job_title`, `relationship`) read off
relations by hand-written code, and label tables that decided roles. Every one of those was a
second kind of class, and every bug of the week — hiring that fired others, a correction that did
nothing, symmetric reads bypassing the rule — lived in the branches they needed.

**A preset class is a grown class with a source.** `growth.apply_growth` treats the base specs
exactly as it treats grown ones: a whole spec replaces or adds, then extensions apply to any class,
in a second pass so their order carries no privilege. The only difference kept is `source`
(`"preset"` or who stated it), which is a record, not a rule. `open_world` is the one recipe —
base specs, then what was grown, then the doors — for the server, the tests and the experiments.

**What went with them:** the job-search fixture and its database, `impls.py`, the derived-relation
layer, `BY_NATURE` cases for `part_of`/`kind_of`, `_correct`, the "one ever" branches, the
scenarios that were written against the fixture, and `describe_world_api`. The host guide was
rewritten for the base world.

**Tests declare what they need.** `tests/base.py` opens a base world and grows an attribute or
declares a word the way a host would. A test that needs an employer defines `works_at`; one that
needs an address grows `Person.email`. A test built this way tests the world a host meets.

**Bugs the port turned up, fixed:** twin prefilter compared raw values instead of canonical ones;
"noticed" questions deduplicated without their text; growth on a preset class was lost on reopen;
symmetric reads skipped `rule()`.

**What the port could not carry over, and why.** These tested machinery that is gone, not
behaviour we lost by accident:

- role labels (mother / stepmother, "a second mother is refused", chains named "sibling in law")
  — words have no labels; roles are `subject_is` / `object_is`;
- hints that read labels: a gap between two spells of one post, a link running against every
  other of its label — the gap check could return keyed on the word;
- a cycle of parts refused — `part_of` is a word like any other now;
- a word refused between classes it was not declared for — classes on a word are watched, not
  enforced;
- `organization=` / `job_title=` / `relationship=` at creation.

**Two things the port showed that are not settled.** `Person.new(email=...)` on a class without
`email` is refused, while `ada.email = ...` grows the attribute — the same word, taken at one door
and refused at the other. And `_named_elsewhere` compares names only for classes in
`matching.NAME_KEYS` (Person, Event, Thing), so a class the world defines never takes part in it:
a privilege the base classes still have.

## 2026-09-27 — a dict at the class door, and 32% against 86% on the same fifty facts

A run of the FactConsolidation slice on the new base was stopped after three minutes instead of
being left to finish: the world it had written held eight relation types and not one typed link —
220 rows of `Related` carrying prose (`descriptions: ["performed by"]`). The type of degradation
the README already has a name and a price for.

**The cause was one line of ours.** `World._name`, the resolver every door that takes a class
passes through, was `cls.__name__` for anything that is not a string. The recorder wrote
`world.identify({"name": name})` — attributes gathered in a dict, the shape most APIs take — and
got back `AttributeError: 'dict' object has no attribute '__name__'`. A Python internal says
nothing about what this world wanted, so the block was rewritten, seventeen finished lines went
with it, and from there the recorder stayed in prose for the rest of the run.

Two doors of ours answered the same turn well — `world.classes()` named `classes_here` and
`classes_like`, `world.identify("Fatah")` said `Fatah.identify(<what the user called them>)`.
The one that crashed is the one that decided the run. A door refuses in the world's own words,
naming what to write instead, or it is not a refusal at all — and this is the cheapest possible
place to hold that rule, since all nine class doors come through the one resolver.

**Measured, one variable, the same fifty facts**, by `experiments/check_expected.py` against the
expectations written down per fact — a lookup, no model, no question asked of a host:

| | before | after |
|---|---|---|
| as owed | 15 (32%) | **40 (86%)** |
| backwards | 2 | 3 |
| no link | 5 | 0 |
| missing | 24 | **3** |

Batches 1–20 went from **0/18** to **18/18**: the loss sat exactly where the crash was, which is
why this reads as structural rather than as one draw of a noisy number. What is left is the two
faults already on the list and not addressed here — three links written backwards (`capital of`,
`author of`: the `_of` direction, measured three ways and deliberately not wired to a picker) and
three `is associated with the sport of` facts with nowhere to go.

**Also done, so a check like this need not cost an hour again.** `run_fc.py` takes `--facts N`
(write only the first N) and `--keep <dir>` (build the world where it can be read afterwards, and
say where it is). The check above cost $0.68 and eleven minutes; the full slice costs $7 and
three quarters of an hour, and finding this at the end of one would have been the whole point
of the morning wasted.

**A record for honesty**: the "before" world was written by the stopped run, whose `config.json`
says commit `b0872f8`; the "after" world ran from the working tree with the fix in it, before the
fix was committed. Same facts, same host model, same slice.

**Found while tracing this, not fixed here**: `ontology.define_class` does `list(identified_by)`
on what `define` stores as a string, so a class the host defines comes back from a reopened world
with `'n'` as its name key — identity dead for that class, duplicates unchecked. It does not touch
this measurement (registration inside the live process is correct, and this host defined relation
types only, all with `identified_by: None`), and it did touch the blank-world runs, where the
host defined `Organization`, `Place` and `Work`.

**Two claims in the 2026-09-26 entry above are wrong and are corrected here.** A class the host
defines *does* take part in `_named_elsewhere` — `register_identity` is called from `define`, and
`_named_elsewhere("Thing", {"name": "Osteria Rossa"})` finds the `Restaurant`. And grown types
*do* come back when a world is reopened: `open_world` applies the growth pass, which reading the
store directly through `WorldRuntime` skips.

## 2026-09-27 — what the close asks for, it names in something the host can run

Six facts, aimed: the ones the fifty-fact check had marked wrong (22, 28, 32, 33, 36, 47), re-run
into a world of their own for a few cents. What came back was one link of a type called `Capital`
between two nameless `Thing`s, the account of that link written onto the **user's own record**, and
five facts with no links at all. Traced in the transcript, turn by turn, because the first
explanation that occurred to us — the engineer mangled it — was wrong: the engineer never ran.

**What actually happened.** The host fumbled `world.relate(a, "capital", b, at=...)` (the kind in
the middle, an argument that does not exist), then missed the `define_relation` signature four
times over — the fumble already on the list at 38.6 per 1000 — then wrote the link backwards. Here
the world worked: the close asked it to read the link back, it reasoned about direction correctly
and fixed it itself. Then the close refused again, for a description, and listed what it wanted:

    Not closed: 1 thing(s) … :
        a442f9c7be034f10b3e74a75c946bfb1 capital eeb0ec6abbab40af9fa75cf4ca0e6127 (capital)

**A link's own word for itself is its two ids.** There is nothing the host can do with that line.
It swept `world.all()`, found the objects with no name — the links — and described whatever came
back, which is how a sentence about Chang'an landed on `you`. Thirty-three turns on one fact; the
other five got what was left.

Asking a link for a description is deliberate and stays (`_needs_describing`: only that line tells
one `Kin` from another). Naming it by ids was the defect, and the fix was already written next
door — `_ask_about_bare_things` names the host's own variable, because that is the whole reason
it asks after the run rather than during it. `_reach` now does the same for the close, three ways
down: the host's own variable, the reading that reaches a link from an end it holds, then a lookup
by name anybody can run.

    tang.describe("...")
    changan.relations("capital_of")[0].describe("...")
    changan.describe("...")

Tested by running the lines the world named and closing the task (`tests/test_tasks.py`), which is
the only check that means anything here: a line the host cannot run is the bug.

**`you` was never asked for.** `person:user` is not in `bare_names` — the predefined records, the
user and the agent, stayed out of the queue as they should. The host reached the user's record on
its own, and only because ids were all it had to match against. Whether `describe` on those two
records should be refused outright is a separate decision and is not taken here.

## 2026-09-27 — a run without an engineer measures a world that cannot type, and said so nowhere

`.env` holds a real `NEBIUS_API_KEY`. Nothing in `terraweaver` reads `.env`: the key reaches a
world from the shell that started it. Both of this morning's runs were started from a shell that
never exported one, so the server got no engineer, `_read_what_was_said` returned at once, and
every link said in words stayed untyped. The run finished and printed a number.

The experiments side already had this right — `base_run._the_key()` reads `.env` and prints a loud
line when there is none. The benchmarks side had nothing. `host.keys()` now reads it and hands it
to the server, and `run_fc.py` writes `engineer` into `config.json`, so no number is ever read
again without knowing whether a reading was possible. The two readers are duplicates and should
become one; not today.

**A correction to what was said earlier today.** "Typing barely happened, so the defect is
untouched" was wrong twice. A world without an engineer keeping its links untyped is documented
behaviour, not a defect — `server.py`: "the link is made at once and stays untyped, which is a
poor link and a real one". And the reading can be run later on purpose: `experiments/catch_up.py`
opens a world as it stands, gives it an engineer and goes over everything unread. The fifty-fact
world holds 47 said and 47 waiting — the queue is intact, so nothing is lost by having written it
without a key.

**What the 47 untyped links showed, and it is the thing worth keeping.** Their descriptions are
exactly what an engineer needs: `capital of`, `authored by`, `founded by`, `associated with sport`,
`plays position`, `died in`. Short, faithful, one per link, and the direction is stated in the
words — `Tang Empire → Chang'an | capital is` and `London → Great Britain | capital of` are both
right and point opposite ways, because the words say which way. A host that says it in words gives
the reading everything it needs; this is the storyteller and the engineer working as intended.

**Two of the six "failures" were never the world's.** `Steve Sax → Baseball | associated with sport`
is in the world and `check_expected` called it missing: it compares names case-sensitively, and the
expectation says `baseball`. And a bare link's direction is a verdict that check cannot honestly
make — it deliberately reads no words, so for a link whose kind is still `related` it calls
`Starship Troopers → Heinlein | authored by` backwards. A third verdict is owed there —
**untyped** — rather than a judgement made without the evidence. Not done here.

**One of the six is a real error, and not in the typing.** Facts 32 and 47 say *American football*.
There is no such thing anywhere in that world: both links point at `association football`. Two
different sports were identified as one, which is the kind of error that answers a question wrongly
with complete confidence.

**Cheap aimed runs, so this can be done again.** `run_fc.py` takes `--from N` (add to the world
`--keep` already holds instead of writing it again from the first) and `--only 22,28,33` (just
those facts, each keeping the day its own batch was said on). `--keep` is resolved now: a relative
path was joined against the host's own folder and the run died on a missing MCP config.

**Next, and argued rather than assumed:** `relate(b, "founded")` is refused while
`relate(b, "died in")` is taken, because `_is_a_sentence` falls back to counting words when the
world has no type by that name. The engineer makes the type from the description, so one word is
as good a description as three, and refusing it throws away the only account of the link there
will ever be. A word this world has no type for is words the user said.

## 2026-09-27 — a word this world has no type for is words, whatever its shape

`relate(b, "died in")` was recorded as a link carrying those words; `relate(b, "founded")` was
refused for naming a type that does not exist. The difference was `_is_a_sentence` falling back to
counting words once the world had been asked and had no type by that name. Nothing distinguishes
the two for anybody downstream: the words land as the link's description, the engineer makes the
type from the description, and `employed_by` and `employed by` are the same account of the same
fact. The host, meanwhile, cannot know which side of a line drawn at one space it is on — measured,
it lost five lines of a block at a time and left the fact recorded neither typed nor as it was
said. The fallback is gone: a word the world has no type for is words the user said.

**What that change reaches.** Twelve checks in three files went red, all for one reason: a single
unknown word no longer arrives at the layer that turns a word into a type, so `MAKES_TYPES` and
`TAKES_NEAR_WORD` are unreachable from a host call. They stay live where a type is actually made —
the reading (`portraits.py`) — and on a read of a word that was mistyped. So the checks moved to
that layer rather than being deleted: `relations.relate(world, a, b, word, {}, {})` is where the
switch decides, and the lesson each of them records — a near word is not the word that was said —
is unchanged. `test_tasks.py` had built its doubt out of type invention and now builds it out of a
link recorded as `related` with a description, which is a live doubt with no switch turned on and
a better test for it.

**Aimed re-run, the same six facts, third time.** Fact 22 cost 11 turns against 33, and the link
is right in both its ends and its words: `Chang'an — "capital_of" → Tang Empire`. The close's
naming fix is what bought that.

## 2026-09-27 — the reading runs in the server's request path, and it costs two minutes

The five facts of the second batch of that run were never recorded, and not for any reason in this
world's code: the host's session reported `terraweaver` MCP server `status: failed`, a connection
timeout at 30 seconds, so it had no tools at all and said so. Each batch is a new session, and the
session before it had just closed a task.

**Measured on the same world:** `experiments/catch_up.py` over one untyped link and one bare name
took **2m07s**, of which one second was local — all the rest waiting on Nemotron. The close runs
that same pass inside the server, so the server is unavailable for minutes at exactly the moment
the next batch tries to connect. This is the same shape as `inspector.twins` on the TODO, and the
same answer is owed: a reading that takes minutes does not belong in the path a host's next call
has to get through.

**And it typed nothing.** `facts said in words: {'typed': 0, 'joined': 0, 'defined': 0, 'left': 1}`,
`things that came in as names: {'read': 1, 'placed': 0, 'gave_up': 1}`. One link, one name, two
minutes, nothing decided. Whether that is the model, the prompt or `formalise` is the next thing to
find out — the tally says what happened and not why, which is itself worth fixing.

## 2026-09-27 — every reading is written down, because one number per run is not a measurement

A reading is a loop: the engineer writes lines, the check puts each claim to the picker, a refusal
goes back, three goes at most. All of it was already in the trace `formalise_one` returns, and
nothing kept it — `runtime._read_what_was_said` reduces the traces to `len(traces)` at the close and
`catch_up` prints the tallies, so a run could say how many links were typed and nothing about how
many goes it took, where they went, or how sure the check was when it refused. A tally cannot tell
"typed on the first go" from "typed on the third after two refusals", and those are not the same
system.

So `formalise/record.py`: one row per reading in the world's own store — the link, the words as the
host said them, goes, how it ended, the word it landed under, whether that word was made for it,
seconds, every verdict with its confidence, and what the look found. `catch_up --shape` reads the
distribution back and spends nothing.

**What it said on the first case it was pointed at**, and it corrected a number of ours in the
process: the reading of one link took **42.4 seconds**, not the two minutes reported earlier — that
was the whole catch-up, one link plus the bare-name pass plus startup.

    1 reading(s): 0 typed, 0 of them under a word made for it
      goes:      1x3
      ended:     not borne out by the words 1
      verdicts:  not_in_it 3  (sure when refusing: 1.0)
      seconds:   least 42.4, middle 42.4, most 42.4
      said as:   one word 1

## 2026-09-27 — the check reads the code, and three of four ways of writing one fact escape it

Traced from the reading above, where the engineer wrote the right lines three times and the check
refused them three times. Two things came out of it, and the first is a correction of what we said
earlier today.

**The verdict was wrong, not merely a rule meeting a degenerate input.** The account was
`capital_of` and the claim `Chang'an capital of Tang Empire`; the picker answered `not_in_it` —
"the sentence does not say this at all" — at 1.0. The word *is* in the account. What the account
does not give is the **direction**, which the question has its own option for (`backwards`). So the
honest answer was `says_so` or `backwards`, and the reason a model gave neither is the question:
`_asking` asks "Does that sentence say that Chang'an capital of Tang Empire?" over a fragment that
names neither end, and read literally a fragment with no names says nothing about anybody.

**Which the design already answers:** the ends are not the text's to confirm. Which two things a
fact is about is handed into the reading and never read out of words — `write.py` says so in as many
words. The check exists against a claim nobody made *in the attributes* — the measured case is
`starts="1792"` invented from nothing — and asking the text to bear out the two names asks about the
one thing that was never in doubt.

**And the claim is taken from the code's syntax, which is fragile.** `claims_in` parses for
`a.set_word(b, ...)` with both ends bound to those two names. Measured, four ways of writing one
fact with one invented date:

    2 claims   a.set_founded(b, starts="1910")
    0 claims   world.relate(a, b, "founded", starts="1910")
    0 claims   founder, made = a, b; founder.set_founded(made, starts="1910")
    0 claims   for x in [b]: a.set_founded(x, starts="1910")

Three of the four make no claim as far as the check can see, so the invented date goes in unchecked.
The hole is the syntax dependence, not the parser.

**Where this goes, and it is the author's framing:** build the phrase and judge the result, not the
source. The world can render what it is about to hold — `Chang'an capital of Tang Empire` — and put
that beside what the host said; asked that way the answer here is plainly yes. And the claim should
come from the written record rather than from the shape of the lines, which is how success is
already judged (`write.typed_between`: "read from the record rather than from what the code appeared
to do"). The objection `check.py` raises against judging afterwards — deleting is the expensive
direction — is about committed writes by somebody else; these are the world's own, made under
`stating("world")`, and `Relation.retract` exists for exactly what the world concluded and no longer
believes.

## 2026-09-27 — the check is asked about what the record holds, as the phrase it amounts to

The author's two objections, and both were right.

**Why read the code at all — read the result.** `claims_in` parsed the engineer's source for
`a.set_word(b, ...)` with both ends bound to those names. One fact with one invented date, written
four ways: `a.set_founded(b, starts="1910")` gave two claims; `world.relate(a, b, "founded",
starts="1910")`, a renamed variable and a one-element loop gave **none**, so the date went in
unchecked three times out of four. The lines are one phrasing of many; the record holds one thing.
`check.claims_of` now reads the claims off the written links — the word, the two ends, and every
attribute on them — and `write.typed_between` was already doing exactly this for success: "read from
the record rather than from what the code appeared to do".

**And say it as a phrase.** The question was "Does that sentence say that Chang'an capital of Tang
Empire?" over the account `capital_of`, and the answer came back "the sentence does not say this at
all" at 1.0 — about a claim whose words are right there in the account. Read literally the picker was
not wrong: a fragment naming nobody says nothing about anybody. The question was wrong. So the claim
is rendered as what the record is about to hold — «Chang'an capital of Tang Empire» — and put beside
the account: *is that the same thing it says?* With the options saying what each means, including
that an account which does not say which way round is not against this one.

That also settles a thing the old question confused: **the ends are not the text's to confirm.**
Which two things a fact is about is handed into the reading and never read out of words. The check
exists against an attribute nobody said — the measured `starts="1792"` — and it still is: that case
is refused on the record now, and the link that carried it is taken back.

**Taking it back is safe here**, which is what the old argument for checking first denied. These
writes are the world's own, a moment old, marked `source="world"` by `stating("world")`, and nothing
outside has seen them. `Relation.retract` refuses them on a technicality — it guards on
`is_conclusion`, which means "has a basis", and the reading's writes go through the ordinary door
with none — so `write.take_back` takes back only a link whose every statement says `source="world"`
and leaves anything with a word from anybody else exactly as it stands.

**Measured, the same link, the same world:**

| | before | after |
|---|---|---|
| goes | 3 | **1** |
| verdicts | `not_in_it` ×3 at 1.0 | **`says_so`** |
| seconds | 42.4 | **16.6** |
| typed | 0 | **1** |

`Chang'an capital of Tang Empire (capital_of)`, with the bare link ended rather than erased — what
the host said is still there to read.

**One thing this changes and only a measurement will judge:** the date claim used to be asked about
the engineer's literal (`"since 2019"`) and is now asked about what the world holds (`2019-01-01`).
The option says "in those words or plainly the same time in other words", which is what it is for,
and the refusal rate and the confidences now land in `readings` where a false alarm will show.

## 2026-09-27 — a failure is written down with whose fault it was: technical or substantive

Asked for by the author, and the day had made the case twice over: an engineer "that answered
nothing" had been cut off mid-thought with its whole budget spent thinking, and a reading "that typed
nothing" had been refused by a check whose question could not be answered. Both were read as the
system not working. Counted together, failures say the reading is broken; told apart, they say which
part to fix.

**On the harness side, the failure that used to pass for a result.** A host session whose world
server did not answer has no tools at all — it says so in words and the batch was reported
"recorded". Measured that morning: five facts of six lost that way, because the session before had
closed a task and the reading it ran at the close held the server past the 30-second handshake.

- `host.ask` now reads the `init` event's `mcp_servers` and reports any that did not connect, keeps
  the `rate_limit_event` it sees, and marks a turn the CLI itself ended with an error.
- `host.answering(port)` waits for the world's health before a turn, which costs nothing when the
  world is free and saves the batch when it is reading.
- `run_fc.py` stops on a batch whose world was unreachable — a run with a batch missing is not a
  measurement — and writes every such event to `trouble.jsonl` beside the results.
- **A question that never reached the world is not a wrong answer.** It is kept out of `accuracy`
  and reported beside it as `never reached the world`. Counted as wrong it lowered the number for a
  reason that had nothing to do with the world, which is our plumbing wearing the world's name.

**On the reading side**, `readings` gains `trouble` and `whose_fault`. Technical: the check could not
be asked at all (and a check that cannot run lets the lines stand, so this failure left no other
trace anywhere), or nothing came back from the engineer. Substantive: not borne out by the words,
gave up, nothing was said about it. `catch_up --shape` prints the split and the wording underneath
it, so "not typed" can be asked *why* without opening a transcript.

## 2026-09-28 — an assignment where a word wanted a call, and the world it poisoned

The full slice was started and stopped at the third batch, on a number that looked wrong rather than
an error: 25 facts in **5 turns**. The batch was empty, and so would the sixteen after it have been.

**The chain, in one line each.** The host wrote `person.set_speaks = "Japanese"` — an assignment
where the word wanted a call. Growth took `set_speaks` for a new attribute, because a name the class
did not declare is taken on the fly rather than refused. The next write to that attribute asked
history to keep the old value, and the old value read off the class for that name was the **bound
setter itself**. `json.dumps` raised on a method. From then on every write to any `Person` in that
world raised: `start_task` answered "Object of type method is not JSON serializable", `describe_world`
and `run` timed out, and the host — correctly — reported the server broken and recorded nothing.

Three fixes, each where the thing actually went wrong:

- **The write is refused at the attribute door, where the reason can be said.** A name the class
  already answers with a call is not a value it can hold: `say it with the call, not an assignment:
  kukai.set_speaks(other) — speaks is a word for a link, and a link is written one at a time while
  the end reads back every one of them`. The same for anything else the class does (`describe`,
  `relate`): *that is something a Person does, not a value it holds*. A name nothing answers still
  grows, which is the behaviour that exists so a fact is never lost for want of an attribute.
- **Keeping the past is worth less than being able to write at all.** `history.record` keeps a value
  it cannot encode as what it looked like. Narrowly there and not in `store._encode`: a graph save
  that cannot encode a value must still raise and leave nothing behind, which is a guarantee with a
  test of its own — the first attempt at this broke it, and the test caught it.
- **A failed tool call is technical trouble and is written down.** `host.ask` collects every
  `tool_result` with `is_error` — "The operation timed out.", a raise inside the server — which is
  not the same thing as the world refusing something, since a refusal comes back as an ordinary
  result and is the world working. A batch turn with any of them stops the run; a question turn with
  any of them is kept out of `accuracy` and reported. The benign `rate_limit_event` with status
  "allowed" no longer goes in the log, because a log of things that are fine is not a log.

**What found it was not the logging.** It was a batch costing 5 turns where the others cost 16 and
25, i.e. the shape of the numbers rather than any error we had thought to catch. The logging is what
makes it visible next time: the same failure would now stop the run at that batch and name the call
that failed.

## 2026-09-28 — during a measured ingestion the world does not read at the close

Two attempts at the full slice died the same way, one batch apart: `finish_task` timed out and the
batch was lost. The first time a budget was put on the sentence reading. The second time the close
timed out anyway, because **the portraits pass had no budget** — forty-eight bare names in one batch,
each a walk down the class tree, and the two passes together were minutes. Both are bounded now by
one deadline for the whole close (`_left_of`), and measured on the world the second attempt left
behind, the close came back in **20.3s** where it had been minutes.

That is still not safe, and the reason is worth writing down: a budget can only stop a reading from
*starting*. One already-started reading has been measured at 45.9s, so the worst case still overruns
whatever tool timeout the host has, and a lost batch is a lost measurement.

**So a run turns it off.** `terraweaver.server --reading-at-close 0`, which `benchmarks/host.py`
passes by default: during a measured ingestion the world records what it is told and types nothing,
and the reading happens once afterwards with the world to itself
(`run_fc.py` stands the server down, runs `experiments/catch_up.py`, brings it back for the
questions). The close with reading off returns in **0.3s**.

Nothing is lost by this and the design says so in as many words: an untyped link holds its two things
and the words it was said in, the row saying nobody has read it stays open, and the reading is the
same pass whenever it runs. What a live host gets is unchanged — the default is still 20 seconds at
the close, which types the fact that was just said while the host is still there.
