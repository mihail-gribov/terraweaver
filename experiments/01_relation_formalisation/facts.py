"""The host's part: two things and a sentence, nine times over.

The host is a script here and not a model, on purpose. What is under test is the reading — given
two entities and a description of what joins them, produce the code that records the link — and a
model standing in for the host adds its own variance to every number. The words are the words a
host would say; how they were arrived at is somebody else's experiment.

Each fact puts its two things in through the doors a host uses (`identify` records a name nobody
here has yet) and says the fact with `world.relate(a, b, "...")`, which joins them at once and
leaves the link untyped. Nothing else is said: not the type, not which end is which, not how many
there may be, not when it began.

**Five of the nine say when.** A date in the words is the date the link began, and it is said the
way people say dates — a year, a year with a month, or nothing at all. Four say nothing, and for
those the link has no start; none of the nine says when anything *ended*, except #9, which says it
by saying when the next one began. An end nobody stated is no end: the link holds until further
notice, and inventing one is inventing a day.

Two of the nine measure something no single reading can show:

    #2 (Paris / France)    the word made for #1 must be found again, not made twice. This is the
                           whole of what "look before you define" is for: without it a world ends
                           up holding `ChairpersonOf` beside `DirectorOf`.
    #9 (Anna / Brightwork) a second employer after #4. Both are true, in their turn. If the type
                           came out as one-ever the world corrects the first — Acme becomes a
                           mistake — instead of ending its period where the next one begins.

`Organization` is deliberately absent: the base has no such class, so Acme is a `Thing`. A run that
quietly added the class would be measuring a world we did not open.
"""

FACTS = [
    ("Rome is the capital of Italy.",
     'a = Thing.identify(name="Rome")[0]\nb = Thing.identify(name="Italy")[0]'),
    ("Paris has been the capital of France since 1792.",
     'a = Thing.identify(name="Paris")[0]\nb = Thing.identify(name="France")[0]'),
    ("Masha has been married to Sasha since June 2015.",
     'a = Person.identify(full_name="Masha")[0]\nb = Person.identify(full_name="Sasha")[0]'),
    ("Anna Weber has worked at Acme since 2019.",
     'a = Person.identify(full_name="Anna Weber")[0]\nb = Thing.identify(name="Acme")[0]'),
    ("Kreuzberg is part of Berlin.",
     'a = Thing.identify(name="Kreuzberg")[0]\nb = Thing.identify(name="Berlin")[0]'),
    ("Boris and Vera are siblings.",
     'a = Person.identify(full_name="Boris")[0]\nb = Person.identify(full_name="Vera")[0]'),
    ("Thomas Kyd was born in London in 1558.",
     'a = Person.identify(full_name="Thomas Kyd")[0]\nb = Thing.identify(name="London")[0]'),
    ("A dog is a kind of mammal.",
     'a = Thing.identify(name="dog")[0]\nb = Thing.identify(name="mammal")[0]'),
    ("Anna Weber left Acme and has worked at Brightwork since March 2023.",
     'a = Person.identify(full_name="Anna Weber")[0]\nb = Thing.identify(name="Brightwork")[0]'),
]


def said(words: str, put: str) -> str:
    """The lines a host runs for one fact: put the two things in, then say the fact about them."""
    return f"{put}\nprint(world.relate(a, b, {words!r}))"
