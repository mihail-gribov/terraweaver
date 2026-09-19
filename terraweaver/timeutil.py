"""One way to compare moments across the world.

Hosts pass dates, naive datetimes and aware ones interchangeably. Everything that decides
"is this current?" goes through here: a date means its midnight, an aware datetime is taken in
UTC, and all of them become naive UTC so they compare without surprises.
"""
from datetime import date, datetime, timedelta, timezone


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
