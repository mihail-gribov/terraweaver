"""Everything this world says to a model outside it, in one place.

The prompts were in five modules, next to the code that sent them, which reads well and hides
the one thing worth seeing: **what does this world ask, altogether?** Three defects in a single
day were the world telling a model something other than what was so — an example naming a class
this record has not got, a promise that a missing word would be made, a counterexample showing
the very call it forbade — and not one of them is visible from inside the module that holds it.

So they live here, each said for out loud: who asks it, when, and what it is for. A prompt for a
door that no longer exists is then a line in this file with nothing importing it, which is a
thing a person can see.

Written as text, formatted by the caller. Nothing here decides anything.
"""


# --- the sentence door: a fact said in words becomes a link, at the close ---
#
# Asked by `terraweaver.formalise`, measured in experiments/01_relation_formalisation. Two parties,
# and the kind of question decides which: the picker answers "is this one of the words the record
# already has" and "does the sentence say this"; the engineer answers "what are the lines that
# record it". What comes back from the engineer is code, run through the door a host's code runs
# through, so every refusal the world makes of a host it makes of this too.

# The picker, first: is there already a word for this kind of link? A way out is always among the
# options — with none, the least bad word is taken, which is how "Amy Winehouse died in Camden
# Town" once went in as `born_in`.
WHICH_WORD = "Which of these is the link between {a} and {b}?"
NONE_OF_THESE = "none of these"
NONE_OF_THESE_IS = "no word here is this link — it is a kind of link this record has not got yet"

# The engineer: the lines that record one fact.
WRITING_A_LINK = ("You write the lines of Python that record one link in a record of facts. You are given "
          "the two things it is about, already found and bound to names, and the fact in the words "
          "it was said in. You answer with code and nothing else — no prose, no fences, no "
          "imports.")

A_LINK_SAID = """Two things in a record of facts, and a fact about the two of them. Write the lines that
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

    a.set_{{word}}(b, starts="<the time the words give, in their words>")

The record reads these and only these: `'now'`, `'today'`, `'yesterday'`, `'3 years ago'`,
`'1792'`, `'March 2023'`, `'12 March 2023'`, `'2023-03-12'`, and any of them behind `'since '`,
`'before '` or `'after '` — `starts="since June 2015"` is the honest form of a date somebody gave
as a month.

Say exactly what the words said and no more precisely: a year said as a year stays a year. Nothing
is worked out from elsewhere — a date nobody said cannot be told apart, later, from one somebody
knew. Say nothing at all when the words say nothing: a link with no start is a true record of a
fact that came without one.

## When it ended — only if the words say it ended

    a.set_{{word}}(b, starts="<when it began>", until="<when it ended>")

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


# **An example is copied, not read.** The definition's example used to be `capital_of` with
# `starts="1792"`, and for "Rome is the capital of Italy" that is the right line whole — so the
# engineer wrote it whole, date and all, three goes running, while the check refused it three times.
# Examples here name a word no fact in sight is likely to need, and every date is a placeholder the
# record refuses if it arrives unfilled: copied, it fails loudly instead of landing quietly.
#
# The last block of A_LINK_SAID reads one of two ways, and the difference is one word: define, or do
# not. Every field of a definition is said to be required or not; told neither, the engineer fills
# what it happens to think of.
THE_WORD_IS_HERE = """## The word is already here: `{word}` — {reads}

Use it and define nothing. A second word for one idea answers for neither, and the links written
under one do not meet the links written under the other."""

NO_WORD_YET = """## This record has no word for this kind of link, so declare one first

On its own line, and then write the link:

    world.define_relation("mayor_of", "a person who leads the government of a city",
                          cardinality="one-to-many",
                          subject_is="a person who leads a city's government",
                          object_is="the city they lead")
    a.set_mayor_of(b)

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

# What goes back to the engineer when the lines did not do what they were for.
WRITE_AGAIN = """{asked}

You wrote this, and the record answered:

{code}

{answer}

Write the lines that still have to run — the ones that finished are done and must not be sent
again. Nothing new is invented: only what the words above say."""

JOINED_NOTHING = """{asked}

You wrote this, and it ran without an error and joined nothing:

{code}

{answer}

The two things are still unjoined. Write the lines that record the link between `a` and `b`."""

# The picker again, before the lines run: does the sentence say what the lines claim? Every
# attribute that came from the text is asked about, and only those — the rest of a line is the
# world's own structure, which is not read out of a sentence and cannot be wrong about one.
IS_IT_SAID = """Somebody said this, and it is the only account of this fact there is:

    {words}

Whether it is true of the world is not asked. What is asked is only whether that sentence says the
thing below."""

NOT_BORNE_OUT = """Not written, because the sentence does not bear it out:

    {what}

Write the lines again with only what the sentence says. Everything a link says about the fact comes
from the sentence and from nowhere else: not from what you know about these two things, not from
what is usually true of them. A fact with no date in it is recorded without one, which is what the
record means by no date."""


# --- the portrait door: a thing that came in as a bare name gets a class ---

PLACING_A_THING = ("You read an account of one thing and say what sort of thing it is, so a record can "
          "hold it under a class. You never say which thing it is — that is given. You never "
          "judge whether what is said is true.")

CLASS_FOR_A_THING = """A record holds a thing and everything known about it. None of the classes
it has fits, so describe the one this thing belongs to.

The thing: {name}
It is a kind of: {parent} — {parent_is}

What is known about it:
{words}

**Whether any of it is true is not part of this task and must not affect the answer.** A record
that holds "Rome is the capital of France" is a record of what somebody said, and the class of
Rome is the same either way.

**class** — {class_ask}

JSON only, this one key and no other:
{{"class": {class_shape}}}"""

MAKE_ONE = """the record has no class for this thing, so describe one. Name the kind, not this
example: "Language", not "LanguageTheUserSpeaks"; "Sport", not "FinnishBatAndBallGame". The
next thing of this kind must fit it without being bent. It is a kind OF {parent}, so it is not
called {parent} — that name is taken by the wider one. Three or four attributes any of these
would have, not everything this one happens to have, each described in a sentence rather than
a label: "how many people live there", not "Population". One of these is known by its name and
the record adds that itself, so give no `name` attribute. `brief` is how the class appears in
the list every host reads before it writes: a clause, not a sentence."""

# --- the offline passes: what the world writes for itself when nothing waits ---

WRITING = ("You write the one line a record puts to whoever records a thing of this kind and "
           "says nothing about it. You write what somebody would have to say for one of these "
           "to be known again. You answer with JSON only.")

WRITE_ONE = """A record holds a class and has nothing to ask about one of these.

The class: {name} — {description}
It is a kind of: {parent}, which asks: {inherited}
The attributes it has: {attributes}

What has been said about the {count} of them here:
{said}

Write the line the record will put after the word "say". It asks for what makes one of these
known again and tells two of them apart — for a person that is the full name and who they are
to the user; for a place, what sort of place and where.

About the kind, never about these ones: not "the Finnish bat-and-ball game" but "what sort of
sport it is and where it is played". Someone recording the next one of these has not met any of
the ones above.

Shorter than a sentence and a half. It is read after "say", so it needs no verb of its own, and
no second person.

JSON only: {{"what_to_say": "..."}}"""


# --- naming the ends of a link, and reading whether one runs the right way ---

NAMER_IS = ("You name the parts of a link type in a record of facts. A link has a subject — the "
            "end it starts from — and an object — the end it leads to. You answer with JSON and "
            "nothing else.")

ASK_NAMES = """Link type: {kind}
What it is: {type_is}
Written like: {examples}

Name what each end IS, as a short noun phrase a thing could be checked against — "a city that
serves as a capital", not "the capital". Keep it wide enough for everything that honestly
belongs there: a religion's followers include people as well as organisations. A role written
too tightly turns every honest link into a false alarm.

Then: does the word '{kind}' tell a reader which end it starts from? `capital_of` does — "a
capital_of b" reads "a is b's capital". `author` does not: it could start from the writer or
from the book. Give a word that would, or the same word if it already does. It must be a name
for the link type, not for one of its ends.

JSON only:
{{"subject_is": "...", "object_is": "...", "clear_name": "..."}}"""

ENDS_FRAME = """One link out of a record of links. A link has two ends and they are not
interchangeable: the subject is the end it starts from, the object is the end it leads to.

    relation:    {kind} — {type_is}
    subject is:  {subject_is}
    object is:   {object_is}

    subject:  {s_name} (a {s_class}){s_said}
    object:   {o_name} (a {o_class}){o_said}
    {link_said}

Judge only whether each end holds the right KIND of thing for its role. Whether the claim is
TRUE is not asked and must not affect the answer: this record deliberately holds claims that
contradict common knowledge and they are meant to be kept. With subject "a city that is a
capital" and object "the country whose capital it is", the pair Rome / Japan is correct in kind
even though Rome is not Japan's capital."""
