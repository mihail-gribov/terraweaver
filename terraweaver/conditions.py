"""Range conditions for find: after, before, between.

`Event.find(start_time=between(date(2026, 9, 21), date(2026, 9, 28)))`. Written by hand, the
same filter trips over the details every time: a date against a datetime, a naive `now()`
against a stored time with a time zone. Here both sides go through timeutil first.

A date as an upper bound means the whole day: between(Monday, Sunday) includes Sunday, and
before(date) is before that day begins.
"""
from datetime import date, datetime, timedelta

from terraweaver import timeutil


class Condition:
    def __init__(self, low=None, high=None, high_includes_day: bool = False, text: str = ""):
        self.low = low
        self.high = high
        self.high_includes_day = high_includes_day
        self.text = text

    def test(self, value) -> bool:
        if value is None:
            return False
        if isinstance(value, (date, datetime)):
            value = timeutil.as_datetime(value)
            low = timeutil.as_datetime(self.low) if self.low is not None else None
            high = timeutil.as_datetime(self.high) if self.high is not None else None
            if high is not None and self.high_includes_day:
                high += timedelta(days=1)
        else:
            low, high = self.low, self.high
        try:
            if low is not None and value < low:
                return False
            if high is not None and value >= high:
                return False
        except TypeError:
            return False  # a number compared with a date: not a match rather than a crash
        return True

    def __repr__(self):
        return self.text


def _whole_day(value) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def after(moment) -> Condition:
    """At or after `moment` (a date means from the start of that day)."""
    return Condition(low=moment, text=f"after({moment!r})")


def before(moment) -> Condition:
    """Strictly before `moment` (a date means before that day begins)."""
    return Condition(high=moment, text=f"before({moment!r})")


def between(start, end) -> Condition:
    """From `start` up to `end`; a date as `end` includes that whole day."""
    return Condition(low=start, high=end, high_includes_day=_whole_day(end), text=f"between({start!r}, {end!r})")


def long_ago() -> datetime:
    """As far back as this world goes: a fact that has held longer than anybody cares to say.

    The honest answer for a standing fact nobody dated — a country's capital, a language, where
    a river runs. Not a guess at a real date and not the moment of telling: it says the thing
    was already so before this world began, which is exactly what is known about it.

    It is `timeutil.NEVER`, so every `holds_at` in the past answers True, and a later telling
    with a real start still supersedes it — earliest possible beginning, not greatest claim.
    """
    return timeutil.NEVER


def now() -> datetime:
    """The current moment, in the one form this world keeps time in: UTC, without a tzinfo.

    Every stored time is that form, so `now()` is comparable with all of them — and with a
    plain `datetime(2026, 10, 1)` a host writes by hand, which is the comparison that used to
    raise "can't compare offset-naive and offset-aware datetimes" in the middle of a task.

    It is the world's now, not the machine's: a world told it is 2020 has to mean 2020 in the
    host's arithmetic as well as in its own records, or the two disagree in the one place the
    disagreement is invisible."""
    return timeutil.now()


def today() -> date:
    return timeutil.now().date()
