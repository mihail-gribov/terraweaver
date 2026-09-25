"""What the two of them are asked. The whole of the question, in one place.

Two questions and they are different kinds. **Is this one of the words the record already has** is
closed — a list of named options with a way out — and goes to the picker. **What are the lines that
record this link** is open and goes to the engineer.

What is asked for is **code**, not a description the world then renders. That is the argument this
experiment exists to settle: the relation door in the working code asks for data because the shape
of what is written is ours (`docs/relation-properties.md`, part seven), the entity door asks for a
class and the code to fill a thing in, and the entity door ran better. Code is asked for here for
the reason it is asked for there — it runs through the door a host's code runs through, so every
refusal the world makes of a host it makes of this, and a reading can express whatever a host could
rather than whatever a hand-written translator thought of.

**Every field is said to be required or not.** Told neither, the engineer fills what it happens to
think of: measured, the ends went unnamed, the roles came out as class names, and a date the fact
stated was left off the line. What must be there is listed as what must be there, what depends on
the words is listed as depending on them, and nothing is left to be inferred from an example.
"""

# --- the closed question: is the word already here? ---

NOTHING_FITS = "none of these"

NOTHING_FITS_IS = "no word here is this link — it is a kind of link this record has not got yet"

WHICH_WORD = "Which of these is the link between {a} and {b}?"


# --- the open question: the lines that record it ---

SYSTEM = ("You write the lines of Python that record one link in a record of facts. You are given "
          "the two things it is about, already found and bound to names, and the fact in the words "
          "it was said in. You answer with code and nothing else — no prose, no fences, no "
          "imports.")

ASK = """Two things in a record of facts, and a fact about the two of them. Write the lines that
record it.

    a = {a}   (a {a_is})
    b = {b}   (a {b_is})

    what was said:   {words}

Both are bound already. Never look either of them up again and never name them any other way:
which two things this is about is settled, and a line that fetches "Anna" afresh may fetch a
different Anna. `world` is bound too.

{class_ask}

## Writing the link — required

A word for a link gives both things a method for it:

    a.set_{{word}}(b)      a is the subject — the end the fact starts from
    b.set_{{word}}(a)      the other way round, when the fact runs that way

Which way it runs is the whole of the direction and nothing else decides it. "Rome is the capital of
Italy" makes Rome the subject of `capital_of`; "Italy's capital is Rome" is the same link, said from
the same end. Read your line back with the underscores as spaces — "Rome capital of Italy" is a
sentence, "Italy capital of Rome" is a false one.

## When it began — required if the words say, left out if they do not

    a.set_{{word}}(b, starts="1792")

The record reads these and only these: `'now'`, `'today'`, `'yesterday'`, `'3 years ago'`,
`'1792'`, `'March 2023'`, `'12 March 2023'`, `'2023-03-12'`, and any of them behind `'since '`,
`'before '` or `'after '` — `starts="since June 2015"` is the honest form of a date somebody gave
as a month.

Say exactly what the words said and no more precisely: a year said as a year stays a year. Nothing
is worked out from elsewhere — a date nobody said cannot be told apart, later, from one somebody
knew. Say nothing at all when the words say nothing: a link with no start is a true record of a
fact that came without one.

## When it ended — only if the words say it ended

    a.set_{{word}}(b, starts="2019", until="March 2023")

**Otherwise there is no end.** A link holds from its start until something says otherwise, and
that is the normal case: do not pass `until=`, do not end anything, do not tidy anything up.

If what was said is that one thing replaced another — she left one employer for another — record
the new one with its start. Whether the earlier one ends there is the type's own rule and the
record applies it; your line says the fact, not the consequence.

## Everything else

**Whether the fact is true is not part of this task and must not change a single line.** This record
holds what somebody said, including what contradicts common knowledge: "London is the capital of
France" is recorded exactly as "Paris is the capital of France" would be.

Nothing is recorded but what the words say. No second link, no attribute nobody mentioned, no
account of either thing, no tidying up.

{held}

The classes this record has, so a line does not name one it has not got:

{classes}

Answer with the lines and nothing else."""


# Two ways the last block can read, and the difference is one word: define, or do not.
USE_ONE = """## The word is already here: `{word}` — {reads}

Use it and define nothing. A second word for one idea answers for neither, and the links written
under one do not meet the links written under the other."""

MAKE_ONE = """## This record has no word for this kind of link, so declare one first

On its own line, and then write the link:

    world.define_relation("capital_of", "a city that is the seat of a country's government",
                          nature="related_to", cardinality="many-to-one",
                          subject_is="a city that serves as a capital",
                          object_is="the country whose capital it is")
    a.set_capital_of(b, starts="1792")

**Required — every one of these, on every definition.** The call is refused without them, and a
type that went in without one is wrong for every link ever written under it:

    the word          lower case, underscores, and **a name with exactly one preposition** —
                      `capital_of`, `born_in`, `married_to`, `works_at`, `part_of`. It comes from
                      the fact and never from what the two things are: "Thomas Kyd was born in
                      London" is `born_in`, not `person_of` and not `city_of`. A bare noun
                      (`chairperson`) or a bare verb (`plays`) reads as nothing between two names;
                      two prepositions (`born_in_of`) is a word with two endings.
    the description   one sentence saying what this **kind** of link is, for somebody who has never
                      seen one. About the kind, not about these two things. A few words is refused.
    nature            one of related_to / part_of / kind_of / same_as / derived_from.
    cardinality       how many may hold **at one moment**, and it is the whole of what decides
                      behaviour. "many-to-one": this thing has one of those at a time — one
                      employer, one spouse, one capital — and a new one ends the standing one where
                      it begins, both staying in the record. "one-to-many": the other end is the
                      limited one — an organisation has one chair at a time, and many people chair
                      many things. "many-to-many": neither is limited and they accumulate — a
                      sibling, a part of a whole, a kind of thing. "one-to-one": both ends.

                      Say it per end and say it about a moment. How many there were **ever** is not
                      a question about a type: a record only ever accumulates, and nothing in it is
                      one forever. Limit an end that is not limited and a fact about somebody else
                      is rewritten — declare one employee per employer and the next person hired
                      ends the last one's job.
    subject_is        what each END IS in a link of this kind, as a short noun phrase a thing could
    object_is         be checked against: "a city that serves as a capital", not "Rome", and not
                      "a place". **Never the class** — `a person`, `a place`, `a thing` are the
                      classes, which are listed below and which the record already knows; a role
                      that repeats one says nothing about the link and makes the type uncheckable.
                      Where both ends hold the same role, say the same word: two siblings are both
                      siblings, and that is the whole of what symmetry is here. Wide rather than
                      tight: a role written tight turns every honest fact into an alarm.

**Fill in if the words support it, leave out otherwise:**

    subject=          which classes may stand at each end, from the classes listed below, as a
    object=           class or a list of them — `subject=Person`, `object=[Person, Thing]`. Leave
                      both out when anything may stand there, and leave them out rather than name a
                      side from this one example: a side named after the first fact refuses the
                      second, and the answer to that refusal is a second type for one idea."""
