"""The world's own time.

Everything else here happens because a host asked for it. A tick is the opposite: a procedure
cron calls, in which the world looks after itself — closes doubts that have resolved themselves,
notices what nobody looked at, counts what it isn't using. It is how a world stops being a
database that answers and starts being something that keeps itself in order.

Three rules hold for every job below, and they are what keep "the world improves itself" from
meaning "the world quietly changes what you told it":

- a tick never invents or alters a fact about the person. It may close its own doubts, raise new
  ones, and count things. Anything touching identity or facts is a *proposal* — an open question
  with its provenance — never an edit.
- a tick is bounded: each job has a period it isn't run more often than, and the whole tick has a
  budget. A world that is behind stays behind rather than blocking on a long night's work.
- a tick is recorded. What ran, when, how long it took, what it did — in `tick_runs`, so the next
  tick knows what it can skip and a person can read what happened while they weren't looking.

Adding a job: write a function taking the world, returning a line for the record or None, and
register it in JOBS with the period it wants. Keep each one short enough to be interrupted.
"""
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from terraweaver import matching

SCHEMA = """
CREATE TABLE IF NOT EXISTS tick_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job TEXT NOT NULL,
    at TEXT NOT NULL,
    took_ms INTEGER NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_tick_runs_job ON tick_runs(job, at);
"""

# How many new doubts one tick may raise. Attention is the scarce thing, not compute: a tick that
# fills the list with fifty duplicates has made the list worthless.
NEW_QUESTIONS_PER_TICK = 3

# How close two remarks must read before they are plainly the same thing said twice. High on
# purpose: measured on real remarks, anything below about 0.7 mixes topics rather than matching
# them, and a loose threshold here would fill the record with noise.
ALIKE = 0.78


@dataclass
class Job:
    name: str
    every: timedelta
    run: Callable
    what: str


def _settle_moot_questions(world) -> str | None:
    """A question whose reason is gone closes itself — but only when someone reads the list.
    Here it happens whether or not anyone looked."""
    before = world.store.conn.execute(
        "SELECT COUNT(*) FROM questions WHERE closed_at IS NULL").fetchone()[0]
    world.questions.open_(limit=10_000)  # verifying is what closes them
    after = world.store.conn.execute(
        "SELECT COUNT(*) FROM questions WHERE closed_at IS NULL").fetchone()[0]
    closed = before - after
    return f"closed {closed} question(s) whose reason had gone" if closed else None


def _spot_duplicates(world) -> str | None:
    """Two records for one person, made while nobody was checking — an agent that answered its
    own question, an import, a name written two ways. Not merged: asked about."""
    raised = []
    for class_name in matching.PART_MATCH_CLASSES:
        if class_name not in world.classes:
            continue
        entities = world.all(class_name, limit=None, history=True)
        name_key = matching.NAME_KEYS.get(class_name)
        for i, one in enumerate(entities):
            for other in entities[i + 1:]:
                if len(raised) >= NEW_QUESTIONS_PER_TICK:
                    break
                score = max((matching.similarity(a, b)
                             for a in matching.known_names(one, name_key)
                             for b in matching.known_names(other, name_key)), default=0.0)
                if score < matching.PART_CEILING:
                    continue
                if matching.contradictions(one, {k: v for k, v in _plain(other).items()}):
                    continue  # they disagree about something: two people, not one record twice
                question = world.questions.raise_(
                    one, "maybe_the_same",
                    f"two records look like one person: {one.display_name()} and "
                    f"{other.display_name()}. The same one?",
                    options=["the same one", "different ones"],
                    involves=[other], touches=["identity"],
                )
                if question is not None:
                    raised.append(question)
    return f"asked about {len(raised)} possible duplicate(s)" if raised else None


def _links_without_rules(world) -> str | None:
    """Links the world keeps making but has no rules for.

    A `related` link is the world admitting it has no type for something: "godfather", "landlord's
    agent", "my physio". When the same label keeps coming back, that is a kind of link this life
    actually contains, and it is worth knowing how it behaves — is there one of them at a time,
    does it read the same from both ends, can it form a cycle? Those are the properties every
    other type declares, and declaring them is what lets the world check anything at all.

    Finding the candidates is deterministic and cheap, so it happens here. Working out the
    properties is not: it needs the model and a look at how the label is used, which is work for
    the agenda (docs/engine/architecture.md) and is stated as a proposal, never applied silently.
    """
    if "Related" not in world.classes:
        return None
    seen: dict = {}
    for link in world.all("Related", limit=None, history=True):
        label = str(getattr(link, "label", "") or "").strip().lower()
        if label:
            seen.setdefault(label, []).append(link)
    recurring = {label: links for label, links in seen.items() if len(links) >= 3}
    if not recurring:
        return None
    described = "; ".join(f"{label} ({len(links)}x)" for label, links in
                          sorted(recurring.items(), key=lambda pair: -len(pair[1]))[:5])
    return f"links used often but with no rules of their own: {described}"


def _remarks_said_twice(world) -> str | None:
    """The same remark recorded about several people, or about one person twice.

    What this job is *not*: grouping remarks by topic, so that "allergic to peanuts", "can't eat
    nuts" and "no shellfish" together propose a dietary attribute. That was tried and measured,
    and the measurement said no — in a multilingual embedding, short remarks about one topic sit
    0.46–0.61 apart while remarks about different topics sit at 0.49. There is no threshold that
    separates them, and a schema proposal built on that would be noise.

    Naming the *kind* of a remark is a judgement — work for the model, kept once per remark and
    then counted (docs/TODO.md). Embeddings do what they are good at here: finding what is
    plainly the same thing said twice, which is worth knowing on its own.
    """
    import json

    world.meanings.refresh(world)
    rows = [(subject, text, json.loads(vector)) for subject, text, vector in
            world.store.conn.execute(
                "SELECT subject, text, vector FROM meanings WHERE kind = 'comment' AND model = ?",
                (world.meanings.model.name,))]
    if len(rows) < 4:
        return None
    groups: list = []
    for subject, text, vector in rows:
        for group in groups:
            if _alike(vector, group[0][2]) >= ALIKE:
                group.append((subject, text, vector))
                break
        else:
            groups.append([(subject, text, vector)])
    worth = [(len(group), group[0][1]) for group in groups if len(group) > 1]
    worth.sort(reverse=True)
    if not worth:
        return None
    described = "; ".join(f"{count}x \"{text[:44]}\"" for count, text in worth[:3])
    return f"the same remark recorded more than once — {described}"


def _alike(one: list, other: list) -> float:
    return sum(a * b for a, b in zip(one, other))


def _tags_whose_time_is_up(world) -> str | None:
    """Tags whose period has ended, taken off the things that carry them.

    A tag put on until the end of the quarter stops holding when the quarter does, and nobody
    writes anything that day. So somebody has to notice: the statement knows its period, the
    entity is what everything reads tags from, and this is where the two are brought back
    together. Nothing is deleted — the tag simply stops being one of this thing's tags."""
    from terraweaver import tags as tagging

    moment = datetime.now(timezone.utc).replace(tzinfo=None)
    changed = []
    for statement in world.facts.with_slot("tags"):
        if statement.valid_until is None or statement.valid_until > moment:
            continue
        try:
            entity = world.store.load(statement.subject, world.classes)
        except KeyError:
            continue
        values = statement.value if isinstance(statement.value, list) else [statement.value]
        stale = {tagging.canonical(v) for v in values if isinstance(v, str)}
        if stale & {tagging.canonical(t) for t in tagging.tags_of(entity)}:
            entity._show_tags()
            changed.append(f"{', '.join(sorted(stale))} off {entity.display_name()}")
    return "tags whose time was up: " + "; ".join(changed[:4]) if changed else None


def _tags_worth_reviewing(world) -> str | None:
    """Tags that have grown since anyone last considered them, and tags written several ways.

    A tag is the loosest thing in the world and the first to rot: `job-search`, `job search` and
    `work` end up as three categories that don't find each other. What the review means — are
    these one idea, has this one drifted, should that one be split — is the model's judgement on
    the agenda. This says where to look, from what changed."""
    from terraweaver import tags as tagging

    due = tagging.due_for_review(world)
    ways = tagging.written_several_ways(world)
    lines = []
    if due:
        lines.append("grown since last looked at: " +
                     "; ".join(f"{tag} ({now} now, {before} then)" for tag, now, before in due[:3]))
    if ways:
        lines.append("written several ways: " +
                     "; ".join(f"{tag} as {', '.join(spellings)}" for tag, spellings in ways[:3]))
    return " | ".join(lines) if lines else None


def _unused_attributes(world) -> str | None:
    """What the class offers and nobody fills. Not removed — counted: a schema grows and shrinks
    on evidence, and this is where the evidence accumulates (docs/engine/schema-growth.md)."""
    idle = []
    for name, cls in world.classes.items():
        if "relation" in cls._spec:
            continue
        entities = world.all(name, limit=None, history=True)
        if len(entities) < 5:
            continue  # too few to conclude anything
        for attr in cls._spec["attributes"]:
            if "derived" in attr or attr["name"] in ("id", "created_at", "accessed_at"):
                continue
            if all(not getattr(e, attr["name"], None) for e in entities):
                idle.append(f"{name}.{attr['name']}")
    return f"never filled by anyone: {', '.join(sorted(idle)[:8])}" if idle else None


def _plain(entity) -> dict:
    """An entity's own values, without references or the world's bookkeeping."""
    out = {}
    for attr in type(entity)._spec["attributes"]:
        if "derived" in attr or attr["type"].startswith(("ref:", "list[")):
            continue
        value = getattr(entity, attr["name"], None)
        if value is not None:
            out[attr["name"]] = value
    return out


JOBS = [
    Job("settle", timedelta(hours=1), _settle_moot_questions,
        "close doubts whose reason has gone"),
    Job("duplicates", timedelta(days=1), _spot_duplicates,
        "ask about records that look like one person"),
    Job("idle-attributes", timedelta(days=7), _unused_attributes,
        "count what the classes offer and nobody fills"),
    Job("loose-links", timedelta(days=3), _links_without_rules,
        "find links used often that no type has rules for"),
    Job("tags-expired", timedelta(hours=12), _tags_whose_time_is_up,
        "take off tags whose period has ended"),
    Job("tags", timedelta(days=2), _tags_worth_reviewing,
        "say which tags have moved enough to be worth another look"),
    Job("said-twice", timedelta(days=3), _remarks_said_twice,
        "find the same remark recorded more than once"),
]


class Ticks:
    def __init__(self, store):
        self.store = store
        store.conn.executescript(SCHEMA)

    def due(self, now: datetime | None = None) -> list[Job]:
        now = now or datetime.now(timezone.utc)
        out = []
        for job in JOBS:
            row = self.store.conn.execute(
                "SELECT at FROM tick_runs WHERE job = ? ORDER BY id DESC LIMIT 1", (job.name,)).fetchone()
            if row is None or datetime.fromisoformat(row[0]) + job.every <= now:
                out.append(job)
        return out

    def record(self, job: Job, took_ms: int, note: str | None) -> None:
        self.store.conn.execute(
            "INSERT INTO tick_runs (job, at, took_ms, note) VALUES (?, ?, ?, ?)",
            (job.name, datetime.now(timezone.utc).isoformat(), took_ms, note),
        )
        self.store.conn.commit()

    def history(self, limit: int = 20) -> list[dict]:
        rows = self.store.conn.execute(
            "SELECT job, at, took_ms, note FROM tick_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"job": j, "at": at, "took_ms": ms, "note": note} for j, at, ms, note in rows]


def tick(world, ticks: Ticks, budget_seconds: float = 20.0, force: bool = False) -> dict:
    """Run what is due, within the budget. Safe to call more often than anything is due."""
    started = time.monotonic()
    did, skipped = [], []
    for job in (JOBS if force else ticks.due()):
        if time.monotonic() - started > budget_seconds:
            skipped.append(job.name)  # it stays due; the next tick picks it up
            continue
        at = time.monotonic()
        try:
            note = job.run(world)
        except Exception as exc:  # noqa: BLE001 - a broken job must not stop the rest
            note = f"failed: {type(exc).__name__}: {exc}"
        took = int((time.monotonic() - at) * 1000)
        ticks.record(job, took, note)
        if note:
            did.append({"job": job.name, "note": note, "took_ms": took})
    return {"ran": did, "left_for_next_time": skipped,
            "took_ms": int((time.monotonic() - started) * 1000)}
