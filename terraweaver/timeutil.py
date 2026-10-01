"""One way to compare moments across the world.

Hosts pass dates, naive datetimes and aware ones interchangeably. Everything that decides
"is this current?" goes through here: a date means its midnight, an aware datetime is taken in
UTC, and all of them become naive UTC so they compare without surprises.
"""
import re
from datetime import date, datetime, timedelta, timezone
from contextlib import contextmanager


class Moment(datetime):
    """A moment the world hands back — a datetime that also compares with a plain date.

    Hosts mix the two constantly: `rel.starts >= today()` is the obvious thing to write and
    Python raises on it, costing a run and a retry every time. Here a date is read as its
    midnight, the way the rest of the world reads it.
    """

    def _both(self, other):
        if isinstance(other, datetime) or not isinstance(other, date):
            return other
        return datetime(other.year, other.month, other.day)

    def __eq__(self, other):
        return datetime.__eq__(self, self._both(other))

    def __ne__(self, other):
        return datetime.__ne__(self, self._both(other))

    def __lt__(self, other):
        return datetime.__lt__(self, self._both(other))

    def __le__(self, other):
        return datetime.__le__(self, self._both(other))

    def __gt__(self, other):
        return datetime.__gt__(self, self._both(other))

    def __ge__(self, other):
        return datetime.__ge__(self, self._both(other))

    __hash__ = datetime.__hash__


def moment(value):
    """The same instant, comparable with dates as well as datetimes."""
    if value is None or isinstance(value, Moment):
        return value
    value = as_datetime(value)
    return Moment(value.year, value.month, value.day, value.hour, value.minute,
                  value.second, value.microsecond)


EXACT, BEFORE, AFTER = "exact", "before", "after"

# The ends of time. A period already had open ends written as None, which is fine while None is
# read as "no end" — but a bound needs the other kind of openness too, and the two are not the
# same: "no end" means it never stops, "an end nobody has named" means it may already have. Two
# moments that compare with every other moment keep the difference sayable in arithmetic instead
# of in an `if` at every reader.
NEVER = datetime.min       # earlier than anything
ALWAYS = datetime.max      # later than anything


def as_datetime(value: date | datetime) -> datetime:
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)


# The world's own "now". None means the clock on the wall; set, it is the moment everything is
# recorded as happening at. A person says "as of last Tuesday" and means every word after it, and
# a transcript replayed years later means its own days, not today's — neither can be said by
# passing a date to every single call, and what is not said once is not said at all: in a run of
# 455 statements told "it is 2020-01-01", the host passed a date exactly zero times and all 1319
# statements landed stamped with the real year.
_MOMENT: datetime | None = None


def now() -> datetime:
    return _MOMENT if _MOMENT is not None else datetime.now(timezone.utc).replace(tzinfo=None)


def real_now() -> datetime:
    """The clock on the wall, whatever the world has been told the time is."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def set_now(moment) -> datetime | None:
    """Move the world's now, or give it back to the clock with None.

    A moment written as words is read as one. `as_datetime` wanted a date or a datetime and a
    string went into it and raised `AttributeError: 'str' object has no attribute 'year'` four
    frames down, although what the host had written — `world.now = "2020-01-20"` — is exactly
    what the docstring on that door invites (docs/code-review-2026-09-30.md 3.3.8).
    """
    global _MOMENT
    if isinstance(moment, str):
        read, _sure = told(moment)
        if read is None or getattr(read, "moment", None) is None:
            raise ValueError(
                f"{moment!r} does not read as a moment. Say it as a date — \"2020-01-20\", "
                f"date(2020, 1, 20) or datetime(2020, 1, 20) — or None to give the world back "
                f"the clock.")
        moment = read.moment
    _MOMENT = as_datetime(moment) if moment is not None else None
    return _MOMENT


@contextmanager
def as_of(moment):
    """Read and write as if it were `moment`, then put the clock back where it was.

    What `set_now` does, scoped. The reading uses it: a fact typed a day after it was said has to
    take its place in time where it was said, or a one-at-a-time word ends the wrong link. The
    deferred reading is resumable by design, so links are typed in whatever order the passes fall
    in — and arrival order is not telling order (docs/now.md, item 2).
    """
    was = _MOMENT
    try:
        set_now(moment)
        yield
    finally:
        set_now(was)


def shifted() -> datetime | None:
    """The moment the world has been told it is, if it has been told one."""
    return _MOMENT


# Time in the database: whole microseconds since the epoch, UTC. SQLite has no date type — the
# choices are a number or a string, and a string is only ordered correctly while every writer
# agrees on one spelling. That agreement is a convention, and a convention is exactly what broke
# here: '2026-09-21T00:00:00' and '2026-09-21T00:00:00+00:00' are the same moment and sort apart,
# so a period query answered wrongly and said nothing about it. A number cannot be spelled two
# ways, so the ordering is a property of the storage rather than of everyone's good behaviour.
EPOCH = datetime(1970, 1, 1)


def to_db(value) -> int | None:
    """A moment as the database keeps it. Dates count as midnight, as they do everywhere here."""
    if value is None:
        return None
    return round((as_datetime(value) - EPOCH).total_seconds() * 1_000_000)


def from_db(raw) -> datetime | None:
    """Back again — reading text too, because rows written before this still say it that way."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return EPOCH + timedelta(microseconds=int(raw))
    return as_datetime(datetime.fromisoformat(str(raw)))


def in_period(starts, until, moment: datetime) -> bool:
    """Whether [starts, until) covers the moment; a missing bound is open."""
    held = holds_at(starts, until, moment)
    return held is not False


def holds_at(starts, until, moment, from_is: str = EXACT, until_is: str = EXACT):
    """Whether [starts, until) covers the moment — True, False, or None for nobody knows.

    The third answer is the one that earns its keep. "She started there some time before now"
    covers today for certain and says nothing about last March, and a world with only two
    answers has to pick one of those to lie about. None is what the host is owed: it can ask,
    and asking beats a confident wrong date every time.
    """
    moment = as_datetime(moment)
    unsure = False
    if starts is not None:
        bound = starts if isinstance(starts, Bound) else Bound(starts, from_is)
        if bound.earliest > moment:
            return False
        unsure = unsure or bound.latest > moment
    if until is not None:
        bound = until if isinstance(until, Bound) else Bound(until, until_is)
        if bound.latest <= moment:
            return False
        unsure = unsure or bound.earliest <= moment
    return None if unsure else True


_NO_END_GIVEN = object()


def period_end(until=None, ttl=None, permanent: bool = False, base: datetime | None = None):
    """The end the caller asked for: a moment, None for no end, or NO_END_GIVEN if they didn't say."""
    given = sum(x is not None and x is not False for x in (until, ttl, permanent or None))
    if given > 1:
        raise ValueError("give one of until, ttl or permanent=True")
    if permanent:
        return None
    if until is not None:
        bound, _ = told(until)
        return bound if not bound.exact else bound.moment
    if ttl is not None:
        if not isinstance(ttl, timedelta):
            raise TypeError("ttl must be a timedelta, e.g. timedelta(days=7)")
        return (base or now()) + ttl
    return NO_END_GIVEN


NO_END_GIVEN = _NO_END_GIVEN


def check_start(starts):
    """The moment a start was told at — the bound's date, whichever side it names."""
    bound, _ = told(starts)
    return bound.moment if bound is not None else None


def show(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d") if (value.hour, value.minute) == (0, 0) else value.strftime("%Y-%m-%d %H:%M")
    return value.isoformat()


# A time somebody said, which is a date and a side of it. "2006-01-01" pins the moment; "before
# now" and "after 2006" name a moment the real one lies on one side of. The second kind is most
# of what people say — "earlier", "a while back", "some time before I moved" — and a world that
# only takes the first kind either loses those facts or, worse, writes down today's date and
# reads it back later as the truth. The bound keeps what was said and no more: the date is real,
# the side says the fact is not *at* it.



class Bound:
    """A moment and which side of it the fact is on."""

    __slots__ = ("moment", "side")

    def __init__(self, moment, side: str = EXACT):
        self.moment = as_datetime(moment) if moment is not None else None
        self.side = side

    def __repr__(self) -> str:
        return f"Bound({show(self.moment)}, {self.side!r})"

    def __str__(self) -> str:
        return self.describe()

    def __eq__(self, other):
        if isinstance(other, Bound):
            return (self.moment, self.side) == (other.moment, other.side)
        return NotImplemented

    __hash__ = None

    def describe(self) -> str:
        if self.moment is None:
            return "at a time nobody has said"
        if self.side == EXACT:
            return show(self.moment)
        return f"{self.side} {show(self.moment)}"

    @property
    def exact(self) -> bool:
        return self.side == EXACT

    @property
    def earliest(self) -> datetime:
        """The soonest the moment can be — NEVER when only its far edge was named."""
        return self.moment if self.side in (EXACT, AFTER) else NEVER

    @property
    def latest(self) -> datetime:
        """The latest it can be — ALWAYS when all that was said is that it came after."""
        return self.moment if self.side in (EXACT, BEFORE) else ALWAYS

    def known_by(self, moment) -> bool:
        """Whether, standing at `moment`, this has certainly happened already."""
        return self.latest <= as_datetime(moment)

    def still_ahead_at(self, moment) -> bool:
        """Whether, standing at `moment`, this certainly has not happened yet."""
        return self.earliest > as_datetime(moment)


def at(moment) -> Bound:
    return Bound(moment, EXACT)


def from_span(low, high) -> "Bound":
    """A bound from an interval with open ends — what `before(x)` and `after(x)` already are.

    The host says when with the same words it asks with: `before(now())` is a window in a
    question and a window around a start, and one word for one idea is the whole reason it can
    be written without being looked up.
    """
    if low is not None and high is not None:
        return Bound(low, EXACT) if as_datetime(low) == as_datetime(high) else Bound(high, BEFORE)
    if high is not None:
        return Bound(high, BEFORE)
    if low is not None:
        return Bound(low, AFTER)
    return None


# The words a person actually uses for a time, and what each one is a bound on. "Earlier" is not
# vagueness to be rejected — it is a real constraint, and the constraint is what ordering needs.
_WORDS = {
    "now": lambda: Bound(now(), EXACT),
    "today": lambda: Bound(_midnight(now()), EXACT),
    "just now": lambda: Bound(now(), EXACT),
    "yesterday": lambda: Bound(_midnight(now()) - timedelta(days=1), EXACT),
    "the day before yesterday": lambda: Bound(_midnight(now()) - timedelta(days=2), EXACT),
    "tomorrow": lambda: Bound(_midnight(now()) + timedelta(days=1), EXACT),
    "earlier": lambda: Bound(now(), BEFORE),
    "before": lambda: Bound(now(), BEFORE),
    "before now": lambda: Bound(now(), BEFORE),
    "in the past": lambda: Bound(now(), BEFORE),
    "a while ago": lambda: Bound(now(), BEFORE),
    "some time ago": lambda: Bound(now(), BEFORE),
    "once": lambda: Bound(now(), BEFORE),
    "back then": lambda: Bound(now(), BEFORE),
    "recently": lambda: Bound(now(), BEFORE),
    "later": lambda: Bound(now(), AFTER),
    "after now": lambda: Bound(now(), AFTER),
    "in the future": lambda: Bound(now(), AFTER),
    "last week": lambda: Bound(_midnight(now()) - timedelta(days=7), EXACT),
    "last month": lambda: Bound(_midnight(now()) - timedelta(days=30), EXACT),
    "last year": lambda: Bound(_midnight(now()) - timedelta(days=365), EXACT),
}

# Hedges are dropped, not refused: "I think earlier" says the same time as "earlier" and adds
# only that the speaker is unsure, which is worth nothing here and everything to the agent who
# decides whether to ask again.
_HEDGES = ("i think", "i guess", "maybe", "probably", "perhaps", "roughly", "around",
           "about", "approximately", "sometime", "some time", "somewhere", "~")

_AGO = re.compile(r"^(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago$")
_EVERY = {"second": 1, "minute": 60, "hour": 3600, "day": 86400,
          "week": 604800, "month": 2592000, "year": 31536000}


def _midnight(moment: datetime) -> datetime:
    return datetime(moment.year, moment.month, moment.day)


def told(said, *, sure: bool = True) -> tuple:
    """What a said time comes to: (Bound, sure). Raises ValueError on words it cannot read."""
    if said is None:
        return None, sure
    if isinstance(said, Bound):
        return said, sure
    if isinstance(said, (date, datetime)):
        return Bound(said, EXACT), sure
    if hasattr(said, "low") and hasattr(said, "high"):   # before(x) / after(x) / between(a, b)
        bound = from_span(said.low, said.high)
        if bound is None:
            raise ValueError(f"{getattr(said, 'text', said)!r} names no moment at all")
        return bound, sure
    if not isinstance(said, str):
        raise TypeError("a time is a date, a datetime, or words like 'now', 'yesterday', "
                        "'before now', '3 years ago', '2006-01-01'")
    text = " ".join(said.strip().lower().replace(",", " ").split())
    for hedge in _HEDGES:
        if text.startswith(hedge + " ") or text == hedge:
            text, sure = text[len(hedge):].strip(), False
    if not text:
        raise ValueError("that says how sure you are but not when")
    for side, word in ((BEFORE, "before "), (BEFORE, "earlier than "), (BEFORE, "until "),
                       (AFTER, "after "), (AFTER, "later than "), (AFTER, "since "),
                       (AFTER, "from ")):
        if text.startswith(word):
            inner, sure = told(text[len(word):], sure=sure)
            return Bound(inner.moment, side), sure
    if text in _WORDS:
        return _WORDS[text](), sure
    hit = _AGO.match(text)
    if hit:
        return Bound(now() - timedelta(seconds=int(hit.group(1)) * _EVERY[hit.group(2)]), EXACT), sure
    if text.startswith("in "):
        text = text[3:].strip()
    if re.fullmatch(r"\d{4}", text):  # "2006" is the year, and the year starts in January
        return Bound(datetime(int(text), 1, 1), EXACT), sure
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return Bound(datetime(int(text[:4]), int(text[5:]), 1), EXACT), sure
    named = _a_month(text)
    if named is not None:
        return Bound(named, EXACT), sure
    try:
        return Bound(datetime.fromisoformat(text), EXACT), sure
    except ValueError:
        raise ValueError(
            f"I cannot read {said!r} as a time. Say a date — date(2006, 1, 1) or '2006-01-01' — "
            f"or words: 'now', 'today', 'yesterday', '3 years ago', 'in 2006', 'March 2006', "
            f"'12 March 2006', or a side and a date when you only know that much: 'before now', "
            f"before(now()), after(date(2006, 1, 1))."
        ) from None


MONTHS = {name: n for n, name in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"), start=1)}
MONTHS.update({name[:3]: n for name, n in list(MONTHS.items())})


def _a_month(text: str):
    """A month said by its name: "march 2023", "12 march 2023", "march 12 2023".

    Here because it is how people say a date, and the engineer writes down what was said. Left out,
    `starts="March 2023"` was refused, and what the writer did next was give the year alone — so a
    month somebody named came into the record as the first of January. A date degraded is worse
    than a date refused, because nothing afterwards can tell it from one somebody knew.

    A month with no day is the first of it, which is what `'2006-03'` and `'2006'` already come to:
    the coarser word names the moment its span begins. What makes that honest is the side — "since
    March 2023" is `after` that moment, and the side is read before this is reached.
    """
    words = text.split()
    if not (2 <= len(words) <= 3):
        return None
    month = next((MONTHS[w] for w in words if w in MONTHS), None)
    if month is None:
        return None
    numbers = [w for w in words if w.isdigit()]
    year = next((int(w) for w in numbers if len(w) == 4), None)
    if year is None:
        return None
    day = next((int(w) for w in numbers if len(w) <= 2), 1)
    try:
        return datetime(year, month, day)
    except ValueError:   # a day that month has not got is not a date
        return None
