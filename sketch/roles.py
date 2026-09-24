"""A relation built from the pair of roles, written from scratch to be tried on examples.

Nothing here touches the world. It is the smallest thing that can answer the questions the
long argument left open (`docs/relation-properties.md`):

- Is the conjugate role pair enough to be the type's identity, with no invented name?
- Does direction stop being a question when the ends are named rather than ordered?
- Is symmetry just `subject_is == object_is`, with no flag?
- Does "cardinality one means the periods do not overlap" hold as the whole of supersession?
- Does the readable attribute on each entity fall out of the pair and the cardinality?

Six fields, and each is here because something cannot be tested without it.

    subject_is, object_is   the pair. The identity, the direction and the reading, at once.
    one_object, one_subject how many hold AT A MOMENT on each side. Decides both whether a
                            period may overlap and whether a read gives a value or a list.
    transitive              the one inference rule being tried.
    descriptions            on the link, not the type: why this one is here, in whose words.
"""
from dataclasses import dataclass, field
from datetime import datetime

def _word(role: str) -> str:
    """A role as an attribute name: "a city that serves as a capital" -> capital."""
    return role.strip().split()[-1].lower().replace("-", "_")


FOREVER = None          # no end: it does not stop
UNKNOWN_END = "before"  # it has stopped, and nobody said when


@dataclass(frozen=True)
class Pair:
    """A relation, which is a pair of conjugate roles and nothing else.

    There is no `kind`. The word a host would write — `capital_of` — is read off the roles, and
    the pair is what two links are the same type by. Two hosts who write `capital ↔ country`
    land on one relation however they would have named it, which is what `ChairpersonOf` and
    `DirectorOf` (0.86 alike, two names for one idea) cost in a measured run.
    """
    subject_is: str
    object_is: str
    one_object: bool = False      # at a moment, may the subject have several objects?
    one_subject: bool = False     # at a moment, may the object have several subjects?
    transitive: bool = False

    @property
    def symmetric(self) -> bool:
        """The whole of symmetry: the two roles are the same word. No flag, nothing declared.

        `sibling ↔ sibling` is symmetric, `mother ↔ child` is not — and a type that claims to be
        symmetric while holding `mother ↔ child`, as `Kin` does today, cannot be written here.
        """
        return self.subject_is == self.object_is

    def reads(self, a: str, b: str) -> str:
        return f"{a} is {b}'s {self.subject_is}" if not self.symmetric else \
               f"{a} and {b} are {self.subject_is}s of each other"

    def word(self) -> str:
        """The name a host would have invented, derived rather than asked for."""
        return f"{_word(self.subject_is)}_of"


@dataclass
class Link:
    """One link: two things, a pair, a period, and why it is here."""
    pair: Pair
    subject: str
    object: str
    starts: datetime | None = None
    until: datetime | None = None
    until_is: str = "exact"          # "exact" when named, "before" when it ended unsaid
    descriptions: list[str] = field(default_factory=list)

    def holds_at(self, moment: datetime):
        """True, False, or None for nobody knows — the third answer is the point."""
        if self.starts is not None and moment < self.starts:
            return False
        if self.until is None:
            return True
        if self.until_is == UNKNOWN_END:
            # It stopped, and when is not known. Before the telling it may or may not have held.
            return None if moment < self.until else False
        return moment < self.until

    def reads(self) -> str:
        return self.pair.reads(self.subject, self.object)


@dataclass(eq=False)
class Thing:
    """Whatever a link joins. Held by reference, not by name: two things called Paris are two.

    Its attributes are not declared anywhere. Ask Paris what it is the capital **of** and the
    answer comes from the pair; ask France for its **capital** and the same link answers from
    the other end. The two names are the two roles, and which of them gives a list rather than
    a value is the cardinality, not a second decision:

        paris.capital_of  ->  France        one_object=True   -> a value
        france.capital    ->  Paris         one_subject=True  -> a value
        anna.mother_of    ->  [Boris, Vera] one_object=False  -> a list
        boris.mother      ->  Anna          one_subject=True  -> a value

    In the working world four such attributes are written out by hand in JSON and registered in
    `relations.DERIVED`; here there are none to write, and none to get out of step with the
    relation they read.
    """
    name: str
    world: "World | None" = None

    def __repr__(self) -> str:
        return self.name

    def __getattr__(self, asked: str):
        world = self.__dict__.get("world")
        if world is None or asked.startswith("_"):
            raise AttributeError(asked)
        answer = world.through(self, asked)
        if answer is _NOTHING:
            raise AttributeError(
                f"{self.name} has no {asked!r}. It is read from the roles of the relations this "
                f"world holds: {', '.join(sorted(world.readable())) or '(none yet)'}")
        return answer


_NOTHING = object()


class World:
    """The smallest world that can hold links of this shape, and answer of them."""

    def __init__(self):
        self.pairs: dict[tuple[str, str], Pair] = {}
        self.links: list[Link] = []
        self.said: list[str] = []          # what the world said while working

    # --- writing ---

    def pair(self, subject_is: str, object_is: str, **how) -> Pair:
        """Find or make the relation. Its identity is the two roles, so the same two words are
        the same relation however anybody would have named it."""
        key = (subject_is, object_is)
        if key not in self.pairs:
            self.pairs[key] = Pair(subject_is, object_is, **how)
        return self.pairs[key]

    def relate(self, subject: Thing, subject_is: str, obj: Thing, object_is: str,
               starts: datetime | None = None, because: str = "") -> Link:
        """Write a link by naming what each end IS. There is no direction to get wrong: the
        roles carry it, and `Great Britain is London's capital` cannot be said by accident —
        it has to be said on purpose, by calling Great Britain the capital."""
        pair = self.pairs.get((subject_is, object_is)) or self.pairs.get((object_is, subject_is))
        if pair is None:
            raise KeyError(f"no relation between a {subject_is!r} and a {object_is!r} yet — "
                           f"world.pair({subject_is!r}, {object_is!r}, ...) makes one")
        if (pair.subject_is, pair.object_is) == (object_is, subject_is) and not pair.symmetric:
            subject, obj = obj, subject          # said from the far end; one link either way
        made = Link(pair, subject, obj, starts=starts,
                    descriptions=[because] if because else [])
        self._make_room(made)
        self.links.append(made)
        return made

    def _make_room(self, new: Link) -> None:
        """Cardinality one means the periods do not overlap. That is all supersession is.

        Nothing is replaced and nothing is refused: whatever was active when this one begins is
        given an end. Named, if the new one said when it started; `before` if it did not, which
        says "it stopped and nobody said when" rather than inventing a day.
        """
        for old in self.links:
            if old.pair is not new.pair or old.until is not None:
                continue
            crowds_subject = new.pair.one_object and old.subject is new.subject
            crowds_object = new.pair.one_subject and old.object is new.object
            if not (crowds_subject or crowds_object):
                continue
            if old.subject is new.subject and old.object is new.object:
                continue                      # the same link said again
            if new.starts is not None:
                old.until, old.until_is = new.starts, "exact"
                self.said.append(f"{old.reads()} ends {new.starts.date()}, where this one begins")
            else:
                old.until, old.until_is = datetime.now(), UNKNOWN_END
                self.said.append(f"{old.reads()} has stopped — nobody said when, so it is "
                                 f"recorded as ended before now, not on a day I made up")

    def thing(self, name: str) -> Thing:
        """A thing that knows its world, so its attributes can be read off the relations."""
        return Thing(name, self)

    # --- reading ---

    def readable(self) -> set:
        """Every attribute name this world's relations give its things."""
        out = set()
        for pair in self.pairs.values():
            out.add(f"{_word(pair.subject_is)}_of")     # asked of the one in the subject role
            out.add(_word(pair.subject_is))             # asked of the one in the object role
        return out

    def through(self, thing: Thing, asked: str):
        """Answer `thing.<asked>` from the relations, or _NOTHING if no role is called that.

        `<role>_of` is asked of the end that holds the role — "Paris, capital of what?"
        `<role>` is asked of the other end — "France, your capital?"
        """
        for pair in self.pairs.values():
            role = _word(pair.subject_is)
            if asked == f"{role}_of":
                return self.read(thing, pair.object_is)
            if asked == role:
                return self.read(thing, pair.subject_is)
        return _NOTHING

    def read(self, thing: Thing, role: str, at: datetime | None = None):
        """What this thing has in that role — a value or a list, decided by the cardinality.

        The attribute a host would have declared by hand falls out of the pair: ask Paris for
        its `capital_of` and get France; ask France for its `capital` and get Paris. Which of
        the two is a list is not a separate decision — it is `one_object` / `one_subject`.
        """
        at = at or datetime.now()
        out, single = [], False
        for pair in self.pairs.values():
            if role == pair.object_is:           # reading from the subject end
                single = pair.one_object
                out += [l.object for l in self._of(pair, at) if l.subject is thing]
                if pair.symmetric:
                    out += [l.subject for l in self._of(pair, at) if l.object is thing]
            elif role == pair.subject_is:        # reading from the object end
                single = pair.one_subject
                out += [l.subject for l in self._of(pair, at) if l.object is thing]
            if pair.transitive and out:
                out += self._chain(pair, out, at)
        out = list(dict.fromkeys(out))
        return (out[0] if out else None) if single else out

    def _of(self, pair: Pair, at: datetime) -> list[Link]:
        return [l for l in self.links if l.pair is pair and l.holds_at(at) is not False]

    def _chain(self, pair: Pair, reached: list, at: datetime) -> list:
        """Everything further along, by every branch — a thing may be in two wholes."""
        out, edge, seen = [], list(reached), {id(x) for x in reached}
        while edge:
            nxt = [l.object for l in self._of(pair, at) for e in edge
                   if l.subject is e and id(l.object) not in seen]
            for x in nxt:
                seen.add(id(x))
            out += nxt
            edge = nxt
        return out
