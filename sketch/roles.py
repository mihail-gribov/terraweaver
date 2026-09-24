"""A relation as the pair of roles — in two layers, because the world has two.

**The record** is what was said, in the words it was said in. `Masha is Sasha's wife` goes down
as three things: Masha, the word `wife`, Sasha. Nothing else. The world does not conclude from
it that `wife` pairs with `husband`, does not name the far end, does not decide how many there
may be — because none of that was said, and the record holds only what was.

**The image** is what follows. Pairs, conjugates, how many hold at a moment, what a thing reads
as: all of it worked out from the statements, none of it stored. Wrong, it is rebuilt; right, it
cost nothing to keep.

The line matters because the world cannot learn a relation from facts reliably — two tellings
about the same two things *look* like a conjugate pair and may be two different relations. So
the conclusion is a reading, held as long as it is useful and dropped when the statements change.

Six things are said about a relation, and every one of them by somebody:

    subject_is, object_is    the two roles, as words somebody used
    one_object, one_subject  how many hold AT A MOMENT on each side
    transitive               the one inference rule being tried
    descriptions             on the link: why this one is here, in whose words
"""
from dataclasses import dataclass, field
from datetime import datetime

UNKNOWN_END = "before"      # it has stopped, and nobody said when


def _word(role: str) -> str:
    """A role as an attribute name: "a city that serves as a capital" -> capital."""
    return role.strip().split()[-1].lower().replace("-", "_")


# --- the record: what was said ---

@dataclass(frozen=True)
class Said:
    """One utterance, in the words it came in. This is all that is stored."""
    subject: "Thing"
    role: str
    object: "Thing"
    starts: datetime | None = None
    because: str = ""

    def reads(self) -> str:
        return f"{self.subject} is {self.object}'s {self.role}"


# --- the image: what follows from it ---

@dataclass(eq=False)
class Pair:
    """Two roles that turned out to be the two ends of one relation. Worked out, not stored."""
    subject_is: str
    object_is: str = ""
    one_object: bool = False
    one_subject: bool = False
    transitive: bool = False
    why: str = ""                 # how the world came to read them as one relation

    @property
    def symmetric(self) -> bool:
        return bool(self.object_is) and self.subject_is == self.object_is

    def word(self) -> str:
        return f"{_word(self.subject_is)}_of"


@dataclass
class Link:
    """One relation between two things, over a period. Built, not stored."""
    pair: Pair
    subject: "Thing"
    object: "Thing"
    starts: datetime | None = None
    until: datetime | None = None
    until_is: str = "exact"
    descriptions: list[str] = field(default_factory=list)

    def holds_at(self, moment: datetime):
        """True, False, or None for nobody knows — the third answer is the point."""
        if self.starts is not None and moment < self.starts:
            return False
        if self.until is None:
            return True
        if self.until_is == UNKNOWN_END:
            return None if moment < self.until else False
        return moment < self.until

    def reads(self) -> str:
        if self.pair.symmetric:
            return f"{self.subject} and {self.object} are {self.pair.subject_is}s of each other"
        return f"{self.subject} is {self.object}'s {self.pair.subject_is}"


_NOTHING = object()


@dataclass(eq=False)
class Thing:
    """Whatever a link joins. Held by reference: two things called Paris are two things."""
    name: str
    world: "World | None" = None

    def __repr__(self) -> str:
        return self.name

    # --- what a host says: the knowledge, not the machinery ---

    def is_the(self, role: str, of: "Thing", starts=None, because: str = "") -> Said:
        """`paris.is_the("capital", of=france)` — this one holds that role toward that one."""
        return self.world.state(self, role, of, starts=starts, because=because)

    def has_the(self, role: str, thing: "Thing", starts=None, because: str = "") -> Said:
        """`france.has_the("capital", paris)` — the same fact, said from the other end."""
        return self.world.state(thing, role, self, starts=starts, because=because)

    def __getattr__(self, asked: str):
        world = self.__dict__.get("world")
        if world is None or asked.startswith("_"):
            raise AttributeError(asked)
        answer = world.image().through(self, asked)
        if answer is _NOTHING:
            raise AttributeError(
                f"{self.name} has no {asked!r}. It is read from the roles this world has been "
                f"told: {', '.join(sorted(world.image().readable())) or '(none yet)'}")
        return answer


class Image:
    """What follows from the statements. Built from them every time, kept by nobody.

    Three readings are made here and none of them is in the record:

    **Which roles are two ends of one relation.** The world watches for the same two things
    spoken about from both sides — `Masha is Sasha's wife`, `Sasha is Masha's husband` — and
    reads the two words as one relation. It is a reading and it can be wrong: two tellings about
    one couple may be two relations, not one. Wrong, it is dropped and rebuilt; it was never
    stored, so nothing has to be unsaid.

    **How many hold at a moment.** Counted, not declared: if nothing anybody said ever gave one
    thing two `wife`s at once, the world reads the role as one-at-a-time. It is not a promise —
    the next statement may widen it, and then the reading widens with it.

    **When each holds.** A period per link, and where a role holds one at a time the periods are
    made not to overlap: the earlier one ends where the later begins, or `before` where nobody
    said when.
    """

    def __init__(self, statements: list[Said]):
        self.statements = statements
        self.pairs: dict[str, Pair] = {}
        self.links: list[Link] = []
        self.noticed: list[str] = []
        self._build()

    # --- building ---

    def _build(self) -> None:
        self._find_pairs()
        self._count_how_many()
        self._lay_out_periods()

    def _find_pairs(self) -> None:
        """Roles that name the two ends of one relation, read off the statements."""
        conjugate: dict[str, str] = {}
        for one in self.statements:
            for other in self.statements:
                if one is other or one.role == other.role:
                    continue
                # The same two things, spoken about from both sides.
                if one.subject is other.object and one.object is other.subject:
                    conjugate.setdefault(one.role, other.role)
                    if conjugate[one.role] == other.role and \
                            f"{one.role}/{other.role}" not in [n.split(": ")[0] for n in self.noticed]:
                        self.noticed.append(
                            f"{one.role}/{other.role}: read as the two ends of one relation — "
                            f"{one.subject} and {one.object} were spoken about from both sides. "
                            f"Nobody said so; it is a reading of the statements")
        seen: set[str] = set()
        for one in self.statements:
            if one.role in seen:
                continue
            far = conjugate.get(one.role, "")
            pair = Pair(one.role, far, why=self.noticed[-1] if far else "")
            self.pairs[one.role] = pair
            seen.add(one.role)
            if far:
                self.pairs[far] = pair
                seen.add(far)

    def _count_how_many(self) -> None:
        """How many a role has held at once — counted from what was said, never promised."""
        by_subject: dict[tuple, set] = {}
        by_object: dict[tuple, set] = {}
        for one in self.statements:
            pair = self.pairs[one.role]
            near = one.role == pair.subject_is
            subject, obj = (one.subject, one.object) if near else (one.object, one.subject)
            by_subject.setdefault((id(pair), id(subject)), set()).add(id(obj))
            by_object.setdefault((id(pair), id(obj)), set()).add(id(subject))
        for pair in set(self.pairs.values()):
            objects = [len(v) for k, v in by_subject.items() if k[0] == id(pair)]
            subjects = [len(v) for k, v in by_object.items() if k[0] == id(pair)]
            pair.one_object = bool(objects) and max(objects) == 1
            pair.one_subject = bool(subjects) and max(subjects) == 1

    def _lay_out_periods(self) -> None:
        """One link per fact, and where a role holds one at a time, periods that do not overlap."""
        for one in sorted(self.statements, key=lambda s: (s.starts or datetime.min, id(s))):
            pair = self.pairs[one.role]
            near = one.role == pair.subject_is
            subject, obj = (one.subject, one.object) if near else (one.object, one.subject)
            standing = next((l for l in self.links if l.pair is pair
                             and l.subject is subject and l.object is obj), None)
            if standing is not None:
                if one.because:
                    standing.descriptions.append(one.because)
                continue                      # the same fact said again is one fact
            made = Link(pair, subject, obj, starts=one.starts,
                        descriptions=[one.because] if one.because else [])
            self._make_room(made)
            self.links.append(made)

    def _make_room(self, new: Link) -> None:
        for old in self.links:
            if old.pair is not new.pair or old.until is not None:
                continue
            crowded = ((new.pair.one_object and old.subject is new.subject)
                       or (new.pair.one_subject and old.object is new.object))
            if not crowded or (old.subject is new.subject and old.object is new.object):
                continue
            if new.starts is not None:
                old.until, old.until_is = new.starts, "exact"
                self.noticed.append(f"{old.reads()} ends {new.starts.date()}, where this begins")
            else:
                old.until, old.until_is = datetime.now(), UNKNOWN_END
                self.noticed.append(f"{old.reads()} has stopped — nobody said when, so it is "
                                    f"read as ended before now, not on a day I made up")

    # --- reading ---

    def readable(self) -> set:
        out = set()
        for pair in set(self.pairs.values()):
            out.add(f"{_word(pair.subject_is)}_of")
            if pair.object_is:
                out.add(_word(pair.subject_is))
        return out

    def through(self, thing: Thing, asked: str):
        for pair in set(self.pairs.values()):
            role = _word(pair.subject_is)
            if asked == f"{role}_of":
                return self.read(thing, pair.object_is or "", pair, far=True)
            if asked == role and pair.object_is:
                return self.read(thing, pair.subject_is, pair, far=False)
        return _NOTHING

    def read(self, thing: Thing, role: str, pair: Pair, far: bool, at: datetime | None = None):
        at = at or datetime.now()
        live = [l for l in self.links if l.pair is pair and l.holds_at(at) is not False]
        out = [l.object for l in live if l.subject is thing] if far else \
              [l.subject for l in live if l.object is thing]
        if pair.symmetric:
            out += [l.subject for l in live if l.object is thing] if far else \
                   [l.object for l in live if l.subject is thing]
        if pair.transitive and out:
            out += self._chain(pair, out, at)
        out = list(dict.fromkeys(out))
        single = pair.one_object if far else pair.one_subject
        return (out[0] if out else None) if single else out

    def _chain(self, pair: Pair, reached: list, at: datetime) -> list:
        out, edge, seen = [], list(reached), {id(x) for x in reached}
        while edge:
            nxt = [l.object for l in self.links if l.pair is pair and l.holds_at(at) is not False
                   for e in edge if l.subject is e and id(l.object) not in seen]
            for x in nxt:
                seen.add(id(x))
            out += nxt
            edge = nxt
        return out


class World:
    """The record, and an image of it rebuilt whenever the record has moved."""

    def __init__(self):
        self.statements: list[Said] = []
        self._image: Image | None = None

    def thing(self, name: str) -> Thing:
        return Thing(name, self)

    def state(self, subject: Thing, role: str, obj: Thing, starts=None, because: str = "") -> Said:
        """Write down what was said, in the words it was said in. Nothing is concluded here."""
        said = Said(subject, role, obj, starts, because)
        self.statements.append(said)
        self._image = None                 # the reading is stale; it will be built again
        return said

    def image(self) -> Image:
        if self._image is None:
            self._image = Image(self.statements)
        return self._image
