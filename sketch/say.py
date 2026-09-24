"""Two things and a sentence. That is the whole of what a host says.

    world.say(sasha, masha, "Sasha is Masha's husband")

Nothing else is asked of it. Not the role, not the type, not which end is the subject, not how
many there may be, not whether it changes over time. Every one of those was a construction the
host had to fill in, and every one was measured today as a place it filled badly:

    a type name had to be chosen      -> `Speaks` collected two ideas and answered for neither
    an argument order had to be right -> three links went in backwards, and a backwards link is
                                         the world asserting a falsehood, not losing a fact
    `over_time` had to be answered    -> asked of the type about something that happens to a
                                         statement, and answered by guess

What happens to the sentence is the world's: it is shown to a reader along with the two things
and what the world already holds, and the reader places it — joins a relation that is there or
describes a new one, and says which of the two holds which role.

Two things are never given away. **Which two things** — identity cannot be recovered from words,
and no later reading repairs a confusion of two Annas. And **the sentence itself**, kept in the
words it came in, because everything else here is a reading of it and a reading may be rebuilt.
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from relation_class import Relation, Relations, as_class  # noqa: E402
from place_the_fact import place  # noqa: E402


def _role_word(role: str) -> str:
    """A role as a word: "a city that serves as a capital" -> capital, "a husband" -> husband.

    The article is stripped because it leaked into every reading — "Masha's a husband" — and a
    reader asked for a noun phrase will put one there however the question is worded. Cheaper to
    take it off here than to fight the wording.
    """
    words = (role or "").strip().lower().replace("-", "_").split()
    while words and words[0] in ("a", "an", "the"):
        words = words[1:]
    return words[-1] if words else ""


@dataclass(eq=False)
class Thing:
    """Whatever a fact is about. Its attributes come from the roles it turns out to hold.

    Sasha is Masha's husband, so `sasha.husband_of` is Masha and `masha.wife_of` is Sasha: each
    end is asked by the name of **its own** role, and the answer is the other end. Nobody
    declares either attribute, and nothing decides whether the answer is one thing or a list
    except how many the relation allows at a moment.
    """
    name: str
    world: "World | None" = None

    def __repr__(self) -> str:
        return self.name

    def related(self, other: "Thing", words, starts=None):
        """Either door: a sentence for a relation nobody has typed, or a relation itself.

            boris.related(anna, "они поженились в 2019")   -> a reader types it
            boris.related(anna, HusbandWife)               -> already typed, nothing is asked
        """
        world = self.__dict__.get("world")
        if isinstance(words, type):
            return world.write(self, other, words, starts=starts)
        return world.say(self, other, words, starts=starts)

    def _related_by_sentence(self, other: "Thing", words: str, starts=None):
        """`boris.related(anna, "они поженились в 2019")` — what the agent writes.

        Two things and a sentence, and the sentence may be put any way the agent finds natural:

            boris.related(anna, "они поженились в 2019")     -> Boris is Anna's spouse
            boris.related(anna, "он женат на Анне")           -> Boris is Anna's husband
            boris.related(anna, "Анна замужем за Борисом")    -> Anna is Boris's wife

        The order of the two arguments is not the direction. Who holds which role is read out of
        the sentence, so the third of those lands with Anna as the subject although Boris was
        written first — which is why direction cannot be got wrong here: nobody sets it.
        """
        world = self.__dict__.get("world")
        return world.say(self, other, words, starts=starts)

    def __setattr__(self, asked: str, value):
        """`sasha.husband_of = olga` — a fact written in the plainest thing Python has.

        Free, and that is the point: the role is already known, so nothing is asked of a reader.
        The expensive question — what relation is this, which end is which — was answered the
        first time somebody said a fact of this kind, and every fact after it is an assignment.

        What it writes is a fact like any other, with the sentence it amounts to kept beside it,
        because the record holds words and this is the words it would have been.
        """
        world = self.__dict__.get("world")
        if world is None or asked in ("name", "world") or asked.startswith("_"):
            return object.__setattr__(self, asked, value)
        role = world.role_named(asked)
        if role is None:
            return object.__setattr__(self, asked, value)
        relation, near = role
        for other in (value if isinstance(value, (list, tuple)) else [value]):
            subject, obj = (self, other) if near else (other, self)
            world.write(subject, obj, relation)

    def __getattr__(self, asked: str):
        world = self.__dict__.get("world")
        if world is None or asked.startswith("_"):
            raise AttributeError(asked)
        answer = world.through(self, asked)
        role = world.role_named(asked)
        if answer is not _NOTHING and role is not None:
            relation, near = role

            def write(other, starts=None, _r=relation, _n=near):
                subject, obj = (self, other) if _n else (other, self)
                return world.write(subject, obj, _r, starts=starts)

            return Held(answer, write)
        if answer is _NOTHING:
            raise AttributeError(
                f"{self.name} has no {asked!r}. It is read from the roles this world has been "
                f"told: {', '.join(sorted(world.readable())) or '(none yet)'}")
        return answer


_NOTHING = object()


class Held:
    """What a role gives back: the answer, and a door to write another one through.

    Two doors into the same place, and which one a host uses decides what it costs:

        boris.related(anna, "они поженились в 2019")   untyped — a reader works out the relation
        boris.husband_of(anna)                         typed   — the world builds it, free
        boris.husband_of                               read    — who that is
        boris.husband_of = anna                        typed   — the same as the call

    The typed doors cost nothing at all: the expensive question — what relation is this, which
    end is which — was answered the first time somebody said a fact of this kind, and every fact
    after it is a call. A world with no reader at all can still be written to through them.

    Being both an answer and a call is a small piece of cleverness, and it is here because the
    two readings of `boris.husband_of` — "who is he married to" and "marry him to her" — are the
    two things a host wants and they differ only by parentheses.
    """

    def __init__(self, answer, write):
        self._answer, self._write = answer, write

    def __call__(self, other, starts=None):
        return self._write(other, starts)

    # Everything else is the answer, so reading behaves as if this class were not here.
    def __repr__(self): return repr(self._answer)
    def __eq__(self, other): return self._answer == other
    def __bool__(self): return bool(self._answer)
    def __iter__(self): return iter(self._answer or [])
    def __len__(self): return len(self._answer or [])
    def __getitem__(self, i): return self._answer[i]
    def __hash__(self): return id(self)

    @property
    def is_(self):
        """The answer itself, for where the proxy would be in the way."""
        return self._answer


@dataclass
class Said:
    """The record: these two, and these words. Nothing else is stored.

    `placed` is not part of the record — it is where the reading is kept once it has been made,
    so a fact is read once rather than once per question. A fact written through a role that is
    already known arrives with it already filled in, and costs no reading at all.
    """
    a: Thing
    b: Thing
    words: str
    starts: object = None
    placed: object = None


@dataclass
class Placed:
    """The reading: which relation, which of the two holds which end, and for how long.

    The period is here rather than in the record because it is worked out: what was said is
    "Sasha is Olga's husband", and that the earlier one stopped is a reading of two statements
    together. Nothing is replaced and nothing is erased — cardinality one means the periods do
    not overlap, and that is the whole of what supersession is in this world.
    """
    relation: type
    subject: Thing
    object: Thing
    said: Said
    starts: object = None
    until: object = None
    until_is: str = "exact"          # "before" when it stopped and nobody said when

    def holds(self) -> bool:
        return self.until is None

    def reads(self) -> str:
        said = f"{self.subject} is {self.object}'s {_role_word(self.relation.subject_is)}"
        if self.until is not None:
            said += (" (ended, when nobody said)" if self.until_is == "before"
                     else f" (ended {self.until})")
        return said


class World:
    def __init__(self, reader=None):
        self.record: list[Said] = []
        self.book = Relations()
        self.reader = reader
        self.asked = 0
        self.astray: list[str] = []    # readings that named somebody who is not here
        self._placed: list | None = None

    def thing(self, name: str) -> Thing:
        return Thing(name, self)

    def say(self, a: Thing, b: Thing, words: str, starts=None) -> Said:
        """Two things and a sentence. The whole of it."""
        said = Said(a, b, words, starts)
        self.record.append(said)
        self._placed = None            # the reading is stale; it is built again when asked
        return said

    # --- the reading, which is nobody's business but the world's ---

    def placed(self) -> list[Placed]:
        """Read the record. Cached, because reading costs a call and re-reading costs another.

        Called twice without this, it asked the reader twice about the same facts, got two
        different answers and defined the same relation twice — which is the very thing the
        looking-first is for.
        """
        if self._placed is not None:
            return self._placed
        out = []
        for said in self.record:
            if said.placed is not None:
                out.append(said.placed)          # written through a known role; nothing to ask
                continue
            got = place(self.reader, said.words, said.a.name, said.b.name, self.book.offer())
            if not got:
                continue
            self.asked += 1
            relation = self._relation_for(got)
            # The assignment has to name one of the two things handed over. Given names that
            # say nothing — X and Y — a reader read "She married him then" and made "She" the
            # subject: a role given to somebody who is not in the record. The two things are
            # the one part of this the world is sure of, so an answer outside them is dropped
            # rather than believed, and the order the host wrote them in stands.
            by_name = {said.a.name: said.a, said.b.name: said.b}
            subject = by_name.get(got.get("subject"))
            obj = by_name.get(got.get("object"))
            if subject is None or obj is None or subject is obj:
                subject, obj = said.a, said.b
                self.astray.append(
                    f"«{said.words}»: the roles were given to "
                    f"{got.get('subject')!r} and {got.get('object')!r}, which are not the two "
                    f"things this is about ({said.a}, {said.b}). Taken in the order they were "
                    f"written, and the reading is worth asking about again.")
            # The date comes out of the sentence, because that is where the writer put it.
            # Asked for as a separate argument it was one more thing to fill in and one more
            # place to guess; said in words — "since 2015" — it arrives with the fact.
            said.placed = Placed(relation, subject, obj, said,
                                 starts=got.get("starts") or said.starts,
                                 until=got.get("until"))
            self._make_room(said.placed, out)
            out.append(said.placed)
        self._placed = out
        return out

    # --- what a thing reads as, from the roles it holds ---

    def readable(self) -> set:
        """Every role this world knows a word for — from the relations, not from the links.

        A relation with nothing written under it yet still has its two roles, and asking about
        one should answer "nobody" rather than "no such word". Read off the links instead, a
        role existed only once somebody had used it, so the first fact of a kind could not be
        written through the door made for it.
        """
        out = set()
        for relation in self.book.known:
            out.add(f"{_role_word(relation.subject_is)}_of")
            if relation.object_is:
                out.add(f"{_role_word(relation.object_is)}_of")
        return out

    def through(self, thing: Thing, asked: str):
        """`sasha.husband_of` -> Masha. Each end asked by the name of its own role."""
        role = self.role_named(asked)
        if role is None:
            return _NOTHING
        relation, near = role
        single = relation.one_object if near else relation.one_subject
        out = []
        for placed in self._read():
            if placed.relation is not relation or not placed.holds():
                continue
            if near and placed.subject is thing:
                out.append(placed.object)
            elif not near and placed.object is thing:
                out.append(placed.subject)
        if relation.transitive and near and out:
            out += self._chain(relation, out)
        out = list(dict.fromkeys(out))
        return (out[0] if out else None) if single else out

    def _chain(self, relation: type, reached: list) -> list:
        """Everything further along, by every branch — a thing may be in two wholes.

        A part of a part is a part of the whole, so the answer to "what is the office part of"
        is the whole chain and not the first step of it. Every branch, because nothing says a
        thing has one whole: cardinality is about a moment, not about how many wholes exist.
        """
        out, edge, seen = [], list(reached), {id(x) for x in reached}
        while edge:
            further = [p.object for p in self._read()
                       if p.relation is relation and p.holds()
                       for e in edge if p.subject is e and id(p.object) not in seen]
            for one in further:
                seen.add(id(one))
            out += further
            edge = further
        return out

    def _through_old(self, thing: Thing, asked: str):
        out, single, found = [], None, False
        for placed in self._read():
            near = f"{_role_word(placed.relation.subject_is)}_of"
            far = f"{_role_word(placed.relation.object_is)}_of"
            if asked not in (near, far):
                continue
            found = True
            # How many this role allows is a property of the relation, so it is taken from the
            # relation — not from whether anything happens to hold right now. Read off the
            # answers instead, an ended marriage made `masha.wife_of` an empty list where it
            # should be nobody: the shape of the answer would have depended on the facts.
            if single is None:
                single = (placed.relation.one_object if asked == near
                          else placed.relation.one_subject)
            if not placed.holds():
                continue                   # it was so and is not now; it is not the answer
            if asked == near and placed.subject is thing:
                out.append(placed.object)
            elif asked == far and placed.object is thing:
                out.append(placed.subject)
        if not found:
            return _NOTHING
        out = list(dict.fromkeys(out))
        return (out[0] if out else None) if single else out

    def thin(self, placed: "Placed") -> str:
        """What is missing from a reading, in one line — or empty when it is sound.

        The loop the whole day keeps arriving at: nothing is refused, and what came back thin is
        asked about again. Measured here on two sentences about one couple:

            "She married him then"                       -> roles "marries" / "married"
            "Anna married Boris in June 2019, after      -> roles "spouse" / "spouse"
             they met at the Lisbon office"

        The first is not a worse answer, it is the answer to a worse question: the agent holds
        the conversation and the world never will, so a sentence that needs the conversation to
        be understood cannot be read by anything downstream. It is not refused — it is recorded,
        read as well as it can be, and the gap is named so the agent can say more.

        Re-reading costs nothing and breaks nothing: the record holds the sentence, and every
        reading is built from it again. Nothing has to be unsaid to be read better.
        """
        relation = placed.relation
        near, far = relation.subject_is, relation.object_is
        gaps = []
        if not far:
            gaps.append("nothing names the far end")
        if _role_word(near) == _role_word(far or "") and not relation.symmetric():
            gaps.append("both ends came back with the same word but the relation is not symmetric")
        for role in (near, far):
            word = _role_word(role)
            if word and (word.endswith("s") and word[:-1] in placed.said.words.lower()):
                gaps.append(f"{word!r} reads as the sentence's verb, not as what an end IS")
        if not gaps:
            return ""
        return (f"«{placed.said.words}» was read as {near or '?'} ↔ {far or '?'}, and "
                + "; ".join(gaps) + ". Say it again with what only you know — who the two are "
                f"by name, when it was, and what {placed.subject} is to {placed.object} in one "
                f"noun: a wife, a capital, a part.")

    def again(self, said: "Said", fuller: str) -> "Placed":
        """The agent said more. Read it again — the record keeps both tellings."""
        said.words = fuller
        said.placed = None
        self._placed = None
        return next((p for p in self.placed() if p.said is said), None)

    def role_named(self, asked: str):
        """The relation an attribute name belongs to, and whether it is asked of the near end."""
        if not asked.endswith("_of"):
            return None
        for relation in self.book.known:
            if asked == f"{_role_word(relation.subject_is)}_of":
                return relation, True
            if relation.object_is and asked == f"{_role_word(relation.object_is)}_of":
                return relation, False
        return None

    def write(self, subject: Thing, obj: Thing, relation: type, starts=None) -> Said:
        """A fact whose relation is already known: recorded, and read without asking anybody."""
        words = f"{subject} is {obj}'s {_role_word(relation.subject_is)}"
        said = Said(subject, obj, words, starts)
        said.placed = Placed(relation, subject, obj, said, starts=starts)
        self.record.append(said)
        if self._placed is not None:
            self._make_room(said.placed, self._placed)
            self._placed.append(said.placed)     # the reading grows; it is not thrown away
        return said

    @staticmethod
    def _make_room(new: Placed, among: list) -> None:
        """Cardinality one means the periods do not overlap. Nothing else happens here.

        The earlier one is given an end — the moment the later begins, if anybody said when, and
        otherwise `before`, which says it stopped without saying on what day. Ending it today
        would claim the world changed today, when all that happened today is that somebody
        mentioned it.
        """
        for old in among:
            if old.relation is not new.relation or old.until is not None:
                continue
            crowded = ((new.relation.one_object and old.subject is new.subject)
                       or (new.relation.one_subject and old.object is new.object))
            if not crowded or (old.subject is new.subject and old.object is new.object):
                continue
            if new.starts is not None:
                old.until, old.until_is = new.starts, "exact"
            else:
                old.until, old.until_is = "now", "before"

    def _read(self) -> list[Placed]:
        if self._placed is None:
            self._placed = self.placed()
        return self._placed

    def _relation_for(self, got: dict) -> type:
        if got.get("use"):
            held = next((r for r in self.book.known if r.__name__ == got["use"]), None)
            if held is not None:
                return held
        where = {"Relation": Relation}
        exec(as_class(got), where)
        made = next(v for k, v in where.items()
                    if isinstance(v, type) and issubclass(v, Relation) and v is not Relation)
        return self.book.add(made)
