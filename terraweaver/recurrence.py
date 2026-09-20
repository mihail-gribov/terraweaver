"""Things that happen again: a rule, not a thousand rows.

Much of a life is periodic — a standup every weekday, rent on the first, a 1:1 every other
Tuesday, a visa every five years, on call every third week. Written out one by one, each of
those is a hundred statements that say the same thing, and the hundred-and-first is missed.

So a repeat is stated once, as a rule, the same way a period is: an anchor (when the first one
is), a step (`every=`), how long each one lasts (`lasting=`, nothing for a moment rather than a
stretch), and when the whole series stops (`until=`). Everything else is arithmetic:

    covers(anchor, every, lasting, moment)     does it hold at that moment — O(1), no expansion
    occurrences(anchor, every, since, until)   the ones inside a window the caller asked about
    next_after(anchor, every, moment)          when the next one is

Nothing is materialised. A rule with no end would otherwise be an infinite table, and a table
cut off at a horizon answers "no" for anything past it, which is worse than slow — it is wrong
and quiet about it. Bounds belong to the question, not to the store.

The step is a small vocabulary on purpose: days and weeks are plain arithmetic, months and years
are not (a monthly thing anchored on the 31st falls on the 28th in February), so those step by
the calendar and clamp. Anything a person says beyond this — "the first Monday", "every other
Thursday except in August" — is a rule about rules, and belongs in a statement somebody wrote,
not in a parser nobody can predict.
"""
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta

# What `every=` may say, as the number of days or months one step takes.
WORDS = {
    "day": (1, "days"), "days": (1, "days"),
    "week": (7, "days"), "weeks": (7, "days"),
    "fortnight": (14, "days"),
    "month": (1, "months"), "months": (1, "months"),
    "quarter": (3, "months"), "quarters": (3, "months"),
    "year": (12, "months"), "years": (12, "months"),
}


@dataclass(frozen=True)
class Every:
    """A step: so many days, or so many months (which the calendar counts, not the clock)."""

    n: int
    unit: str  # "days" | "months"

    def __str__(self) -> str:
        if self.unit == "months" and self.n % 12 == 0:
            n = self.n // 12
            return "year" if n == 1 else f"{n} years"
        if self.unit == "days" and self.n % 7 == 0:
            n = self.n // 7
            return "week" if n == 1 else f"{n} weeks"
        one = self.unit[:-1]
        return one if self.n == 1 else f"{self.n} {self.unit}"


def read(every) -> Every | None:
    """What the host said, as a step. None means it said nothing."""
    if every is None or every is False:
        return None
    if isinstance(every, Every):
        return every
    if isinstance(every, timedelta):
        days = int(every.total_seconds() // 86400)
        if days < 1:
            raise ValueError("a repeat steps by whole days at least: every=timedelta(days=1)")
        return Every(days, "days")
    text = str(every).strip().lower()
    match = re.fullmatch(r"(?:every\s+)?(?:(\d+)\s+)?([a-z]+)", text)
    if not match or match.group(2) not in WORDS:
        raise ValueError(
            f"no repeat like {every!r}: say it as 'week', '2 weeks', 'month', 'quarter', 'year', "
            f"or a timedelta. Anything more particular is a note, not a rule.")
    size, unit = WORDS[match.group(2)]
    return Every(size * int(match.group(1) or 1), unit)


def add(moment: datetime, every: Every, times: int = 1) -> datetime:
    """One step on (or several), by the clock for days and by the calendar for months."""
    if every.unit == "days":
        return moment + timedelta(days=every.n * times)
    return _add_months(moment, every.n * times)


def which(anchor: datetime, every: Every, moment: datetime) -> int | None:
    """Which occurrence is the last one at or before `moment` — None before the series starts."""
    if moment < anchor:
        return None
    if every.unit == "days":
        return int((moment - anchor).days // every.n)
    months = (moment.year - anchor.year) * 12 + (moment.month - anchor.month)
    if _add_months(anchor, months) > moment:
        months -= 1
    return max(0, months // every.n)


def starts_at(anchor: datetime, every: Every, index: int) -> datetime:
    """When the occurrence with that index begins."""
    return add(anchor, every, index)


def covers(anchor: datetime, every, lasting, moment: datetime, until: datetime | None = None) -> bool:
    """Does the series hold at that moment — arithmetic, whatever the moment is.

    A repeat with no length is a moment, not a stretch: a standup at nine does not "hold" at
    half past. Those are asked about with occurrences(), which is the question they answer.
    """
    step, length = read(every), _length(lasting)
    if step is None or length is None or moment < anchor or (until is not None and moment >= until):
        return False
    index = which(anchor, step, moment)
    if index is None:
        return False
    begins = starts_at(anchor, step, index)
    return begins <= moment < begins + length


def occurrences(anchor: datetime, every, since: datetime, until: datetime,
                lasting=None, ends: datetime | None = None, cap: int = 500) -> list[tuple]:
    """Every occurrence touching the window asked about, as (starts, until-or-None) pairs.

    The window is the caller's, and so is the bound: a rule that never ends is fine, a question
    about it must still say how far it is asking.
    """
    step, length = read(every), _length(lasting)
    if step is None or until < anchor:
        return []
    stop = min(until, ends) if ends is not None else until
    index = max(0, (which(anchor, step, since) or 0) - (1 if length else 0))
    out = []
    while len(out) < cap:
        begins = starts_at(anchor, step, index)
        if begins > stop:
            break
        finishes = begins + length if length else None
        if (finishes or begins) >= since or (length and begins <= since < finishes):
            if begins <= stop and (ends is None or begins < ends):
                out.append((begins, finishes))
        index += 1
    return out


def next_after(anchor: datetime, every, moment: datetime,
               ends: datetime | None = None) -> datetime | None:
    """When the next one is, or None once the series is over."""
    step = read(every)
    if step is None:
        return None
    if moment < anchor:
        return anchor
    index = which(anchor, step, moment)
    following = starts_at(anchor, step, (index or 0) + 1)
    if ends is not None and following >= ends:
        return None
    return following


def describe(anchor: datetime, every, lasting=None, ends: datetime | None = None) -> str:
    """The rule in the words a person would use, for a repr or a receipt."""
    step = read(every)
    if step is None:
        return ""
    from terraweaver import timeutil

    text = f"every {step}, from {timeutil.show(anchor)}"
    length = _length(lasting)
    if length:
        text += f", {_days(length)} at a time"
    if ends is not None:
        text += f", until {timeutil.show(ends)}"
    return text


def _length(lasting) -> timedelta | None:
    if lasting is None or lasting is False:
        return None
    if isinstance(lasting, timedelta):
        return lasting if lasting > timedelta(0) else None
    return timedelta(days=float(lasting))


def _days(length: timedelta) -> str:
    """How long one occurrence runs, in the unit a person would say it in."""
    if length < timedelta(hours=1):
        return f"{round(length.total_seconds() / 60)} minutes"
    if length < timedelta(days=1):
        hours = round(length.total_seconds() / 3600, 1)
        return "an hour" if hours == 1 else f"{hours:g} hours"
    days = length.days + (1 if length.seconds else 0)
    return "a day" if days == 1 else f"{days} days"


def _add_months(moment: datetime, months: int) -> datetime:
    """Calendar months, clamped: the 31st becomes the 30th, or the 28th, where there is no 31st."""
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    return moment.replace(year=year, month=month, day=min(moment.day, monthrange(year, month)[1]))
