"""A relation as a class, found before it is made.

The mechanism, end to end:

    the host wants to say "Sasha is Masha's husband"
      -> LOOK: is there already a relation with these roles, or near enough?
           yes -> use it. Nothing is defined, nothing is named twice.
           no  -> DESCRIBE it: two roles and the properties. The host can do this itself,
                  because it is given what the world already holds; or it is asked of a reader.
                  -> the description becomes a class that inherits Relation
                  -> the class is registered, and from then on step one finds it

Looking first is not tidiness. In a measured run one recorder wrote `ChairpersonOf` and
`DirectorOf` (0.86 alike) and `CreatedBy` beside `FoundedBy` — two words for one idea, and a
world that holds both answers for neither. The look is what makes a vocabulary converge.

The class is the artefact because it is what the host can read, write and reason about with no
new notation: six class attributes, a docstring, and `Relation` above it.
"""
from dataclasses import dataclass


class Relation:
    """What every relation is. A class body says the six things and nothing else.

    No `kind`: the word is read off the roles. No `symmetric`: it is the roles being the same
    word. No `over_time`: a period belongs to the statement, not to the type.
    """
    subject_is: str = ""
    object_is: str = ""
    one_object: bool = False      # at a moment, may the subject have several objects?
    one_subject: bool = False     # at a moment, may the object have several subjects?
    transitive: bool = False

    @classmethod
    def symmetric(cls) -> bool:
        return bool(cls.object_is) and cls.subject_is == cls.object_is

    @classmethod
    def word(cls) -> str:
        return f"{cls.subject_is.strip().split()[-1].lower()}_of"

    @classmethod
    def roles(cls) -> tuple[str, str]:
        return cls.subject_is, cls.object_is


@dataclass
class Found:
    """What the look turned up: a relation, which end the asked-for role is, and how sure."""
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

    def settle(self, found: "Found", role: str, role_of: str, judge=None) -> str:
        """A candidate the look turned up, put to a judge with named options.

        The look is a generator and a poor judge: one word inside another catches `chair` in
        `chairperson` and `Berkeley` in `University of California, Berkeley`. So the deciding is
        a closed question — same idea, different ideas, or the two ends of one relation — and it
        is asked once, only when there is a candidate, and never acted on. Whether two words are
        one idea depends on what the person meant, which the host has and the world has not.

        Measured on seven pairs: six right and every confident answer right. `citizen` against
        `capital` — which the look offers and which is the false match that comes of comparing
        strings — was told apart at 0.98. The one it would not call was `spouse` against
        `husband`, at 0.50, which is the honest answer: one is wider than the other, and whether
        that is one idea depends on whether this world tells the sexes apart.
        """
        if judge is None:
            return (f"{role!r} reads like {found.relation.subject_is!r}, already here as "
                    f"{found.relation.__name__}. Is it the same idea?")
        said = judge(role, role_of, found.relation.subject_is, found.relation.object_is,
                     found.relation.__doc__ or "")
        choice, sure = said["choice"], said["probabilities"].get(said["choice"], 0.0)
        if choice == "same":
            return (f"{role!r} reads as {found.relation.subject_is!r} ({sure:.0%}), which this "
                    f"world already holds as {found.relation.__name__}. Use it rather than a "
                    f"second word for one idea — or say how they differ, and the difference "
                    f"goes in the descriptions where the next lookup will find it.")
        if choice == "two_ends":
            return (f"{role!r} and {found.relation.subject_is!r} read as the two ENDS of one "
                    f"relation ({sure:.0%}), not as two relations. {found.relation.__name__} is "
                    f"that relation; say the fact with it and name which end you mean.")
        return ""          # apart: nothing to say, and nothing is more wrong than a false alarm

    def offer(self) -> str:
        """What the world holds, for the host to read before it invents anything.

        This is the whole reason the host can do the describing itself: it is not being asked to
        remember what it defined an hour ago, it is being shown.
        """
        if not self.known:
            return "This world holds no relations yet."
        lines = ["Relations this world already holds — use one of these before defining another:"]
        for relation in self.known:
            many = ("many" if not relation.one_object else "one",
                    "many" if not relation.one_subject else "one")
            lines.append(
                f"    {relation.__name__:22} {relation.subject_is} ↔ {relation.object_is}"
                f"   ({many[0]} per {_plain(relation.subject_is)}, "
                f"{many[1]} per {_plain(relation.object_is)})"
                + ("  transitive" if relation.transitive else ""))
        return "\n".join(lines)


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


def as_class(described: dict) -> str:
    """The description as the source of a class. What the host writes, or is handed to write.

    A class rather than a record because it is the one notation the host already knows: it can
    be read, kept in a file, subclassed, and argued with. Nothing here is a new language.
    """
    subject_is, object_is = described["subject_is"], described["object_is"]
    name = "".join(w[:1].upper() + w[1:] for w in _plain(subject_is).split()[-1:]) + "Of"
    body = [f"class {name}(Relation):",
            f'    """{described.get("relation_is", "").strip()}"""',
            f'    subject_is = {subject_is!r}',
            f'    object_is = {object_is!r}']
    if described.get("one_object"):
        body.append("    one_object = True")
    if described.get("one_subject"):
        body.append("    one_subject = True")
    if described.get("transitive"):
        body.append("    transitive = True")
    return "\n".join(body)
