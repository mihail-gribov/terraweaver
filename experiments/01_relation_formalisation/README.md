# 01 — formalising a relation from the host's words

**The question.** Two entities are in the record and somebody has said what joins them, in words.
Produce the formal representation of that relation: find the word for it if the record already has
one, declare it if it has not, and write the link. The answer is asked for as **code**, and the
code runs through the door a host's code runs through.

    a = Thing.identify(name="Rome")[0]
    b = Thing.identify(name="Italy")[0]
    world.relate(a, b, "Rome is the capital of Italy.")     # the host, at once, untyped

    ...                                                     # the reading, afterwards

    world.define_relation("capital_of", "a city that is the seat of a country's government",
                          nature="related_to", cardinality="many-to-one",
                          subject_is="a city that serves as a capital",
                          object_is="the country whose capital it is")
    a.set_capital_of(b)

## What this runs against

The whole system, not a model of it: the real `WorldRuntime`, the real store, the real
`define_relation`, the real sandbox, the real refusals. What is written in the experiment is the
**piece under test** — the reading — and nothing else.

The world is the **base**: `Thing`, `Related`, `Person`, `AIAgent`, `Event`, plus `Task`, which is
the world's own record of work. No fixture. A fixture holds fifteen classes and a `Kin` with
fourteen labels, and a run against one measures a vocabulary somebody wrote by hand. `Organization`
is therefore absent, so Acme is a `Thing` — which is the honest state of a world that has not met a
company yet.

## The steps

    look    Is there already a word for this kind of link? A closed question over what the record
            holds, narrowed by the classes at the two ends, with "none of these" among the options,
            put to the **picker**. Nothing is defined and nothing is named twice. This is the step
            that makes a vocabulary converge — without it a world holds `ChairpersonOf` beside
            `DirectorOf`, each answering for half of one idea.

    make    Only what the look could not place, and only then: one open call to the **engineer**
            for the lines that declare the relation and write the link.

    run     Through `runtime.run`, with `a` and `b` bound before the code starts. Which two things
            this is about is never read out of an answer — identity is handed over here as
            everywhere else in this world. It fails, the world says what it would say to a host,
            and that goes back to whoever wrote the line. Three goes.

    end     The bare link stops where the typed one begins. Not erased: the host's words are the
            only account of this link the world did not write itself.

Not read and not guessed anywhere: **which two things**. Not asked anywhere: **whether the fact is
true** — a record that holds "London is the capital of France" describes it exactly as the truth.

## Files

    world.py     a base world opened in this process, and the two readers put on it
    facts.py     the host's part: nine facts, each as two things and a sentence
    asking.py    what the two readers are asked — the closed question and the open one
    reading.py   the piece under test
    run.py       the run, the readout, and the trace written to results/
    earlier/     the sketches this experiment grew out of, kept as they were

## Running it

    .venv/bin/python experiments/01_relation_formalisation/run.py               all nine facts
    .venv/bin/python experiments/01_relation_formalisation/run.py --facts 2     the first two
    .venv/bin/python experiments/01_relation_formalisation/run.py --say-only    no model is called
    .venv/bin/python experiments/01_relation_formalisation/run.py --keep var/exp01

Fresh world every time unless `--keep`: a run against a world that already holds the words measures
the look and not the making, and the two have to be told apart.

## What the nine facts are for

Seven of them ask one question each — can this be read at all, and into what. Two ask something no
single reading can answer:

- **#2 Paris / France.** The word made for #1 must be *found*, not made a second time.
- **#9 Anna / Brightwork**, after #4 put her at Acme. Both employers are true, in their turn. This
  is the one fact in the set whose answer depends on what the type says about *how many at a
  moment*, and it is aimed at two things the working code already gets wrong:

  - `sentences.formalise` passes `over_time=False` on every type it declares
    (`terraweaver/sentences.py:311`), so a reader's honest "one employer at a moment" is stored in
    the slot that means *one ever* (`authoring.py:368`).
  - and `_correct`, the branch *one ever* takes, only prints a note
    (`relations.py:965`) — its docstring says the earlier link is "marked as no longer held" and
    nothing marks it. So two employers stand side by side and "who now" has two answers.

  This experiment asks the engineer for `over_time` directly, in the words that say what it does, so
  the run separates *the reader answered badly* from *the world stored a good answer in the wrong
  slot*.

## What is being settled

1. **Does the look hold the vocabulary together?** Measured as: words defined vs words joined.
2. **Code or data?** The relation door in the working code asks for data and renders the call
   itself, on the argument that the shape of what is written is ours
   (`docs/archive/relation-properties.md`, part seven). The entity door asks for a class and the code to
   fill a thing in, and it ran better. This asks for code on the relation door, against the same
   world, so the argument is settled by measurement rather than by assertion.
3. **How much of a relation can be read out of one sentence?** The roles as role words and not as
   class names, the direction, the date, and how many hold at a moment.

## Where it came from

`earlier/` is every iteration before this one, moved here whole rather than summarised:

    relation.py            the settled type: six fields, and what is deliberately absent —
                           no kind (the word is read off the roles), no symmetric (it is the
                           roles being the same word), no over_time, no cardinality
    formalise.py           the procedure — look, then describe only if nothing fits
    describe_to_code.py    the ask-for-code question, and the argument for it
    try_formalise.py       eight facts in a row against stand-in classes, to watch a vocabulary
                           converge
    one_idea_or_two.py     a cheap match offers, a closed reader decides — 6/7, and the one it
                           would not call was the honest abstention
    say.py, roles.py,      the two doors, and the record/image division: what was said is stored,
    place_the_fact.py      what follows is worked out and never kept
    relation_class.py      superseded by relation.py

Measured there, on stand-in classes: part/whole gives `transitive`; dog/mammal gives `transitive`
and `inherits`; employment gives one employer at a moment; "London is the capital of France" is
placed exactly as a true one would be. **`identity` missed twice running** on "Bombay is Mumbai".

## Runs

Three, on 2026-09-25, each after fixing what the last exposed. A fresh base world every time,
Nemotron 3 Nano 30B as the engineer, Jev as the picker, 1.8 minutes a run.

    run          typed      words made   joined   left bare
    08:29        8 of 9     7            1        the 2019 employment
    08:35        8 of 9     6            2        "a dog is a kind of mammal"
    08:38        9 of 9     7            2        none
    11:23        8 of 9     6            2        the marriage — the reader returned nothing
    12:23        7 of 9     5            2        two readings returned nothing
    12:28        9 of 9     7            2        none — with room to think
    13:03        9 of 9     7            2        none — with the gate on what is written

**End state: nine facts said in words, nine links typed, seven words, nothing bare.** `capital_of`
was made once and joined twice. The employment handover is dated from the words:

    works_at   Anna Weber works at Brightwork     from 2023-03-01
               Anna Weber works at Acme           from 2019-01-01, ended 2023-03-01

Asked who she works for now, the record says Brightwork; asked about 2020, it says Acme. Both
periods hold, neither was invented, and nothing was corrected.

### What was broken, and what fixing it cost

**The world could not read a month by name.** `starts="March 2023"` was refused — the record took
`'in 2006'`, `'3 years ago'`, `'2006-01-01'`, and not the commonest way anybody says a date. What
the engineer did next is what makes this worth the entry: it degraded the date to `"in 2023"`, which
the record *did* take, and the fact went in as **1 January 2023**. A date refused costs a line; a
date degraded costs the fact, because nothing afterwards can tell it from one somebody knew.
`timeutil` reads a named month now (`March 2023`, `12 March 2023`, `march 12 2023`), a month with no
day being the first of it — exactly what `'2006-03'` and `'2006'` already came to.

**The reading went newest-first.** `sentences.unread` returns links in whatever order the tables
give them, and the 2023 employment was read before the 2019 one. Everything the world does with a
second fact about the same two ends assumes the second one arrived second: the line it offers when
it refuses — *end that one where this one begins* — is written for a fact that starts later than
what is standing. Against a 2023 employment, the 2019 one had no honest line at all, and that was
the failure in run one. The reading is sorted by when the host said it.

**A trace without the record's answer is not a trace.** Run one reported "nothing came back" about a
line the world had refused for a reason nobody could see, and the reason had to be found by writing
the line again by hand. Every go now keeps what the record answered, and a reader that returns
nothing says which kind of nothing it was.

### What the reader gets right

Asked in the words that say what it does, **`over_time` comes back right**: True for an employer and
a spouse, False for a birthplace, a part, a sibling, a kind. The working code does not ask — it
passes `over_time=False` on every type it declares (`terraweaver/sentences.py:311`) — so this
settles where that defect lives. The reader is not the problem.

Dates land where the words gave them and nowhere else: four of the nine links have no start, which
is what the facts said. No `until=` was ever written, and none should have been.

### Fixed because this run measured it: `over_time` is gone

**`over_time=True` overrode the cardinality on both sides, and it fired people.** The engineer said
`works_at` is `many-to-one` — many employees per employer — and the world stored *one subject at a
time* as well, because `one_subject_ever = over_time or one_subject`. In the world the 08:38 run left
behind:

    boris.set_works_at(brightwork, starts="2024")
    → Brightwork had Anna Weber works at Brightwork, and WorksAt holds one at a time,
      so that one ends 2024-01-01 — the date this one starts.

Boris being hired **fired Anna** — a correct answer from the reader, destroyed by the mapping, and a
fact about a third party rewritten with nothing but a hint to say so. `over_time` is withdrawn:
cardinality is the only thing that says how many, it says it per end and about one moment, and "one
ever" is not a category (`docs/decisions.md`, 2026-09-25). Re-measured in the 11:23 world, the same
line leaves Anna's job exactly where it was, and her Acme period still ends 2023-03-01.

The same change made the **undated** case honest. A link nobody dated used to arrive at the check
looking like one dated today, so the standing one was ended today, *exactly* — a day nobody said.
It is now ended *some time before now* (`until_is = before`): not holding today, and *nobody knows*
about 2020, which is the truth.

### A reader that returns nothing was cut off mid-thought

Two readings of nine came back empty in the 12:23 run, and "the reader answered with nothing at all"
points at the wrong thing. Measured on the question it failed:

    room= 3000   finish='length'   completion_tokens=3000   content=0 chars
    room= 8000   finish='stop'     completion_tokens=2845   right answer

A reasoning model thinks inside the same budget it answers in, so a budget that is generous for the
answer is a cliff for the pair. `outside.Nemotron` defaulted to 3000 — a silent cliff under every
door of the world, not only this one. The default is 8000 now, this experiment asks with 12000, and
a truncated answer **says so** instead of returning an empty string: every caller treated nothing as
"the reader had nothing to say", which is the one reading it was not. With room, 9 of 9.

### What is still wrong

### Fixed the same day: a claim is checked before it is written, not deleted after

The 12:28 run read "Rome is the capital of Italy" — no date in it — and wrote
`a.set_capital_of(b, starts="1792")`. *First read here as a date carried over from the Paris fact;
corrected:* it was the question's own example, `a.set_capital_of(b, starts="1792")`, which for Rome is
the right line whole and was copied whole. The examples are placeholders now (`docs/decisions.md`,
"an example is copied, not read"); the check stays, because a claim the sentence does not bear out
should never be written whatever planted it.

`checking.py` puts every claim the lines make to the **picker**, one closed question each, in one
call — **before the lines run**. The 13:03 run:

    Rome is the capital of Italy.
        | a.set_capital_of(b, starts="1792")
        ✓ link: capital_of  says_so (0.99)
        ✗ starts: 1792  not_in_it (1.0)
        > Not written, because the sentence does not bear it out … Leave it out; a link with no
        > start is a true record of a fact that came without one.
        | a.set_capital_of(b)
        ✓ link: capital_of  says_so (0.99)
        done

**17 claims put to the picker over nine facts, one refused, and it was the right one.** Every date
that was really in a sentence passed — Paris 1792 at 1.0, "since June 2015" at 0.99, 2019 at 1.0,
1558 at 0.94, "since March 2023" at 1.0 — and every link claim came back borne out at 0.92 to 1.0.
`Rome capital of Italy` holds no start, which is what the sentence gave.

Checked before, not after, for a reason: a check that reads the record afterwards has to **delete**
what it finds, and by then the write is committed, whoever holds the instance holds a stale one, and
a link taken back leaves the fact it came from unrecorded. Asked first, a claim nobody made is simply
never added — the lines go back to whoever wrote them, through the loop a refusal already uses.

What is asked is **every attribute that came from the sentence** — the link, which way round, when it
began and ended, and anything else the line writes onto it as a literal — and nothing else. Those are
the only places a claim nobody made can get in, because they are the only places filled from the
text; the rest of the line is the world's own structure. And the doubt goes to the line, not against
it: below 0.6 the verdict is not acted on, because a false alarm costs a go out of three and the fact
with it.

### What is still wrong

**A wrong cardinality now limits the wrong end.** With the two ends no longer forced together, they
are also no longer forced right: in the 11:23 run `born_in` came back `one-to-many`, which says
**London has one person born in it at a time** — so a second birth in London would end the first.
The direction was hidden while `over_time` limited both ends regardless; the reader has to be asked
about the two ends separately, in the words of the things in front of it, rather than handed four
hyphenated names to choose between.

**A symmetric fact is written twice**, in two of the three runs that reached it. "Boris and Vera are siblings"
came back as `a.set_sibling_of(b)` *and* `b.set_sibling_of(a)` — two links for one fact, though the
question says no second link. Symmetry is the two roles being the same word, which this type has, so
the second line is not a second fact and the world should be the one to know it.

**A coarse date is stored as an exact day.** `starts="1792"` lands as 1 January 1792 marked
`exact`; only `"since June 2015"`, which one run wrote and another did not, lands as `after`
2015-06-01. A year said as a year is a year, and the record has the machinery to say so — the side
is read before the date is. Either `told()` marks a year- or month-only date as `after` its first
moment, or every reader has to remember the word `since`, and one of those is a rule and the other
is a hope.

**Roles still come out as class names**, though less than before the prompt forbade it: `born_in` is
`a person who was born ↔ a place of birth` — the second is a role, the first is the class with a
clause on it. The roles exist so a link written backwards can be told from one written right, and a
role that repeats the class cannot do that.

**A role phrase becomes an identifier.** `subject_is="a city that serves as a capital"` is stored as
`a_city_that_serves_as_a_capital`, because `define_relation` runs `_clean(...).lower()` over it. It
is a noun phrase for a reader to check a thing against, not a name — the underscores are the
world's, and they make every later reading read a phrase that nobody wrote.
