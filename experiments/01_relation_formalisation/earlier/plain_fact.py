"""The host says the fact in words. Nothing is constructed but the two things it is about.

    paris.fact("is the capital of", france)

Everything the host had to isolate — which word is the role, which end it names, what the far
end is called — it no longer does. It is a language model; a sentence is its native form, and
every construction it was asked to fill in today turned out to be a place it filled badly:
`Speaks` collected two ideas because a type name had to be chosen, and three links went in
backwards because an argument order had to be got right.

**What is not given away.** Which two things. The world cannot tell two Annas apart from a
sentence, and identity is the one thing no reading repairs.

**What it costs.** One open question per distinct *phrase*, not per fact. "is the capital of"
is asked about once and answered for every capital thereafter — 115 links over 20 phrasings is
20 calls, not 115. That is the whole economy of it, and the reason the phrase is the cache key.
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relation_class import Relation, Relations, as_class, _plain  # noqa: E402


@dataclass
class Phrases:
    """What a phrase turned out to mean, kept so it is worked out once.

    The host writes as it speaks and says the same thing many ways: "is the capital of", "is
    capital of", "serves as the capital of". Each is asked about once; the answer is the same
    relation, and the second phrasing joins the first rather than making a second type.
    """
    book: Relations
    describe: object = None                      # the open reader; None means nothing is asked
    known: dict = field(default_factory=dict)    # phrase -> (relation, which end the subject is)
    asked: int = 0

    def read(self, phrase: str, a: str, b: str):
        """What relation this phrase is, and which end the sentence starts from."""
        key = _plain(phrase)
        if key in self.known:
            return self.known[key]
        said = self.describe(phrase.replace("_", "{}", 1).format(a).replace("_", b, 1)
                             if "_" in phrase else f"{a} {phrase} {b}") if self.describe else None
        if not said:
            return None
        self.asked += 1
        found = self.book.look(said["subject_is"], said["object_is"])
        if found is not None:
            # Already here under these very words: the phrase joins it, nothing is defined.
            self.known[key] = (found.relation, found.role_is)
            return self.known[key]
        where = {"Relation": Relation}
        exec(as_class(said), where)
        made = next(v for k, v in where.items()
                    if isinstance(v, type) and issubclass(v, Relation) and v is not Relation)
        self.book.add(made)
        self.known[key] = (made, "subject")
        return self.known[key]


@dataclass(eq=False)
class Thing:
    name: str
    world: "World | None" = None

    def __repr__(self) -> str:
        return self.name

    def fact(self, said: str, other: "Thing", starts=None):
        """`masha.fact("Маша — жена Саши", sasha)` — the link, with the sentence inside it."""
        return self.world.fact(self, said, other, starts=starts)


@dataclass
class Fact:
    """A link between two things, with the sentence that said it kept inside.

    Both are needed and neither replaces the other. **The two things** because identity cannot
    be recovered from words — two Annas are two, and no reading repairs a confusion of them.
    **The sentence** because it is what was said, and everything else about this link is a
    reading of it: which relation, which end is which, how many there may be. A reading may be
    wrong and be built again; the sentence may not be rebuilt from anything.

    So the record is: these two, and these words. Nothing else is stored.
    """
    subject: Thing
    object: Thing
    said: str                     # "Маша — жена Саши", in the words it came in
    starts: object = None

    # There was a `phrase()` here that cut the names out of the sentence, to ask about the
    # wording once rather than once per fact. It is gone, and the reason is worth keeping: the
    # reader is handed the two things **as things**, beside the sentence. It does not look for
    # their names in the text, so nothing has to be cut out of it — and cutting was never going
    # to work anyway, since "жена Саши" and "жена Бориса" differ by a declension the cutting
    # cannot see. What the reader does is read the meaning, and the meaning is there whole.
    #
    # The economy is elsewhere, and it is the two readers: asking whether a fact belongs to a
    # relation already held is a **closed** question with the held ones as its options, which is
    # cheap and calibrated; only when none of them fits is a new relation **described**, which is
    # the expensive open question and happens once per relation rather than once per fact.

    def reads(self) -> str:
        return self.said


class World:
    """The record is the sentences. What they mean is read, and read again when it changes."""

    def __init__(self, describe=None):
        self.facts: list[Fact] = []
        self.book = Relations()
        self.phrases = Phrases(self.book, describe)

    def thing(self, name: str) -> Thing:
        return Thing(name, self)

    def fact(self, subject: Thing, said: str, obj: Thing, starts=None) -> Fact:
        """Write down the link and the words. Reading them is separate, and may be done later."""
        made = Fact(subject, obj, said, starts)
        self.facts.append(made)
        return made

    def links(self) -> list[tuple]:
        """The facts as relations — read, not stored. (relation, subject, object)."""
        out = []
        for said in self.facts:
            read = self.phrases.read(said.said, said.subject.name, said.object.name)
            if read is None:
                continue
            relation, which = read
            subject, obj = ((said.subject, said.object) if which == "subject"
                            else (said.object, said.subject))
            out.append((relation, subject, obj))
        return out
