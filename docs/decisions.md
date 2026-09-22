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
