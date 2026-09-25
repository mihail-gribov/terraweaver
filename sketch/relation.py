"""A relation as a class: everything a relation is, and everything it deliberately is not.

The mechanism, end to end:

    the host wants to say "Sasha is Masha's husband"
      -> LOOK: is there already a relation with these roles, or near enough?
           yes -> use it. Nothing is defined, nothing is named twice.
           no  -> DESCRIBE it: the roles and the properties below. The host can do this
                  itself, because it is given what the world already holds; or it is asked
                  of a reader whose whole task that is.
                  -> the description becomes a class that inherits Relation
                  -> the class is registered, and from then on step one finds it

Looking first is not tidiness. In a measured run one recorder wrote `ChairpersonOf` and
`DirectorOf` (0.86 alike) and `CreatedBy` beside `FoundedBy` — two words for one idea, and a
world that holds both answers for neither. The look is what makes a vocabulary converge.


## What is in it

    subject_is / object_is        what each END IS in this link: capital ↔ country,
                                  wife ↔ husband, part ↔ whole. This is what a class cannot
                                  say — a car is not barred from driving because it is a Car
                                  but because nothing that drives is a vehicle — and it is
                                  what makes a link written backwards visible as a wrong fact
                                  rather than a type mismatch. An outside reader told the roles
                                  found 13 backwards links in 115; told only the type's name
                                  and description it found none.

    subject_class / object_class  what may stand at each end, from the classes the world
                                  holds. "" is open, and open is the honest answer while the
                                  first example is all anybody has seen: a side named after it
                                  refuses the second, and the answer to that refusal is a
                                  second type for one idea. Watched, never enforced.

    one_object / one_subject      how many hold AT A MOMENT. Not over a life.

    implies                       what becomes true in addition: transitive · inherits ·
                                  identity. Only these words, and empty is a common and honest
                                  answer.

    descriptions                  what this kind of link is, in prose, by whoever said it —
                                  a list, like everything else described in this world.


## What is not in it, and why

**No `kind`.** The word is read off the roles: a capital is `capital_of`, a wife is `wife_of`.
A type is not a name somebody chose; it is the two roles, and the name follows.

**No `symmetric`.** It is the roles being the same word. Two siblings are both siblings; a wife
and a husband are not the same word, so that link is not symmetric even though it joins two
people and reads from both ends.

**No `over_time`.** A period belongs to the statement, not to the type. It was a field once and
it wiped out the cardinality standing next to it: all four cardinalities with `over_time=True`
came to the same thing.

**No cardinality.** "How many were there ever" is not a question about a type: history always
accumulates, because the record is only ever added to. And "one ever" is not a category —
nothing in a record is one forever. A birthplace changes in the record not because anybody
moved but because sources disagree, somebody was wrong, an opinion was sharpened. "Forever" is
a property of the world, not of the record.

**No nature.** `part_of`/`kind_of`/`same_as`/`derived_from` was one word carrying a set of
inference rules, which is `implies` and which one word cannot hold. Deriving it from
transitivity was rubbish left from an earlier iteration.


## How a later telling meets an earlier one

There is no "superseding" as an action of its own:

    **Everything has a period. One at a moment means the periods do not overlap.**

A link arrives with start T: the world finds what held at T and ends it there. That is all.

Correction ("I was told wrong") and handover ("he changed jobs") are the same record and the
world does not tell them apart — two statements with their own periods, one of which holds at
any given moment. What happened in life is not something the record has to know. The only
difference is what closes the earlier period:

    the new start is named   ->  the earlier ends exactly there          until_is = exact
    no start was named       ->  the earlier ended some time before now  until_is = before
                                 — when, nobody said, and the world does not invent it


## The words

One word per end, out of that end's own role, and each is a name and exactly one preposition:

    rome.capital_of   -> Italy        italy.country_of   -> Rome
    masha.wife_of     -> Sasha        sasha.husband_of   -> Masha
    kyd.born_in       -> London       london.birthplace_of -> [Kyd]

A bare noun (`chairperson`) or a bare verb (`plays`) reads as nothing between two names; two
prepositions (`born_in_of`) is a word with two endings. Built from a type's word plus a tail it
gave `capital_of_of`, because the tail was already there.

Reading gives a value where only one can hold at a moment and a list where several can. Writing
is a call and never an assignment: writing is always one link, reading a plural end is every
link there is, and `=` would claim replacement over an addition.


## Measured, including what missed

On five sentences: part/whole gives `transitive`; dog/mammal gives `transitive` and `inherits`;
employment gives one employer at a moment; "London is the capital of France" is placed exactly
as a true one would be. **`identity` missed twice running** on "Bombay is Mumbai", giving
`transitive` instead. And "Princess Alice was an Anglican" got `inherits`, which is arguable.
Both misses are in the inference rules — the newest part of this.
"""

from dataclasses import dataclass

# Every word for an end is a name and exactly one preposition — `capital_of`, `born_in`,
# `married_to`. A bare noun or a bare verb reads as nothing between two names.
PREPOSITIONS = ("of", "in", "at", "for", "to", "from", "on", "with", "by", "into", "about")

# What may follow from a link, beyond the link itself. Only these, and empty is common.
IMPLICATIONS = ("transitive", "inherits", "identity")


class Relation:
    """What every relation is. A class body says these and nothing else."""

    subject_is: str = ""          # what the subject IS here: "capital", "wife", "part"
    object_is: str = ""           # and the other end: "country", "husband", "whole"
    subject_class: tuple = ()     # the classes themselves, not their names: a name is a string
    object_class: tuple = ()      #   nobody can check. Several, because a side often takes
                                  #   several — an employer is an organisation or a person, a
                                  #   religion's followers are people and bodies both. Empty is
                                  #   open, and open is honest while one example is all there is
    one_object: bool = False      # at a moment, the subject has one object — not one ever
    one_subject: bool = False     # at a moment, the object has one subject
    implies: tuple = ()           # transitive · inherits · identity

    @classmethod
    def symmetric(cls) -> bool:
        """Not declared: it is the roles being the same word.

        Two siblings are both siblings. A wife and a husband are not the same word, so that
        link is not symmetric even though it joins two people and reads from both ends.
        """
        return bool(cls.object_is) and _plain(cls.subject_is) == _plain(cls.object_is)

    @classmethod
    def transitive(cls) -> bool:
        return "transitive" in cls.implies

    # A word for each end, out of that end's own role. The city is the capital of the country
    # and the country is the country of the capital, so `rome.capital_of` and `italy.country_of`
    # each read as what that end IS — the one thing a class cannot say and a role can. Built
    # from a type's word plus a tail it gave `capital_of_of`, because the tail was there already.
    @classmethod
    def word(cls) -> str:
        """What the subject's end is called: `capital_of`, `wife_of`, `born_in`."""
        return _as_a_word(cls.subject_is)

    @classmethod
    def word_back(cls) -> str:
        """And the object's end, by its own role: `country_of`, `husband_of`, `birthplace_of`."""
        return _as_a_word(cls.object_is) if cls.object_is else ""

    @classmethod
    def reads(cls) -> str:
        """The link with its ends in place, which is how a backwards one is seen at all.

        The word already carries the subject's role, so saying the role again doubled it: "a
        capital capital of a country". The ends are shown as what stands there.
        """
        return f"<{cls.subject_is}> {cls.word()} <{cls.object_is}>"


def _as_a_word(role: str) -> str:
    said = "_".join(_plain(role).replace("-", " ").split())
    return said if said.rsplit("_", 1)[-1] in PREPOSITIONS else f"{said}_of"


@dataclass
class Found:
    """What the look turned up: a relation, which end the asked-for role is, and why."""
    relation: type
    role_is: str        # "subject" or "object" — which end the asked-for word names
    how: str            # why this was taken as a match


class Relations:
    """Everything the world holds, and the look that comes before defining anything."""

    def __init__(self):
        self.known: list[type] = []

    def add(self, relation: type) -> type:
        self.known.append(relation)
        return relation

    def look(self, role: str, other: str = "") -> Found | None:
        """Is there already a relation for this? Exact words first, then a word inside a word.

        Kept deliberately dumb here. Matching by meaning is what the working world does
        (`classes_like`, embeddings) and it belongs at this step — but a sketch that guessed by
        meaning would hide whether the *shape* works, which is what is being tried.
        """
        wanted = _plain(role)
        for relation in self.known:
            near, far = _plain(relation.subject_is), _plain(relation.object_is)
            if wanted == near and (not other or _plain(other) == far):
                return Found(relation, "subject", "the same two words")
            if wanted == far and (not other or _plain(other) == near):
                return Found(relation, "object", "the same two words, said from the far end")
        for relation in self.known:
            for end, held in (("subject", relation.subject_is), ("object", relation.object_is)):
                if _alike(wanted, _plain(held)):
                    return Found(relation, end,
                                 f"{role!r} reads as {held!r} — offered, not applied: whether "
                                 f"two words are one idea depends on what was meant")
        return None

    def offer(self, subject_class: type | None = None, object_class: type | None = None) -> str:
        """What the world holds, for whoever is about to describe another one.

        Narrowed by the classes at the ends when there are two things to hand: a fact about a
        person and a place is worth reading against the words that have run between a person
        and a place. Narrowed, never hidden — the classes on a type are what it has seen, not a
        rule about what it may see, and a type named from one example must stay reachable for
        its second.
        """
        if not self.known:
            return "This world holds no relations yet."
        def fits(relation) -> bool:
            if subject_class is None and object_class is None:
                return True
            return ((not relation.subject_class or subject_class in relation.subject_class)
                    and (not relation.object_class or object_class in relation.object_class))

        near = [r for r in self.known if fits(r)]
        far = [r for r in self.known if not fits(r)]
        lines = []
        if near:
            lines.append("Relations this world already holds, between these sorts of thing:")
            lines += [f"    {_said(r)}" for r in near]
        if far:
            lines.append("And between other sorts of thing — one of these may still be the word,"
                         " and what it has run between is behind the times:")
            lines += [f"    {_said(r)}" for r in far]
        return "\n".join(lines)


def _said(relation: type) -> str:
    many = ("one" if relation.one_object else "many", "one" if relation.one_subject else "many")
    return (f"{relation.word():18} {relation.subject_is} \u2194 {relation.object_is}"
            f"   ({many[0]} per {_plain(relation.subject_is)}, "
            f"{many[1]} per {_plain(relation.object_is)})"
            + (f"  {', '.join(relation.implies)}" if relation.implies else ""))


def _plain(role: str) -> str:
    return (role or "").strip().lower()


def _alike(a: str, b: str) -> bool:
    """A stand-in for matching by meaning, and deliberately a poor one.

    One word inside another catches `chair` in `chairperson` and would catch `Berkeley` in
    `University of California, Berkeley` — which cost a measured world twelve names. It is here
    because the shape of the step matters and the quality of the matcher does not, yet: the real
    one compares meaning (`classes_like`), and the only thing this must show is that a near
    match is **offered** rather than silently missed.
    """
    if not a or not b:
        return False
    short, long = sorted((a, b), key=len)
    return len(short) >= 4 and short in long


def as_spec(described: dict) -> dict:
    """The description as the world's own JSON.

    What is asked of a reader is **data**, and the shape of what is written is ours. Two
    renderers from one description, and the prompt knows about neither: change how a relation
    is written down — a class, a spec file, a row — and nothing has to be asked again,
    re-measured or re-worded. A prompt that emitted code would have tied the two together, and
    every change to the code would have been a change to the question.
    """
    implies = tuple(w for w in described.get("implies") or () if w in IMPLICATIONS)
    return {"name": _class_name(described["subject_is"], described["object_is"]),
            "description": described.get("relation_is", ""),
            "relation": {"subject_is": described["subject_is"],
                         "object_is": described["object_is"],
                         "subject_class": tuple(described.get("subject_class") or ()),
                         "object_class": tuple(described.get("object_class") or ()),
                         "one_object": bool(described.get("one_object")),
                         "one_subject": bool(described.get("one_subject")),
                         "implies": list(implies)}}


def as_class(described: dict) -> str:
    """The description as the source of a class — the one notation a host already knows.

    Generated from the description rather than asked for: the reader is asked for data and the
    shape of the code is ours. See `as_spec`, the same description written another way.
    """
    subject_is, object_is = described["subject_is"], described["object_is"]
    body = [f"class {_class_name(subject_is, object_is)}(Relation):",
            f'    """{(described.get("relation_is") or "").strip()}"""',
            f"    subject_is = {subject_is!r}",
            f"    object_is = {object_is!r}"]
    for field in ("subject_class", "object_class"):
        if described.get(field):
            # The class itself, by its name in the code — not a string of it. A name in quotes
            # is a claim nothing checks; a name that must resolve is checked by Python.
            named = described[field]
            named = named if isinstance(named, (list, tuple)) else [named]
            inside = ", ".join(str(one) for one in named)
            body.append(f"    {field} = ({inside},)" if len(named) == 1
                        else f"    {field} = ({inside})")
    for field in ("one_object", "one_subject"):
        if described.get(field):
            body.append(f"    {field} = True")
    implies = tuple(w for w in described.get("implies") or () if w in IMPLICATIONS)
    if implies:
        body.append(f"    implies = {implies!r}")
    return "\n".join(body)


def _class_name(subject_is: str, object_is: str = "") -> str:
    """The two roles joined: `WifeHusband`, `CapitalCountry`, `PartWhole`.

    Nobody invents it and nobody argues about it. A name asked of a reader is one more open
    question, one more thing to get wrong, and one more word that can drift from what it names —
    and the roles already say everything the name would. Where both ends hold the same role it
    is said once: `SiblingSibling` would be silly, so `Sibling`.
    """
    near, far = _one_word(subject_is), _one_word(object_is)
    if not far or far == near:
        return near[:1].upper() + near[1:]
    return near[:1].upper() + near[1:] + far[:1].upper() + far[1:]


def _one_word(role: str) -> str:
    words = _plain(role).replace("-", "_").split()
    while words and words[0] in ("a", "an", "the"):
        words = words[1:]
    return words[-1] if words else ""
