# Time

Time in the world is one axis. Every entity, every relation, every remark sits on it, and the
same words mean the same thing everywhere: `starts`, `until`, `expire()`, `current()`,
`any_time=True`, `timeline()`. There is no separate calendar module — what a host has to learn is
which of three questions it is answering.

## Three times, easy to confuse

**When it is true** — the validity period, `starts` / `until`. A job that began in March and
ended in September, a lease that runs to next June, a manager who is the manager now. Every
entity and every relation has one. Nothing is ever deleted when a period ends; it stops holding
and becomes history.

**When it happened** — the thing's own time, stored as an ordinary attribute: `Event.start_time`,
a comment's `when`. A meeting that took place in May and one next week are both perfectly valid
records; their periods say nothing interesting, their `start_time` says everything. Searching
for them is searching an attribute: `Event.find(start_time=after(now()))`.

**When we learned it** — `created_at` on entities, `recorded_at` on comments. This is the world's
own bookkeeping and can differ from both of the above: a marriage recorded today may have started
in 2019. The host never sets it.

A single rule keeps these apart: *the period is about the record, the attribute is about the world,
`created_at` is about us*.

## Writing time

    Class.ensure(..., starts=date(2026, 10, 1))    # begins later
    Class.ensure(..., until=date(2026, 12, 31))    # ends then
    Class.ensure(..., ttl=timedelta(days=30))      # holds a month
    entity.keep(starts=..., until=... | ttl=... | permanent=True)
    entity.expire()                                 # ends now
    entity.current()                                # does it hold?

The same four keywords work on relations, because a relation is an instance:

    kevin.relate(b04, "membership", title="logistics lead", starts=date(2026, 1, 15))
    old_job.expire()

and on comments, where they say how long the remark is worth keeping:

    person.comment("on vacation", until=date(2026, 9, 30))
    person.comment("peanut allergy", permanent=True)

## Reading time

Reads answer about now — that is the useful default, and the reason "who is her partner" doesn't
return an ex. One keyword widens them everywhere:

    Class.all(any_time=True)         Class.find(..., any_time=True)
    entity.relations(kind, any_time=True)    entity.related(kind, any_time=True)
    entity.comments(any_time=True)   world.comments(any_time=True)

(`history=True` and `include_expired=True` still work; `any_time` is the name to use, because
what it adds is not only history — a relation that starts next month is the future.)

When a read hides something, the world says so rather than letting silence pass for an answer:

    [hints] Michael: 1 that ended (Olga is Michael's wife (partner)) — not shown, because
            partner relations read as they hold now; any_time=True includes them

## One function for everything dated

`entity.timeline(since=None, until=None)` works on anything that has time — an entity or a
relation — and returns the dated facts about it, oldest first: when it was recorded, when its
period starts and ends, what its attributes were changed to and when, its dated remarks, and
its relations starting and ending.

    for moment in ada.timeline():
        print(moment)
    <2026-01-15 — membership: TechCorp — from here>
    <2026-09-01 — remark: moved teams>
    <2026-09-19 — membership: TechCorp — until here>
    <2026-09-19 — membership: DataWorks — from here>

Each `Moment` has `.when` and `.what`. This is the answer to "what happened with this, and when" —
one call instead of assembling `history()`, `comments()`, `relations(any_time=True)` and the
period by hand.

`entity.history(attr)` remains for one attribute's past values, with the moment each stopped
holding.

## Comparing

`starts`, `until` and a timeline's `.when` come back as moments that compare with plain dates as
well as datetimes — `rel.starts >= today()` works instead of raising `'>=' not supported between
instances of 'datetime.datetime' and 'datetime.date'`, which used to cost a run and a retry every
time a host wrote the obvious thing. A date is read as its midnight, the way the rest of the
world reads it.

## What the world checks

Period overlap, not "now", is what makes a conflict. A person has at most one current employer,
but divorced in 2020 and married in 2022 is no contradiction — the periods don't overlap. Role
limits (one mother, one CEO) are checked the same way, so a former CEO never blocks the current
one.
