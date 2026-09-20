"""One way to compare moments across the world.

Hosts pass dates, naive datetimes and aware ones interchangeably. Everything that decides
"is this current?" goes through here: a date means its midnight, an aware datetime is taken in
UTC, and all of them become naive UTC so they compare without surprises.
"""
from datetime import date, datetime, timedelta, timezone


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


def as_datetime(value: date | datetime) -> datetime:
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    return value if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def in_period(starts, until, moment: datetime) -> bool:
    """Whether [starts, until) covers the moment; a missing bound is open."""
    if starts is not None and as_datetime(starts) > moment:
        return False
    if until is not None and as_datetime(until) <= moment:
        return False
    return True


_NO_END_GIVEN = object()


def period_end(until=None, ttl=None, permanent: bool = False, base: datetime | None = None):
    """The end the caller asked for: a moment, None for no end, or NO_END_GIVEN if they didn't say."""
    given = sum(x is not None and x is not False for x in (until, ttl, permanent or None))
    if given > 1:
        raise ValueError("give one of until, ttl or permanent=True")
    if permanent:
        return None
    if until is not None:
        if not isinstance(until, (date, datetime)):
            raise TypeError("until must be a date or datetime")
        return as_datetime(until)
    if ttl is not None:
        if not isinstance(ttl, timedelta):
            raise TypeError("ttl must be a timedelta, e.g. timedelta(days=7)")
        return (base or now()) + ttl
    return NO_END_GIVEN


NO_END_GIVEN = _NO_END_GIVEN


def check_start(starts):
    if starts is not None and not isinstance(starts, (date, datetime)):
        raise TypeError("starts must be a date or datetime")
    return as_datetime(starts) if starts is not None else None


def show(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d") if (value.hour, value.minute) == (0, 0) else value.strftime("%Y-%m-%d %H:%M")
    return value.isoformat()
