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

TYPING_A_FACT = ("You place a fact in a record of relations. A relation joins two things and each end "
          "has a role. You answer with JSON and nothing else.")

A_FACT_SAID = """Two things are in a record of facts, and somebody has said how they are related.
Your task is to describe that relation, and nothing else.

    the first thing:   {a}   (a {a_is})
    the second thing:  {b}   (a {b_is})
    what was said:     {words}

{held}

**First: can this be typed as a relation?** The link is already in the record either way — two
things are joined and the words are on it, and nothing you say takes that away. The question is
only whether it can be given a type, and sometimes it cannot, because what was said is not
about two things at all:

    a value        a characteristic of one thing — "Anna is tall", "the salary is 60000".
                   "tall" is not a thing; it is what Anna is like, and a type made for it
                   invents a thing called "tall" and hangs somebody off it.
    a kind         one thing said to be OF a class — "Paris is a city", "Anna is a person".
                   "city" is a class, not another thing: this says what Paris IS.

Both ends were handed to you as things this record holds, not as words in a sentence, so "kind"
is right only when the second of them is one of the classes listed above. "wide receiver" and
"cornerback" are things; "plays the position of" joins two of them and is a link. The word "of"
in a sentence is not the test — `part_of`, `capital_of` and `mother_of` all have it.

Say `ill_typed` as "value" or "kind" when it is one of those, with `description` and nothing
else, and stop. The link stays; it stays untyped, which is a poor link and a real one, and the
writer is told which door would have served it better. Guessing a type for what has none is
worse than saying there is none.

Null when it can be typed, and then:

A relation in this record is four things and no others. Give them.

**use** — the name of one of the relations listed above, **only when this fact is that same
relation**. A second word for one idea answers for neither — and so does one word for two, which
is worse and cannot be taken apart afterwards: being born somewhere and dying somewhere are not
the same link because both join a person to a place. Null whenever the word you give below is
not already there, and then give the rest.

**the word** — `word`: what this kind of link is called. Four rules, and they are what keep one
idea under one word:

  1. Lower case, underscores between words, nothing else.
  2. It comes from the fact, never from what the ends are: "Thomas Kyd was born in the city of
     London" is `born_in`, not `person_of` and not `city_of`.
  3. **A name and a preposition, always, and exactly one preposition.** That is the shape:
     `capital_of`, `mother_of`, `born_in`, `died_in`, `worked_in`, `married_to`,
     `headquarters_in`. A bare noun (`chairperson`) or a bare verb (`plays`) reads as nothing
     between two names; two prepositions (`born_in_of`) is a word with two endings. Use the
     preposition the fact itself uses, and `of` when it uses none.
  4. Read it back between the two names, in the order the link runs, with the underscores as
     spaces. "Thomas Kyd born in London" is a sentence. If it is not one, the word is wrong or
     the ends are the wrong way round.

**the roles** — `subject_is` and `object_is`: what each END of the relation IS, as a short noun
phrase a thing could be checked against. "a city that serves as a capital", not "Paris"; "the
country whose capital it is", not "France". When both ends hold the same role, give the same
word — two siblings are both siblings, and that sameness is the whole of what symmetry is here,
so there is no separate thing to say about it. `also_called`: up to four other words this
relation is said with, so the next person who says it another way lands here instead of making
a second word for it.

**what may stand there** — `subject_class` and `object_class`: what sort of thing may fill each
role, chosen from the classes this record has:

{classes}

Widely, not narrowly. A role written tight turns every honest fact into an alarm: a religion's
followers are people as well as bodies, so an affiliation takes both and not just one. Give
"any" when anything may stand there, and say nothing a first example taught you that a second
would contradict. These are watched, not enforced — a fact whose ends do not fit is reported
and kept, because a fact refused goes somewhere nothing can find it.

**how many** — `one_object` is true when the first end may have only one of the second AT ONE
MOMENT; `one_subject` is the same the other way. About one moment, never about a lifetime:
somebody has one employer now and many over a life, so that is true. A parent has several
children at once, so for a parent that is false.

**what follows** — `implies`, a list of what becomes true *in addition* when a link of this kind
is written. Only these words, and empty is a common and honest answer:

    "transitive"   A to B and B to C makes A to C. A part of a part is part of the whole.
                   A mother of a mother is not a mother.
    "inherits"     what holds of the second end holds of the first by virtue of this link.
                   A dog is a kind of mammal, so what is true of mammals is true of dogs.
                   A wheel is part of a car and is not a car.
    "identity"     the two are one and the same thing under two names — "Bombay is Mumbai".
                   A part is not the whole and a member is not the group.

**what it is** — `description`: one sentence saying what this kind of relation is, for somebody
who has never seen it. About the kind of link, not about these two things.

Then, about this one fact rather than about the relation:

**which end is which** — `subject` and `object`, by the names given at the top. This is the
whole of the direction; nothing else decides it. Do not name anything that is not one of those
two things.

**when** — `starts`, if what was said says so, in the words it said it ("2019", "June 2019",
"since she moved"). Null when nothing was said about when. Do not work one out: a date nobody
said cannot be told apart, later, from one somebody knew.

**Whether the fact is true is not part of this task and must not affect any answer.** This
record holds what somebody said, including what contradicts common knowledge: "London is the
capital of France" is described exactly as "Paris is the capital of France" would be — same
relation, same roles, London in the capital's role.

JSON only, these keys and no others:
{{"ill_typed": null,
  "use": null,
  "word": "...",
  "subject_is": "...", "object_is": "...", "also_called": ["..."],
  "subject_class": "...", "object_class": "...",
  "one_object": true, "one_subject": true,
  "implies": [],
  "description": "...",
  "subject": "...", "object": "...", "starts": null}}"""


# --- the portrait door: a thing that came in as a bare name gets a class ---

PLACING_A_THING = ("You read an account of one thing and say what sort of thing it is, so a record can "
          "hold it under a class. You never say which thing it is — that is given. You never "
          "judge whether what is said is true.")

FORMALISE = """A record holds a thing and an account of it in words. Put the account into the
record's own terms: describe the class it belongs to, and write the code that fills this one in.

The thing: {name}   (bound in the code as `it`)
It is a kind of: {parent} — {parent_is}
{standing}

What was said about it:
{words}

**Everything comes out of those words and nothing else.** You know a great deal about the world
and none of it belongs here: a city is in a country, a sport has a ball, a person has a birthday
— and if the words did not say so, it is not here. An empty answer to either part is a common
and correct one, and the shortest account is often the whole of it: "Rome is a city" gives a
class and no code at all.

**Whether any of it is true is not part of this task and must not affect any answer.** A record
that holds "Rome is the capital of France" is written exactly as one holding the truth would be,
with France in the country's place. Correcting it would be inventing too — it would put in the
record something nobody said.

**class** — {class_ask}

**code** — the lines that fill this thing in, in the same language a person writing to this
record uses. `it` is already bound to the thing; never make it again, never rename it.

    it.population = 2800000                      a value the words gave
    it.describe("...")                           something no attribute can hold
    italy = Thing.get(name="Italy")              another thing, if this record has it
    it.set_capital_of(italy)                     what the words say this one is to that one

**The other end is looked up, never made.** `get` finds what is here and raises when it is not,
and that is the right end of it: which Italy is meant is the business of whoever said the words,
not yours. A record that held "British Broadcasting Corporation" got a second thing called "BBC"
this way, and nothing afterwards could tell them apart. If the line raises, the thing is not
here — say the rest and leave that out.

**Do not say again what is already said.** What this thing is already joined to:

{joined}

A link here for any of those is the same fact a second time, from the other end and under
another word — one record held `born_in` and `birthplace_of` for one birth. The words this
record has for links, to use rather than invent a second for the same idea:

{held}

**Only what these words say.** An account of a city knows its country and its famous dead; if
these words did not say it, it is not here.

Dates as `date(2019, 6, 1)`, and only where the words gave one; do not work one out.

JSON only, these two keys and no others:
{{"class": {class_shape}, "code": "..."}}"""

MAKE_ONE = """the record has no class for this thing, so describe one. Name the kind, not this
example: "Language", not "LanguageTheUserSpeaks"; "Sport", not "FinnishBatAndBallGame". The
next thing of this kind must fit it without being bent. It is a kind OF {parent}, so it is not
called {parent} — that name is taken by the wider one. Three or four attributes any of these
would have, not everything this one happens to have, each described in a sentence rather than
a label: "how many people live there", not "Population". One of these is known by its name and
the record adds that itself, so give no `name` attribute. `brief` is how the class appears in
the list every host reads before it writes: a clause, not a sentence."""

KEEP_ONE = """this thing is a {parent} and the record has the class already, so `class` is
null."""


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
