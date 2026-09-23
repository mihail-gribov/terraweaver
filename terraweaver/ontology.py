"""Loads class specs from ontology/core/*.json and builds real Python classes from them.

Attributes come purely from the JSON spec (generic). Method bodies are not derivable
from a signature + description alone, so they are looked up in `terraweaver.impls`
by (class_name, method_name); a method with no registered implementation gets a stub
that raises NotImplementedError, so gaps fail loudly instead of silently no-op-ing.
"""
import json
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Policy hook called before an attribute of an already-known entity is overwritten.
# Installed by the world layer; may raise to refuse the write. Kept as a hook rather
# than an import so the object model stays independent of the consistency layer.
_WRITE_GUARD = None
_FILLING = False
_TRUSTED = False
# The world the classes currently belong to, so `Person.find(...)` can reach it without
# every class having to be handed a store.
_WORLD = None

# Held by every entity, outside the JSON specs, and maintained by the machinery itself.
_MANAGED_ATTRS = ("id", "created_at", "accessed_at", "valid_from", "valid_until",
                  "from_is", "until_is")

# Counts what a running script actually touched. "Did the answer come from the world, or was
# it typed?" can't be judged from the text — but it can be measured at the source.
_TRACK = False
ACCESS = {"entity_reads": 0, "world_queries": 0, "world_writes": 0}
# Entities changed while recording, keyed by id(): a script's writes have to be persisted even
# when the changed object isn't bound to any variable (`Vacancy.find(...).matches[0].apply()`).
# Keyed by object identity because an entity's hash changes once it receives an id.
_CHANGED: "Recording | None" = None
# The ones that are stored as values (id is the row key, not a value).
# `from_is`/`until_is` say which side of its date a bound is on: "exact" unless somebody said
# "before" or "after". Kept beside the date rather than folded into it, because a date that
# has swallowed a "before" is indistinguishable from one that was known, and the whole point
# of taking the word was not to lose it.
MANAGED_VALUE_ATTRS = ("created_at", "accessed_at", "valid_from", "valid_until",
                       "from_is", "until_is")


def set_write_guard(guard) -> None:
    global _WRITE_GUARD
    _WRITE_GUARD = guard


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def set_world(world) -> None:
    global _WORLD
    _WORLD = world


def world_if_bound():
    """The world, or None while a fixture is still being built without one."""
    return _WORLD


def current_world():
    if _WORLD is None:
        raise RuntimeError("no world is bound: this class isn't attached to a world yet")
    return _WORLD


@contextmanager
def track_access():
    """Count world contact for the duration of a script."""
    global _TRACK
    before = dict(ACCESS)
    ACCESS.update({key: 0 for key in ACCESS})
    _TRACK = True
    try:
        yield ACCESS
    finally:
        _TRACK = False
        for key, value in before.items():
            ACCESS[key] += value


class Recording:
    """What a block of code did to the world, entity by entity.

    changed — every entity whose attributes were set, with the attribute names;
    found   — entities picked out as "the one meant" by get(). Keyed by id(), not the entity's
    hash, which changes once it receives an id.
    """

    def __init__(self):
        self.changed: dict[int, Any] = {}
        self.attrs: dict[int, set] = {}
        self.found: dict[int, Any] = {}
        # Entities a query handed back, as distinct from the one get() settled on. Only the
        # world's own doors put anything here, which is what makes it usable as evidence: a
        # variable left over from a loop looks exactly like a choice, and this does not.
        self.looked_up: dict[int, Any] = {}
        self.remarks: list[str] = []  # comments added, forgotten or confirmed, as the host should read them
        self.assumed: list[str] = []  # identities taken from what the user settled before
        self.hints: list[str] = []  # what the world suggests about a write that went through
        self.questions: list[str] = []  # doubts recorded about an entity, open until the user answers
        self.ask_now: list[str] = []  # doubts this run's reads actually depend on
        # The first link of each type made in this run, as the sentence the world reads it as.
        self.readings: dict[str, str] = {}


@contextmanager
def record_changes():
    """Collect every entity whose attributes change inside the block."""
    global _CHANGED
    previous = _CHANGED
    _CHANGED = Recording()
    try:
        yield _CHANGED
    finally:
        _CHANGED = previous


@contextmanager
def not_recording():
    """Suspend change recording — loading from storage fills attributes but changes nothing."""
    global _CHANGED
    previous = _CHANGED
    _CHANGED = None
    try:
        yield
    finally:
        _CHANGED = previous


@contextmanager
def filling_from_record():
    """Attributes being filled from what is stored, so nothing written here replaced anything.

    A rebuild sets every declared attribute to its empty form and then puts the record's value
    on top, and a relation's class carries its own kind as a class attribute — so the value the
    record's value "replaced" is scaffolding that was never true of anything. Written to the
    history table it read as a past this thing never had, two rows deep and growing by two on
    every rebuild.
    """
    global _FILLING
    was, _FILLING = _FILLING, True
    try:
        yield
    finally:
        _FILLING = was


def filling() -> bool:
    return _FILLING


def _note_changed(entity, attr: str | None = None) -> None:
    if _CHANGED is not None:
        _CHANGED.changed[id(entity)] = entity
        if attr is not None:
            _CHANGED.attrs.setdefault(id(entity), set()).add(attr)


def note_looked_up(entities) -> None:
    """Entities a query returned — evidence of what the host actually asked the world for."""
    if _CHANGED is None:
        return
    for entity in (entities if isinstance(entities, (list, tuple)) else [entities]):
        if getattr(entity, "id", None) is not None:
            _CHANGED.looked_up[id(entity)] = entity


def note_found(entity) -> None:
    if _CHANGED is not None:
        _CHANGED.found[id(entity)] = entity


def note_assumed(text: str) -> None:
    if _CHANGED is not None and text not in _CHANGED.assumed:
        _CHANGED.assumed.append(text)


def note_first_reading(type_name: str, sentence: str) -> None:
    """The sentence a type's first link makes — read back together when the task closes."""
    if _CHANGED is not None:
        _CHANGED.readings[type_name] = sentence


def note_hint(text: str) -> None:
    if _CHANGED is not None and text not in _CHANGED.hints:
        _CHANGED.hints.append(text)


_OPEN_TOKENS: dict = {}


def set_open_tokens(tokens: dict) -> None:
    """What every open question hangs over, by entity id: {id: {"relation:service": line}}.
    Refreshed once per run so the checks below cost a dict lookup, not a query."""
    global _OPEN_TOKENS
    _OPEN_TOKENS = tokens or {}


def ask_if_questioned(entity, token: str) -> None:
    """A read that depends on something a question hangs over can't be answered cleanly: say so
    here, while the host is holding the answer, rather than in a list it may never look at."""
    if not _OPEN_TOKENS:
        return
    try:  # never through getattr: this is called from inside __getattribute__
        entity_id = object.__getattribute__(entity, "id")
    except AttributeError:
        return
    line = _OPEN_TOKENS.get(entity_id, {}).get(token)
    if line and _CHANGED is not None and line not in _CHANGED.ask_now:
        _CHANGED.ask_now.append(line)


_STATING = ("agent", None)


@contextmanager
def stating(source: str, run_id: str | None = None):
    """Whose word the writes inside this block are, and what run they belong to.

    The default is `agent`: everything that arrives through the assistant, whether it was
    relayed or concluded. The world can't tell those apart and doesn't try — what the assistant
    passes on is the assistant's responsibility. The world's own work says `stating("world",
    ticket)`, and what it writes then carries the lowest standing and comes back off in one
    move."""
    global _STATING
    before = _STATING
    _STATING = (source, run_id)
    try:
        yield
    finally:
        _STATING = before


def stated_by() -> tuple:
    return _STATING


def note_question(text: str) -> None:
    if _CHANGED is not None and text not in _CHANGED.questions:
        _CHANGED.questions.append(text)


def note_remark(text: str) -> None:
    if _CHANGED is not None:
        _CHANGED.remarks.append(text)


def note_world_call(kind: str) -> None:
    if _TRACK:
        ACCESS[kind] = ACCESS.get(kind, 0) + 1


@contextmanager
def trusted_writes():
    """Writes made by the machinery itself (loading, applying a settled decision)."""
    global _TRUSTED
    previous = _TRUSTED
    _TRUSTED = True
    try:
        yield
    finally:
        _TRUSTED = previous


# The least a world can be. A Thing is somewhere to put anything at all, so nothing waits for a
# class to exist; a Related is a link with no type yet, so no fact waits for a relation type. And
# every world is between two parties who are in it as entities — without a Person and an Agent
# there is no "me" and no "you", and "my dentist" has no "my".
#
# Everything else — Organization, Place, Event, Vacancy — is filling: useful, probably, but it
# has to earn its place by making the work easier than the base alone, or it is not help but
# noise. `Idea` was noise: seventy things were forced into a class meant for notes, ten were lost
# saying so, and the rest got through by inventing what the host did not know.
# Task is in the base because the boundary has to exist before any work does: a world
# that could be written to without one is a world where facts land outside every task,
# which is the state every check added here was built to end.
BASE_CLASSES = ("Thing", "Related", "PartOf", "Kind", "Person", "AIAgent", "Task")


# What each base class keeps. A Person in the base is a name, not a name with an employer and a
# job title: those read from relation types and other classes the base hasn't got, and an
# attribute that presumes a type is filling however useful it is. What every class gets anyway —
# descriptions, tags, and the one-word reading of them — is kept, because that is how anything
# says what it has no attribute for.
BASE_KEEPS = {
    "Person": ("full_name", "aliases"),
    "AIAgent": ("name", "owner", "character"),      # the soul file's body goes into character
    "Thing": ("name", "aliases", "nature"),
    "Related": ("label", "nature"),
    "PartOf": (),
    "Kind": (),
    "Task": ("stated", "mode", "touched", "runs", "closed_as"),
}
_ALWAYS = ("descriptions", "tags", "notes", "description")


def base_specs(ontology_dir: Path) -> dict[str, dict[str, Any]]:
    """The least a world can be: the base classes, each cut back to what a world needs of it."""
    specs = load_specs(ontology_dir, grown_dir=Path("/nonexistent"))
    out = {}
    for name in BASE_CLASSES:
        spec = dict(specs[name])
        keep = BASE_KEEPS.get(name, ()) + _ALWAYS
        spec["attributes"] = [dict(a) for a in spec["attributes"] if a["name"] in keep]
        spec["methods"] = []
        out[name] = spec
    return out


def load_specs(ontology_dir: Path, grown_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """The classes we fixed, plus whatever the world has added to them.

    The core files are read as they are and never written to; additions live beside them and are
    merged in here (growth.py), so reading ontology/core/ still tells you what a class is."""
    from terraweaver import growth

    specs = {}
    for path in sorted(ontology_dir.glob("*.json")):
        spec = json.loads(path.read_text())
        specs[spec["name"]] = spec
    grown = growth.load_grown(grown_dir if grown_dir is not None else ontology_dir.parent / "grown")
    return growth.apply_growth(specs, grown) if grown else specs


class Entity:
    """Common ancestor of every class in the world.

    Everything each entity shares lives here instead of being regenerated per class:
    identity, equality by id, the write guard, declared-type checking and inverse
    relationships. It also gives the rest of the system one honest way to ask "is this a
    world entity?" — isinstance(x, Entity) — instead of feeling for an attribute, which
    is how `str.title` once got mistaken for an entity's title.

    Subclasses carry only what genuinely differs: their `_spec` and their methods.
    """

    _spec: dict[str, Any] = {"attributes": [], "methods": []}
    _classes: dict[str, type] = {}

    def __init__(self, **kwargs):
        # Every entity gets an id (None until a Store assigns or loads one), so any class
        # is persistable without the JSON spec having to declare it.
        self.id = kwargs.pop("id", None)
        # When it entered the world, and when it was last worked with. Together these are
        # what makes the world a context: who and what the conversation has been about
        # lately, rather than an undifferentiated pile of entities.
        now = datetime.now(timezone.utc).replace(tzinfo=None)  # one form of time: see timeutil
        self.created_at = kwargs.pop("created_at", None) or now
        self.accessed_at = kwargs.pop("accessed_at", None) or now
        # When it holds in the world: [valid_from, valid_until). None on either side is open —
        # most things exist from when they're recorded and for good. Nothing is deleted when a
        # period ends; the entity becomes history.
        self.valid_from = kwargs.pop("valid_from", None)
        self.valid_until = kwargs.pop("valid_until", None)
        class_name = type(self).__name__
        missing = []
        # Every declared name, derived ones included: `organization=` is a real word for a
        # Person, and treating it as unknown once "corrected" it to `location`.
        spec_attrs = [a["name"] for a in type(self)._spec["attributes"]]
        for given in [k for k in list(kwargs) if k not in spec_attrs]:
            from terraweaver import matching

            calls_it = matching.NAME_KEYS.get(class_name)
            synonyms = {w: calls_it for w in ("name", "title", "label", "full_name")} if calls_it else {}
            meant = did_you_mean(given, spec_attrs, synonyms)
            if meant and meant not in kwargs:
                kwargs[take_as(f"{class_name}(...)", given, meant)] = kwargs.pop(given)
        # An older spelling given at construction is folded into the one place it belongs before
        # anything is built. Left to the property, it would be applied after the entity is saved
        # — outside whatever is recording the run, so a link the world worked out came back with
        # a description that looked like something the user had said.
        for attr in type(self)._spec["attributes"]:
            source = str(attr.get("derived", ""))
            if source.startswith("self.") and attr["name"] in kwargs:
                held = source.split(".", 1)[1]
                given = kwargs.pop(attr["name"])
                if given is not None:
                    kwargs[held] = list(kwargs.get(held) or []) + [given]
        for attr in type(self)._spec["attributes"]:
            name = attr["name"]
            if "derived" in attr:
                if name in kwargs:
                    if not attr.get("settable"):
                        raise TypeError(_derived_message(class_name, attr))
                    # Relations need both ends stored; the world applies these after saving.
                    self.__dict__.setdefault("_deferred", {})[name] = kwargs.pop(name)
                continue
            if name in kwargs:
                setattr(self, name, kwargs.pop(name))
            elif attr.get("required") and "default" not in attr:
                missing.append(attr)
            else:
                default = attr.get("default")
                if default is None and attr["type"].startswith("list["):
                    default = []
                setattr(self, name, default)
        missing = _gaps_are_not_refusals(self, class_name, missing)
        if missing or kwargs:
            # Both at once, and with the near miss named. Reported one at a time, a host told
            # only "missing title" adds a title and keeps its `name=` — and learns on the next
            # try that the first answer was incomplete. Once cost a whole scenario: the events
            # went in under `name=`, were refused, and came back with no title at all.
            raise TypeError(_construction_problem(class_name, type(self)._spec,
                                                  [a["name"] for a in missing], kwargs))

    # --- what every class in the world can do ---

    @classmethod
    def all(cls, limit: int | None = 50, *, any_time: bool = False, history: bool = False) -> list:
        """Entities of this class, most recently worked with first — the ones that hold now;
        any_time=True adds those whose period has ended or hasn't started."""
        return current_world().all(cls, limit=limit, history=history or any_time)

    @classmethod
    def where(cls, **conditions) -> list:
        """Entities of this class answering all the conditions at once — attributes, a link,
        tags, words, meaning. `Person.where(...)` is `world.where(Person, ...)`; the world's own
        one is for a question that isn't about a single kind of thing (selecting.py)."""
        return current_world().where(cls, **conditions)

    @classmethod
    def find(cls, *, any_time: bool = False, history: bool = False, **attrs):
        """Entities of this class matching the attributes, best match first.

        A by-name lookup that isn't a certain match returns a NeedsResolution rather than
        ranked guesses — picking one would be deciding who was meant.
        """
        return current_world().find(cls, history=history or any_time, **attrs)

    @classmethod
    def get(cls, **attrs):
        """The existing entity the user means. Never creates; nothing found is a loud error."""
        return current_world().get(cls, **attrs)

    @classmethod
    def new(cls, *, starts=None, until=None, ttl=None, permanent: bool = False,
            every=None, lasting=None, **attrs):
        """A new entity. If one just like it already exists, the user is asked before creating."""
        made = current_world().new(cls, starts=starts, until=until, ttl=ttl, permanent=permanent,
                                   **attrs)
        return _also_repeats(made, every, lasting, starts, until)

    @classmethod
    def ensure(cls, *, starts=None, until=None, ttl=None, permanent: bool = False,
               every=None, lasting=None, **attrs):
        """Existing or new — for when you genuinely can't tell which."""
        found = current_world().ensure(cls, starts=starts, until=until, ttl=ttl,
                                       permanent=permanent, **attrs)
        return _also_repeats(found, every, lasting, starts, until)

    def keep(self, *, starts=None, until=None, ttl=None, permanent: bool = False,
             every=None, lasting=None) -> None:
        """Set when this entity holds: starts=date, until=date / ttl=timedelta, permanent=True.

        `every=` makes it cyclic instead of one-off — see repeat(), which this passes through to."""
        if starts is not None or until is not None or ttl is not None or permanent:
            current_world().set_period(self, starts=starts, until=until, ttl=ttl,
                                       permanent=permanent)
        elif every is None:
            current_world().set_period(self)  # says, in one place, what a period needs
        if every is not None:
            self.repeat(every=every, lasting=lasting, starts=starts, until=until)

    def repeat(self, *, every, lasting=None, starts=None, until=None, tag: str | None = None):
        """Say that this happens again and again: `every="2 weeks"`, `every="month"`, a timedelta.

        A repeat is a rule, stated once — an anchor (when the first one is, `starts=`), a step,
        how long each one lasts (`lasting=`, left out for a moment rather than a stretch) and
        when the series stops (`until=`). It is kept in the same period table as every one-off
        period, as one cyclic row rather than a thousand rows, and read with the same words:
        entity.occurrences(...), entity.next_occurrence(), world.where(tagged=..., at=...).

            standup.repeat(every="day", lasting=timedelta(minutes=30))
            michael.repeat(every="3 weeks", lasting=timedelta(days=7), tag="on-call")
            visa.repeat(every="5 years")
        """
        from terraweaver import periods, recurrence, tags as tagging, timeutil

        step = recurrence.read(every)  # refuses here, where the host can still fix it
        world = current_world()
        if self.id is None:
            world.save(self)
        anchor = timeutil.check_start(starts) or self._anchor()
        length = None
        if lasting is not None:
            length = lasting.total_seconds() / 86400 if hasattr(lasting, "total_seconds") else float(lasting)
        source, run_id = stated_by()
        rule = {"nature": "tags" if tag else "valid",
                "value": tagging.canonical(tag) if tag else None,
                "every": str(step), "lasting": length,
                "anchor": anchor.isoformat(),
                "ends": timeutil.check_start(until).isoformat() if until is not None else None}
        world.facts.state(self.subject_id, periods.REPEATS, rule, source=source, run_id=run_id,
                          class_name=type(self).__name__)
        periods.rebuild(world)
        note_hint(f"{self.display_name()}: {recurrence.describe(anchor, step, lasting, timeutil.check_start(until) if until is not None else None)}"
                  + (f" — tagged {tagging.canonical(tag)}" if tag else ""))
        return self

    def _anchor(self):
        """When the first one is, unless the host said: a dated attribute, else when it holds
        from, else now. A repeat has to start somewhere, and guessing badly is worse than asking,
        so the guess is only ever something this entity already says about itself."""
        from terraweaver import timeutil

        for attr in type(self)._spec["attributes"]:
            if attr["name"] in _MANAGED_ATTRS or attr.get("derived"):
                continue
            value = self.__dict__.get(attr["name"])
            if isinstance(value, datetime):
                return value
        return getattr(self, "valid_from", None) or timeutil.now()

    def occurrences(self, since=None, until=None, tag: str | None = None) -> list:
        """The times this happens inside a window — (starts, ends) pairs, ends None for a moment.

        A rule has no end, so a question about it needs one: `since` defaults to now and `until`
        to ninety days after that. Ask wider by saying so."""
        from terraweaver import periods, tags as tagging, timeutil

        world = current_world()
        start = timeutil.check_start(since) or timeutil.now()
        stop = timeutil.check_start(until) or (start + timedelta(days=90))
        found = periods.stretches(world, self.subject_id, "tags" if tag else "valid",
                                  tagging.canonical(tag) if tag else None, since=start, until=stop)
        return [(begins, ends) for _, begins, ends in found]

    def next_occurrence(self, after=None, tag: str | None = None):
        """When the next one is, or None if nothing repeats here (or the series is over)."""
        from terraweaver import periods, tags as tagging, timeutil

        return periods.next_time(current_world(), self.subject_id, "tags" if tag else "valid",
                                 tagging.canonical(tag) if tag else None,
                                 after=timeutil.check_start(after) or timeutil.now())

    def repeats(self) -> list[str]:
        """What repeats about this one, in words: one line per rule."""
        from terraweaver import periods, recurrence

        out = []
        for row in periods.cycles(current_world(), self.subject_id):
            said = recurrence.describe(row["starts"], row["every"], row["lasting"], row["until"])
            out.append(f"{row['value']}: {said}" if row["value"] else said)
        return out

    def expire(self, at=None) -> None:
        """It no longer holds from `at` (default: now). It stays in the world as history."""
        from terraweaver import timeutil
        current_world().set_period(self, until=at or timeutil.now())

    def history(self, attr: str) -> list:
        """The values this attribute has held, oldest first, each with when it stopped; the
        current one last."""
        declared = next((a for a in type(self)._spec["attributes"] if a["name"] == attr), None)
        if declared is not None and declared.get("derived") == "relation":
            from terraweaver import relations

            history = relations.DERIVED[(type(self).__name__, attr)][2]
            return history(self) if history else []
        return current_world().history.of(self, attr)

    def relate(self, other, kind: str, /, *, starts=None, until=None, ttl=None,
               permanent: bool = False, every=None, lasting=None, basis: list | None = None,
               **attrs):
        """Record that this entity stands in relation `kind` to `other`; returns the relation.

        A relation takes a period like anything else, and a cyclic one the same way: a cleaner
        every other week, a class every Tuesday term-time."""
        made = current_world().relate(self, other, kind, starts=starts, until=until, ttl=ttl,
                                      permanent=permanent, basis=basis, **attrs)
        return _also_repeats(made, every, lasting, starts, until)

    def relations(self, kind: str | None = None, *, any_time: bool = False, history: bool = False) -> list:
        """The relations this entity takes part in — of one type, or all."""
        from terraweaver import relations

        return relations.relations_of(current_world(), self, kind, history or any_time)

    def how_related(self, other, max_hops: int = 3) -> str | None:
        """How `other` is connected to this entity, in words: "Mark Stone is Michael's sibling in
        law: Michael → sister Olga → husband Mark Stone". None if nothing links them."""
        from terraweaver import relations

        return relations.how_related(current_world(), self, other, max_hops)

    def related(self, kind: str, *, any_time: bool = False, history: bool = False) -> list:
        """The entities at the other end of relations of `kind` (and the rest of a chain)."""
        from terraweaver import relations

        return relations.related(current_world(), self, kind, history or any_time)

    @property
    def expired(self) -> bool:
        """Whether its period has run out — the word hosts reach for on anything dated."""
        from terraweaver import timeutil

        until = getattr(self, "valid_until", None)
        return until is not None and timeutil.as_datetime(until) <= timeutil.now()

    @property
    def starts(self):
        """When it begins to hold (None: since it was recorded) — as given with starts=."""
        from terraweaver import timeutil

        return timeutil.moment(getattr(self, "valid_from", None))

    @property
    def until(self):
        """When it stops holding (None: no end) — as given with until= / ttl=."""
        from terraweaver import timeutil

        return timeutil.moment(getattr(self, "valid_until", None))

    def timeline(self, since=None, until=None) -> list:
        """Everything dated about this entity, oldest first: when it was recorded, when its
        period starts and ends, what its attributes were changed to and when, its dated remarks,
        and its relations starting and ending. One way to ask "what happened with this, and when"."""
        from terraweaver import relations, timeutil

        world = current_world()
        spec = type(self)._spec
        moments = [(self.created_at, f"recorded as {type(self).__name__} «{self.display_name()}»")]
        if getattr(self, "valid_from", None):
            moments.append((self.valid_from, "holds from here"))
        if getattr(self, "valid_until", None):
            moments.append((self.valid_until, "stops holding here"))
        for attr in spec["attributes"]:
            if "derived" in attr:
                continue
            value = getattr(self, attr["name"], None)
            if isinstance(value, datetime) and attr["name"] not in _MANAGED_ATTRS:
                moments.append((value, f"{attr['name']}"))
            for past in (world.history.of(self, attr["name"]) if attr["name"] not in _MANAGED_ATTRS else []):
                if past.until is not None:
                    moments.append((past.until, f"{attr['name']} was {_brief(past.value)} until here"))
        for spell in self.spells("tags"):
            moments.append((spell.starts, f"tagged {spell.value}"))
            if spell.until is not None:
                moments.append((spell.until, f"no longer tagged {spell.value}"))
        for comment in self.described(any_time=True):
            moments.append((comment.when or comment.recorded_at, f"remark: {comment.text}"))
        for relation in (relations.relations_of(world, self, None, True) if not isinstance(self, Relation_base()) else []):
            other = relation.other(self)
            what = relation.role_of(other) or type(relation)._spec["relation"]["kind"]
            moments.append((relation.valid_from or relation.created_at, f"{what}: {other.display_name()} — from here"))
            if relation.valid_until:
                moments.append((relation.valid_until, f"{what}: {other.display_name()} — until here"))
        start = timeutil.as_datetime(since) if since is not None else None
        end = timeutil.as_datetime(until) if until is not None else None
        # What repeats belongs on a timeline as the rule plus the ones inside the window asked
        # about: a series shown as its first occurrence reads as something that happened once.
        for said in self.repeats():
            moments.append((self.created_at, f"repeats — {said}"))
        if start is not None and end is not None:
            for begins, ends in self.occurrences(since=start, until=end):
                moments.append((begins, "one of these" + (f", until {timeutil.show(ends)}" if ends else "")))
        out = []
        for when, what in moments:
            at = timeutil.moment(when)
            if (start is None or at >= start) and (end is None or at <= end):
                out.append(Moment(at, what))
        return sorted(out, key=lambda m: m.when)

    def current(self) -> bool:
        """Whether this entity holds now."""
        from terraweaver import timeutil
        return timeutil.in_period(getattr(self, "valid_from", None), getattr(self, "valid_until", None), timeutil.now())

    def save(self) -> None:
        """Persist this entity and everything it references."""
        current_world().save(self)

    def become(self, what, when=None):
        """Say what this turned out to be, and read it as that from now on.

        A world starts without the word for everything in it. A book, a sport, a genre arrive as
        Things because nothing better exists yet; later the world has a class for them, and this
        is how they join it. Nothing is copied and nothing is re-read — the statements about it
        stay exactly where they were written, and only the class the image is built under
        changes, because the class was always a thing of the image and of the host's code.

        Told again it supersedes, so a wrong guess is corrected by saying the right one.
        """
        from terraweaver import assembly

        world = current_world()
        name = what if isinstance(what, str) else getattr(what, "__name__", str(what))
        if name not in world.classes:
            near = did_you_mean(name, list(world.classes))
            raise ValueError(f"there is no class {name!r} here"
                             + (f" — did you mean {near!r}?" if near else "")
                             + ". Define one with world.authoring.define(...) first.")
        if name == type(self).__name__:
            return self
        world.facts.state(self.subject_id, assembly.IS_A, name, valid_from=when,
                          class_name=type(self).__name__)
        return world.retype(self, name)

    def describe(self, text: str, when=None, tentative: bool = False, until=None, ttl=None,
                 starts=None, permanent: bool = False):
        """Say something about this entity in words — for what its attributes have no place for.

        It goes where every text about it goes, into `descriptions`, and is read back with
        `described(...)`. One word for one place: this used to be called `comment` while landing
        in descriptions, which is exactly the kind of discrepancy a host pays for.

        `starts=` is taken as `when=`: everywhere else in the world that word opens a period, and
        a remark's period opens on the day it is about. One vocabulary, however the host reaches
        for it."""
        return current_world().comments.add(self, text, when=when if when is not None else starts,
                                            tentative=tentative, until=until, ttl=ttl, permanent=permanent)

    @property
    def subject_id(self):
        """This entity's identity in the record — where new statements about it are attached.

        An entity has two: `id`, which is the image built from statements, and this, the subject
        those statements are about. They are the same until two subjects turn out to be one
        person, and then the image keeps both while every new word still lands on one of them.
        """
        return self.__dict__.get("_subject") or self.id

    def path_to(self, other, max_hops: int = 4, kind: str | None = None):
        """How this entity and that one are connected, step by step — or None if nothing links
        them. The world walks the links that were written down; what the chain means is yours."""
        from terraweaver import graph

        return graph.path_to(current_world(), self, other, max_hops, kind)

    def near(self, hops: int = 2, kind: str | None = None) -> list:
        """Everything within a few links, nearest first, each with the way there."""
        from terraweaver import graph

        return graph.near(current_world(), self, hops, kind)

    def shared_with(self, other, kind: str | None = None) -> list:
        """What both are connected to — the people, companies or places in common."""
        from terraweaver import graph

        return graph.shared_with(current_world(), self, other, kind)

    def reaches(self, kind: str, up: bool = True) -> list:
        """Everything along one kind of link, as far as it goes: a department tree, a family line."""
        from terraweaver import graph

        return graph.reaches(current_world(), self, kind, up)

    def _no_world(self) -> bool:
        world = world_if_bound()
        return world is None or getattr(world, "facts", None) is None

    def add(self, slot: str, *texts: str, starts=None, until=None, ttl=None,
            permanent: bool = False, every=None, lasting=None):
        """Put one more text into a dated list — a description, a tag, anything of that type.

        A `list[text]` slot holds several free texts, and each one is a statement of its own:
        said when it was said, holding for as long as it holds, ended without anything being
        deleted. That is what makes prose part of this world rather than beside it — a second
        description does not overwrite the first, and a description that stopped being true
        stops holding on a date instead of disappearing.

            anna.add("descriptions", "does cell chemistry at a battery startup")
            acme.add("descriptions", "hiring freeze", starts=date(2026, 3, 1))
            mike.add("tags", "on-call", every="3 weeks", lasting=timedelta(days=7))
        """
        slot = _check_slot(self, slot) or slot
        tidy = _texts_as(slot)
        if self._no_world():
            with trusted_writes(), not_recording():
                object.__setattr__(self, slot, tidy(list(getattr(self, slot, None) or []) + list(texts)))
            return self
        world = current_world()
        source, run_id = stated_by()
        period = {}
        if starts is not None or until is not None or ttl is not None or permanent:
            from terraweaver.world import _period

            period = _period(starts, until, ttl, permanent)
        if self.id is None:
            world.save(self)
        # Stated as written, shown in one form: a tag typed three ways is one tag to compare
        # by and three spellings in the record, which is what makes the tidying rule changeable.
        for text in _as_written(texts):
            if every is not None:
                self.repeat(every=every, lasting=lasting, tag=text if slot == "tags" else None,
                            starts=period.get("valid_from") or starts,
                            until=period.get("valid_until"))
                continue
            world.facts.state(self.subject_id, slot, text, source=source, run_id=run_id,
                              class_name=type(self).__name__,
                              valid_from=period.get("valid_from"),
                              valid_until=period.get("valid_until"))
        self._show(slot)
        return self

    def drop(self, slot: str, *texts: str):
        """Take a text out of a dated list: it stops holding now, and the record keeps that it did."""
        slot = _check_slot(self, slot) or slot
        tidy = _texts_as(slot)
        if self._no_world():
            gone = set(tidy(texts))
            with trusted_writes(), not_recording():
                object.__setattr__(self, slot,
                                   [t for t in (getattr(self, slot, None) or []) if t not in gone])
            return self
        world = current_world()
        wanted = set(tidy(texts))
        for statement in world.facts.about(self.subject_id, slot):
            if statement.valid_until is not None:
                continue
            values = statement.value if isinstance(statement.value, list) else [statement.value]
            if any(t in wanted for t in tidy([v for v in values if isinstance(v, str)])):
                world.facts.end(statement.id)
        self._show(slot)
        return self

    def _show(self, slot: str) -> None:
        """Put what holds now into the entity, which is where everything reads the slot from."""
        world = current_world()
        moment = datetime.now(timezone.utc).replace(tzinfo=None)
        holding = []
        for statement in world.facts.about(self.subject_id, slot):
            if not statement.holds_at(moment):
                continue
            values = statement.value if isinstance(statement.value, list) else [statement.value]
            holding += [v for v in values if isinstance(v, str)]
        with trusted_writes(), not_recording():
            object.__setattr__(self, slot, _texts_as(slot)(holding))
        world.store.save(self)

    def _set_many(self, slot: str, wanted) -> None:
        """"These are the texts now": state what is new, end what is no longer named."""
        tidy = _texts_as(slot)
        world = world_if_bound()
        if world is None or getattr(world, "facts", None) is None:
            with trusted_writes(), not_recording():
                object.__setattr__(self, slot, tidy(wanted))
            return
        from terraweaver import periods

        periods.rebuild_for(world, self.subject_id, slot)
        # What the record says holds, never what the entity happens to carry: at creation the
        # entity already carries what was asked for, and taking that as "already stated" left
        # every tag given to Class.new() unrecorded.
        now_holding = set(tidy(periods.holding(world, self.subject_id, slot)))
        given = _as_written(wanted)          # as said, in the order said
        asked = tidy(given)                  # the same, in the form things are compared in
        fresh = [text for text in given if (tidy([text]) or [None])[0] not in now_holding]
        if fresh:
            self.add(slot, *fresh)
        gone = [text for text in now_holding if text not in asked]
        if gone:
            self.drop(slot, *gone)
        self._show(slot)

    def tag(self, *names: str, starts=None, until=None, ttl=None, permanent: bool = False,
            every=None, lasting=None):
        """Put a tag on, for a while, for good, or every so often.

        A tag is often true of something for a season and not after: `q3-push`, `apartment-hunt`,
        `on-loan`. Each one is stated on its own, so it carries a period like anything else in
        this world — and when the period is over it simply stops being one of this thing's tags,
        without anybody deleting anything.

        `every=` makes that period cyclic instead of one-off — on call every third week, closed
        every August. The rule is stated once and the period table keeps it as one row; see
        repeat() below, which this passes through to.
        """
        return self.add("tags", *names, starts=starts, until=until, ttl=ttl,
                        permanent=permanent, every=every, lasting=lasting)

    def untag(self, *names: str):
        """Take a tag off: it stops holding now, and the record keeps that it once did.

        Ended, not retracted — it was true of this thing for a while, and asking later what it
        was tagged in June should still answer. Tag it again next year and that is a second
        spell, not a contradiction of the first."""
        return self.drop("tags", *names)

    def spells(self, slot: str = "tags", value: str | None = None) -> list:
        """Every stretch of time something held of this one — all of them, in order.

        A tag put on in March, taken off in September and put back in November is three facts and
        one word, and a world that only knows the last one cannot answer "what was this in June".
        Reads out of the statements, where the periods are; no separate account is kept.
        """
        from terraweaver import periods, timeutil

        world = current_world()
        periods.rebuild_for(world, self.subject_id, slot)  # exactly what the statements say
        return [Spell(one, timeutil.moment(starts), timeutil.moment(until), "record")
                for one, starts, until in periods.stretches(world, self.subject_id, slot, value)]

    def _set_tags(self, wanted) -> None:
        self._set_many("tags", wanted)

    def _show_tags(self) -> None:
        self._show("tags")

    def suggest_tags(self, limit: int = 3) -> list:
        """Tags worth considering for this one, from whatever else reads like it. Candidates and
        how strongly they read, nothing applied — what earns a tag is yours to decide."""
        from terraweaver import tags as tagging

        return tagging.suggest(current_world(), self, limit)

    def similar(self, limit: int = 5) -> list:
        """Whatever else in the world reads like what is said about this one. Candidates only —
        nothing here decides who someone is."""
        return current_world().meanings.similar(current_world(), self, limit)

    def why(self, attr: str):
        """What the world worked out for this attribute, and what it rests on — for when the user
        asks why you think so. It comes back as the judgement, the statements behind it, and
        whether it has gone stale; putting that into a sentence is yours. Nothing comes back for
        an attribute someone simply told us: then the answer is that they did."""
        world = current_world()
        found = world.facts.why(self.id, attr) if getattr(self, "id", None) else None
        if found is None:
            return None
        judgement, basis = found
        return Judgement(judgement.value, judgement.stated_at, judgement.run_id,
                         world.facts.stale(judgement), basis)

    def question(self, text: str, options=(), about: str | None = None) -> Any:
        """Record something about this entity that doesn't add up and isn't yours to decide —
        "two phone numbers, which is current?". It stays open until the user answers it.
        `about` is the attribute or relation it hangs over ("phone", "service"): a later read of
        that one is told it can't be answered cleanly, instead of quietly returning one side."""
        touches = []
        if about:
            touches = [f"attr:{about}"] if any(a["name"] == about for a in type(self)._spec["attributes"]) \
                else [f"relation:{about}"]
        return current_world().questions.raise_(self, "noticed", text, options=options,
                                                touches=touches, by="host")

    def questions(self, include_closed: bool = False) -> list:
        """What's open about this entity. Each has .text, .options, .answer("…"), .drop()."""
        return current_world().questions.of(self, include_closed=include_closed)

    def described(self, since=None, until=None, contains: str | None = None,
                  include_expired: bool = False, any_time: bool = False) -> list:
        """What has been said about this one in words, newest first — each with when it happened,
        how long it holds and whether it was only tentative. any_time=True adds what has run out."""
        return current_world().comments.of(self, since=since, until=until, contains=contains,
                                           include_expired=include_expired or any_time)

    def touch(self) -> None:
        """Mark that this entity was just worked with — the moment, and one more time in the
        count that decides whose open questions are worth the user's attention (usage.py)."""
        with trusted_writes():
            self.accessed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        current_world().usage.record(self)
        ask_if_questioned(self, "identity")

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        # Reading an entity's attribute is contact with the world just as much as querying it
        # is: `report(owner.full_name)` makes no calls yet is perfectly grounded.
        if _TRACK and not name.startswith("_") and not callable(value):
            ACCESS["entity_reads"] += 1
            if _OPEN_TOKENS and name not in _MANAGED_ATTRS:
                ask_if_questioned(self, f"attr:{name}")
        # Times come back comparable with dates. `event.start_time >= today()` is the obvious
        # thing to write, and a plain datetime raises on it — one discarded run each time, for
        # nothing. Moment is a datetime, so everything else about it is unchanged.
        if isinstance(value, datetime) and type(value).__name__ not in ("Moment",) \
                and not name.startswith("_"):
            from terraweaver import timeutil

            return timeutil.moment(value)
        return value

    def display_name(self) -> str:
        """Short human handle for this entity."""
        for attr in ("full_name", "name", "title"):
            value = getattr(self, attr, None)
            if isinstance(value, str) and value:
                return value
        return self.id or "unsaved"

    def __repr__(self):
        # One level deep on purpose. A referenced entity is shown by its label, never by its
        # own repr: the world is a graph with cycles (person -> company -> employees -> person),
        # and Python's repr guard only covers containers, so recursing here blew the stack as
        # soon as the model got a few links deeper. It also makes output readable — the fully
        # expanded version buried the answer in nested brackets.
        fields = ", ".join(
            f"{a['name']}={_brief(getattr(self, a['name'], None))}" for a in type(self)._spec["attributes"]
        )
        period = _period_text(getattr(self, "valid_from", None), getattr(self, "valid_until", None))
        return f"{type(self).__name__}(id={self.id!r}, {fields}{period}{_remark_note(self)})"

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self):
        # Two instances loaded by separate Store.load_all() calls can represent the same row
        # without being the same object — hashing on the id makes them behave as one in
        # dicts and sets regardless.
        return hash((type(self).__name__, self.id)) if self.id is not None else object.__hash__(self)

    def __getattr__(self, name):
        """Only reached when the attribute isn't there — so it is the place to say what is.

        Reading `idea.name` where the class calls it `title` used to give Python's bare message
        and cost the statement. Writing it already said which word was meant; reading it should
        say the same thing.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        spec = type(self)._spec
        known = [a["name"] for a in spec.get("attributes", [])]
        from terraweaver import matching

        calls_it = matching.NAME_KEYS.get(type(self).__name__)
        synonyms = {w: calls_it for w in ("name", "title", "label", "full_name")} if calls_it else {}
        near = did_you_mean(name, known, synonyms)
        raise AttributeError(
            f"{type(self).__name__} has no {name!r}"
            + (f" — did you mean {near!r}? " if near else ". ")
            + (f"It has: {', '.join(known)}." if known else "")
            + " What none of them holds goes into a description: entity.describe(...).")

    def __setattr__(self, name, value):
        spec = type(self)._spec
        class_name = type(self).__name__
        if name not in _MANAGED_ATTRS and not name.startswith("_"):
            declared = next((a for a in spec["attributes"] if a["name"] == name), None)
            # An attribute the class doesn't have used to be accepted and then lost on save —
            # a write that looked fine and never happened.
            if declared is None:
                near = did_you_mean(name, [a["name"] for a in spec["attributes"]])
                if near:
                    setattr(self, take_as(class_name, name, near), value)
                    return
                raise AttributeError(
                    f"{class_name} has no attribute '{name}'"
                    + (f" — did you mean '{near}'? " if near else ". ")
                    + "Its attributes are: "
                    + ", ".join(a["name"] for a in spec["attributes"])
                    + ". What none of them holds goes into a dated remark: entity.describe(...."
                )
            if "derived" in declared:
                if declared.get("settable"):
                    object.__setattr__(self, name, value)  # the property's setter records it
                    return
                raise TypeError(_derived_message(class_name, declared))
            value = _check_type(class_name, spec, name, value) or value
            if (isinstance(value, list) and getattr(self, "id", None) is not None
                    and not _TRUSTED and name in dated_lists(spec)):
                # One way in, whichever way it is written. `anna.tags = [...]` and
                # `anna.character = [...]` both say "these are the texts now", so each is the
                # same act as adding what is new and dropping what is gone — through the same
                # door, which is what keeps the periods honest.
                #
                # Only for a write somebody made, though: inside trusted_writes() the machinery
                # is filling this in — loading a row, rebuilding an image — and the door states
                # facts and saves the entity, which during a load means saving a half-filled one. That is what emptied Event.title across a whole world:
                # `descriptions` is set partway through loading, the save that followed wrote
                # every attribute not yet read as null, and the next read found them gone.
                self._set_many(name, value)
                return
            # A date where a datetime is wanted is the same moment, said shorter — midnight, as
            # everywhere else in this world. Refusing it cost a statement each time, and the
            # refusal the host actually saw was "Object of type date is not JSON serializable".
            if (isinstance(value, date) and not isinstance(value, datetime)
                    and declared.get("type") == "datetime"):
                value = datetime(value.year, value.month, value.day)
            # One form of time, whatever came in. A world that keeps some times with a zone and
            # some without cannot compare its own records — and the host, holding a literal
            # datetime(2026, 10, 1), finds that out mid-task.
            if isinstance(value, datetime) and value.tzinfo is not None:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
            # Stored as given, only without stray whitespace; comparisons use the kind's normalize.
            if isinstance(value, str):
                value = value.strip()
                declared_type = declared.get("type") or ""
                if declared_type.startswith("enum["):  # one word for one thing, however it was typed
                    allowed = [v.strip() for v in declared_type[len("enum["):-1].split(",")]
                    value = next(v for v in allowed if v.lower() == value.lower())
                elif declared_type in ("email", "phone", "url", "domain"):
                    _ask_about_value(self, name, declared_type, value)
        overwrite = (
            _WRITE_GUARD is not None
            and not name.startswith("_")
            and name not in _MANAGED_ATTRS
            and getattr(self, "id", None) is not None  # only entities the world already knows
            and getattr(self, name, None) is not None  # only overwrites, not first assignment
        )
        if overwrite:
            _WRITE_GUARD(self, name, getattr(self, name), value)  # keeps the old value in history
        object.__setattr__(self, name, value)
        # When a record holds is data about it like any other, so it is stated too; only the
        # world's own bookkeeping (id, when we first saw it, when it was last touched) isn't.
        given = value if "given" not in dir() else given
        if (_CHANGED is not None and not name.startswith("_")
                and name not in ("id", "created_at", "accessed_at")
                and getattr(self, "id", None) is not None):
            # What is written is also what was said: the image changes here, and the statement
            # behind it goes into the record (facts.py). Loading from storage doesn't come
            # through here recording, so nothing is re-stated on a read.
            world = world_if_bound()
            if world is not None and getattr(world, "facts", None) is not None:
                source, run_id = stated_by()
                # Against the subject, not the image: an entity is a cluster of subjects
                # (assembly.py), and a statement made now must stay with the one it was made
                # about — otherwise a later split cannot put anything back where it belongs.
                world.facts.state(self.subject_id, name, _as_statement(given), source=source,
                                  run_id=run_id, class_name=type(self).__name__)
        if not name.startswith("_"):
            _note_changed(self, name)


@dataclass
class Spell:
    """One stretch of time something held of an entity — a tag, a value, a state."""

    value: Any
    starts: datetime
    until: datetime | None
    source: str

    @property
    def holds(self) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return self.starts <= now and (self.until is None or self.until > now)

    def __repr__(self):
        from terraweaver import timeutil

        ends = timeutil.show(self.until) if self.until else "…"
        return f"<{self.value!r} {timeutil.show(self.starts)} → {ends}{'' if self.holds else ', over'}>"


@dataclass
class Judgement:
    """Something the world worked out, with what it rests on. Handed to the host to explain."""

    value: Any
    made_at: datetime
    made_in: str | None   # the run — and, once work is organised into tickets, the ticket
    stale: bool
    because: list         # the statements it was drawn from

    def __repr__(self):
        from terraweaver import timeutil

        rests = "; ".join(str(s.value) for s in self.because[:4])
        return (f"<judged {self.value!r} on {timeutil.show(self.made_at)}"
                f"{', stale' if self.stale else ''} — from: {rests}>")


@dataclass
class Moment:
    """One dated thing in an entity's timeline."""

    when: datetime
    what: str

    def __repr__(self):
        from terraweaver import timeutil

        return f"<{timeutil.show(self.when)} — {self.what}>"


def Relation_base():
    from terraweaver.relations import Relation

    return Relation


def _remark_note(entity) -> str:
    """Relations and entities carry remarks that attributes don't show. Reading one and seeing
    only fields is how "rent: not recorded" gets answered over a comment that says $2,100."""
    try:
        count = len(entity.described())
    except Exception:  # noqa: BLE001 - a repr must never fail
        return ""
    return f", {count} remark{'s' if count > 1 else ''} (.described())" if count else ""


def _as_statement(value):
    """A value as the record keeps it: an entity is a reference to its subject, a moment is its
    own text, everything else is itself."""
    if isinstance(value, Entity):
        return {"$subject": value.id}
    if isinstance(value, list):
        return [_as_statement(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _also_repeats(made, every, lasting, starts, until):
    """`every=` is two more period keywords, not a second way of writing: whatever door wrote
    the period writes the repeat through the same one call."""
    if every is not None and isinstance(made, Entity):
        made.repeat(every=every, lasting=lasting, starts=starts, until=until)
    return made


def _as_written(values) -> list:
    """The texts as they were said, without repeats or stray whitespace — what is stated."""
    out = []
    for value in values or []:
        if not isinstance(value, str) or not value.strip():
            continue
        said = " ".join(value.split())
        if said not in out:
            out.append(said)
    return out


def did_you_mean(word: str, options, extra: dict | None = None) -> str | None:
    """The closest of `options` to `word`, or None when nothing is close enough.

    One place, so every refusal in this world guesses the same way and guesses the same thing
    twice. It is spelling distance, singular against plural, and a small table of words people
    use for each other (`extra`) — arithmetic on strings, no model, no world knowledge. The
    answer is a suggestion named out loud, never a substitution made quietly.
    """
    from difflib import get_close_matches

    if not word:
        return None
    names = [str(one) for one in options]
    near = get_close_matches(str(word), names, n=1, cutoff=0.6)
    if near and _same_head(str(word), near[0]):
        return near[0]
    plural = [n for n in names if n.rstrip("s") == str(word).rstrip("s")]
    if plural:
        return plural[0]
    swap = (extra or {}).get(str(word))
    return swap if swap in names else None


# Tails that carry grammar rather than meaning: two link names sharing one are not therefore
# close. "invented_by" and "owned_by" agree on four of eleven characters and on nothing else.
_GRAMMAR_TAILS = ("_by", "_of", "_in", "_at", "_to", "_for", "_with", "_from")


def _same_head(word: str, candidate: str) -> bool:
    """Whether a spelling match survives having its grammatical tail removed.

    Only applied where both words carry such a tail, or where one is the other's bare head:
    `located_in` still finds `located`, `job_title` still finds `title`, and `invented_by` no
    longer finds `owned_by`.
    """
    from difflib import get_close_matches

    def head(w):
        for tail in _GRAMMAR_TAILS:
            if w.endswith(tail) and len(w) > len(tail):
                return w[: -len(tail)]
        return w

    a, b = head(word.lower()), head(candidate.lower())
    if (a, b) == (word.lower(), candidate.lower()):   # no tail on either: nothing to correct for
        return True
    # Once a tail is off, the heads have to be nearly the same word. At a loose bar "partner"
    # matched "part_of" — a nature of links — and a host writing about somebody's wife got a
    # composition. What this is for is grammar, not resemblance: `located_in` finding `located`.
    if a == b or get_close_matches(a, [b], n=1, cutoff=0.85):
        return True
    # A missing underscore is a typo, not a different word: "partof" is "part_of" and "ownedby"
    # is "owned_by", and both are the sort of slip this exists to forgive.
    return bool(get_close_matches(word.lower(), [candidate.lower()], n=1, cutoff=0.85))


def take_as(what: str, given: str, meant: str) -> str:
    """Say that the world read one word as another, and get on with the answer.

    A refusal costs the host a turn to learn something the world already knew. Where the
    correction is unambiguous — one close word and no other — it is applied and announced
    instead: the answer arrives with the caveat attached, which is what the host would have
    written on the second try anyway. Ambiguity is still refused; this never guesses between two.
    """
    note_assumed(f"{what}: {given!r} taken as {meant!r} — the nearest thing to it here, and "
                 f"nothing else is close; say so if you meant something else")
    return meant


def _gaps_are_not_refusals(entity, class_name: str, missing: list) -> list:
    """Of the required attributes not given, keep refusing only the one that names the entity.

    A required attribute the host hasn't got is an invitation to invent one. Measured on a
    455-fact run: `Idea` requires `content`, and of seventy things the host tried to record,
    ten were lost outright and the rest got through by filling it — "Novel by Robert A.
    Heinlein" for one, an empty string for eight others. The invented lines went into the record
    as `source=agent`, indistinguishable from what the person actually said, which is the one
    thing this world exists to keep apart.

    So the gap is left open instead. The name is still required, because an entity nothing can
    identify breeds duplicates, and that is a defect no later telling repairs.
    """
    from terraweaver import matching

    identifies = matching.NAME_KEYS.get(class_name) or type(entity)._spec.get("identified_by")
    unnamed = [a for a in missing if a["name"] == identifies]
    gaps = [a for a in missing if a["name"] != identifies]
    for attr in gaps:
        object.__setattr__(entity, attr["name"], [] if attr["type"].startswith("list[") else None)
    if gaps:
        note_hint(
            f"{class_name} declares {', '.join(repr(a['name']) for a in gaps)} required and none "
            f"was given — left empty rather than refused. Fill it when the user says so; don't "
            f"put your own knowledge there to satisfy the check, because the record cannot tell "
            f"that apart from what they told you."
        )
    return unnamed


def _construction_problem(class_name: str, spec: dict, missing: list, unexpected: dict,
                          call: str = "(...)") -> str:
    """What is wrong with this call, all of it, with the likely word for each slip."""
    from terraweaver import matching

    known = [a["name"] for a in spec["attributes"] if "derived" not in a]
    parts = []
    if missing:
        parts.append("missing required attribute(s): " + ", ".join(f"'{n}'" for n in missing))
    # Whatever this class calls its name, a host will sometimes call it something else: "name"
    # for a title, "title" for a name. That is not a typo, so spelling distance never finds it.
    calls_it = matching.NAME_KEYS.get(class_name)
    synonyms = {word: calls_it for word in ("name", "title", "label", "full_name")} if calls_it else {}
    for given in unexpected:
        near = did_you_mean(given, known, synonyms)
        parts.append(f"no attribute '{given}'" + (f" — did you mean '{near}'?" if near else ""))
    return (f"{class_name}{call}: " + "; ".join(parts) + ". Its attributes are: "
            + ", ".join(known) + ". What none of them holds goes into a dated remark: "
            "entity.describe(....")


def _check_slot(entity, slot: str) -> None:
    """A text written into a slot the class hasn't got would be a fact nothing ever reads.

    Silent is the worst of the three outcomes here: the host believes it recorded something,
    the record holds it under a name no image is built from, and nobody finds out.
    """
    lists = dated_lists(type(entity)._spec)
    if slot in lists:
        return
    near = did_you_mean(slot, lists)
    if near:
        return take_as(type(entity).__name__, slot, near)
    raise AttributeError(
        f"{type(entity).__name__} has no list of texts called {slot!r}"
        + (f" — did you mean {near!r}? " if near else ". ")
        + (f"It has: {', '.join(sorted(lists))}." if lists else "It has none.")
        + " What no slot holds goes into a dated remark: entity.describe(....")


def _texts_as(slot: str):
    """How a slot shows its texts: tags in one form so they find each other, prose as written."""
    from terraweaver import tags as tagging

    return tagging.tidy if slot == "tags" else _as_written


def dated_lists(spec: dict) -> set:
    """The slots of a class that hold several texts, each with its own period.

    Three shapes of the same idea, and a world structuring itself climbs between them: free
    prose (`list[text]`) for what has no vocabulary yet, a vocabulary (`list[enum[...]]`) once
    the same words keep coming back, and a plain value for what is only ever one thing. Tags are
    the free shape shared by every class."""
    return {a["name"] for a in spec.get("attributes", [])
            if str(a.get("type", "")).startswith(("list[text]", "list[enum["))
            or a["name"] == "tags"}


def _period_text(starts, until) -> str:
    if starts is None and until is None:
        return ""
    from terraweaver import timeutil
    left = timeutil.show(starts) if starts else "…"
    right = timeutil.show(until) if until else "…"
    return f", holds {left} → {right}"


def _brief(value) -> str:
    """How a value appears inside an entity's repr — references by label, never expanded."""
    if callable(value) and not isinstance(value, type):
        # A method's own repr names the object it is bound to, which sends us straight back
        # here. Nothing about a function belongs in a picture of the facts anyway.
        return f"<{getattr(value, '__name__', 'callable')}()>"
    if isinstance(value, Entity):
        return f"<{type(value).__name__} {value.display_name()}>"
    if isinstance(value, list) and any(isinstance(v, Entity) for v in value):
        shown = ", ".join(f"<{type(v).__name__} {v.display_name()}>" if isinstance(v, Entity) else repr(v) for v in value[:3])
        return f"[{shown}{', …' if len(value) > 3 else ''}]"
    return repr(value)


def _ask_about_value(entity, name: str, kind: str, value: str) -> None:
    """A value that can't be what it's declared to be. The user said it, so it's kept — but the
    world holds the shape of its data, so it asks the host to check it rather than filing a
    phone number that has no digits in it."""
    from terraweaver import values

    if values.looks_like(kind, value) or getattr(entity, "id", None) is None:
        return
    world = current_world()
    world.questions.raise_(
        entity, "unclear_value",
        f"{name} recorded as {value!r}, which doesn't read as {'an' if kind[0] in 'aeiou' else 'a'} "
        f"{kind}. Is that right?",
        options=[f"it is the {kind}", "it's something else — put it in a remark"],
        touches=[f"attr:{name}"],
    )


def _check_type(class_name: str, spec: dict[str, Any], attr_name: str, value) -> None:
    """Enforce declared ref types, so a bare string can't land in a relationship field."""
    if value is None:
        return
    declared = next((a["type"] for a in spec["attributes"] if a["name"] == attr_name), None)
    if not declared:
        return
    if declared.startswith("list[") and isinstance(value, str):
        # One of several is still one of several. Written as a bare string it used to be stored
        # as a string, and then a list attribute answered with its last character.
        return [value]
    if declared.startswith("ref:"):
        expected = declared[4:]
        if expected != "any" and type(value).__name__ not in expected.split("|"):
            raise TypeError(
                f"{class_name}.{attr_name} must be a {expected} instance, got {type(value).__name__} "
                f"({value!r}). Get the entity first, e.g. {expected}.ensure(name=...)."
            )
    elif declared.startswith("enum["):
        allowed = [v.strip() for v in declared[len("enum["):-1].split(",")]
        if not isinstance(value, str):
            raise TypeError(f"{class_name}.{attr_name} is one of: {', '.join(allowed)}; got {value!r}")
        # A vocabulary is there so the same thing is recorded the same way — the world's own
        # business. Spelling and case are not: "Meeting" is the word, written differently.
        match = next((v for v in allowed if v.lower() == value.strip().lower()), None)
        if match is None:
            near = did_you_mean(value, allowed)
            if near:
                return take_as(f"{class_name}.{attr_name}", value, near)
            raise ValueError(
                f"{class_name}.{attr_name} is one of: {', '.join(allowed)} — {value!r} is none of them"
                + (f"; did you mean {near!r}? " if near else ". ")
                + (f"Use '{allowed[-1]}' and say what it is in a remark: entity.describe(...."
                   if allowed[-1] in ("other", "misc") else
                   "Pick the closest, and put what the user actually said in a remark.")
            )
    elif declared.startswith("list[enum["):
        allowed = [v.strip() for v in declared[len("list[enum["):-2].split(",")]
        if not isinstance(value, list):
            raise TypeError(f"{class_name}.{attr_name} is a list of: {', '.join(allowed)}")
        for one in value:
            if not isinstance(one, str) or not any(v.lower() == one.strip().lower() for v in allowed):
                raise ValueError(
                    f"{class_name}.{attr_name} takes any number of: {', '.join(allowed)} — "
                    f"{one!r} is none of them. What the vocabulary has no word for belongs in a "
                    f"free text: entity.add('descriptions', ...) or entity.describe(....")
    elif declared.startswith("list[ref:"):
        expected = declared[len("list[ref:"):-1]
        if expected == "any":
            return
        for item in value:
            if type(item).__name__ != expected:
                raise TypeError(
                    f"{class_name}.{attr_name} must contain {expected} instances, got "
                    f"{type(item).__name__} ({item!r})."
                )


def derived_names(spec: dict[str, Any]) -> set[str]:
    """Attributes computed from the other side of a relationship rather than stored."""
    return {a["name"] for a in spec.get("attributes", []) if "derived" in a}


def _derived_message(class_name: str, attr: dict) -> str:
    if attr["derived"] == "relation":
        return (f"{class_name}.{attr['name']} is read from relations and can't be set directly — "
                f"{attr.get('description', '')}")
    source_class, source_attr = attr["derived"].split(".", 1)
    return (f"{class_name}.{attr['name']} is derived from {attr['derived']} and can't be set directly; "
            f"set {source_attr} on the {source_class} instead")


def _reopen_what_the_world_ended(cls, side: str) -> None:
    """Take back the ends the world wrote because it believed there could be only one.

    Told a country has one citizen, the world ended one citizenship for every new one — six of
    them in a 455-fact run. Told afterwards that it can have several, nothing came back: the
    end dates stood, written by nobody anyone could name. They were the world's, drawn from a
    premise it has now been told is wrong, so they go with it. Ends a host set itself are not
    touched: those were said, not worked out.
    """
    world = current_world()
    if world is None:
        return
    brought = 0
    for link in world.all(cls.__name__, limit=None, history=True):
        if getattr(link, "valid_until", None) is None:
            continue
        try:
            said = world.facts.about(link.id)
        except Exception:  # noqa: BLE001 - a world without the record keeps its dates
            return
        ended_by_us = [s for s in said if s.slot == "valid_until" and s.source == "world"]
        if not ended_by_us:
            continue
        with trusted_writes(), stating("world"):
            link.valid_until = None
            world.save(link)
        brought += 1
    if brought:
        note_hint(f"{brought} {cls.__name__} link(s) had been ended because one per {side} was "
                  f"said; that is withdrawn, so they hold again. Anything a person ended "
                  f"themselves stays ended.")


def _keep_spec(spec: dict) -> None:
    """Write a grown type's spec back where it was read from, if it was grown at all."""
    world = current_world()
    where = getattr(world, "grown_dir", None) if world is not None else None
    if not where:
        return
    path = Path(where) / f"{spec['name']}.json"
    if path.exists():           # only types this world grew; the core ontology is not ours
        path.write_text(json.dumps(spec, indent=2))


class _RelationClass(type):
    """A relation type is a class, so what it is is said the way anything else is: by assignment.

    `london.nature = "place"` on a thing and `born_in.nature = "related_to"` on a type read the
    same because they are the same act — the one on an instance, the other on a class. A call of
    its own for the second (`world.relation_is(...)`) was a second vocabulary for one idea, which
    is what this world spends its days undoing.
    """

    @staticmethod
    def _now_said(cls):
        """Mark the type as one somebody has ruled on, and keep the ruling.

        Confirming a guess sets the same value the guess held, so the spec alone cannot tell
        "nobody has looked at this" from "somebody looked and agreed" — and a check that cannot
        tell them apart either asks forever or never asks at all.

        Written out, too. A type amended only in memory answers correctly until the process
        ends and then goes back to what the world guessed, which is the worst of both: the
        agent was asked, it answered, and the answer was thrown away without anybody being
        told.
        """
        cls._spec["relation"]["said_by_hand"] = True
        _keep_spec(cls._spec)

    @property
    def nature(cls):
        return cls._spec["relation"].get("nature")

    @nature.setter
    def nature(cls, value):
        from terraweaver import authoring

        word = authoring.AS_WRITTEN.get(str(value).strip().lower(), value)
        if word not in authoring.NATURES:
            raise ValueError("nature is one of: " + ", ".join(authoring.NATURES))
        cls._spec["relation"]["nature"] = word
        _RelationClass._now_said(cls)
        note_hint(f"{cls.__name__} is a {word} link now"
                  + (f", so: {', '.join(k for k in _relation_rules(word))}"
                     if _relation_rules(word) else ""))

    @property
    def one_per_subject(cls):
        return bool(cls._spec["relation"].get("functional"))

    @one_per_subject.setter
    def one_per_subject(cls, value):
        was = cls._spec["relation"].get("functional")
        cls._spec["relation"]["functional"] = _one_or_many(cls, value)
        _RelationClass._now_said(cls)
        if was and not cls._spec["relation"]["functional"]:
            _reopen_what_the_world_ended(cls, "subject")

    @property
    def one_per_object(cls):
        return bool(cls._spec["relation"].get("inverse_functional"))

    @one_per_object.setter
    def one_per_object(cls, value):
        was = cls._spec["relation"].get("inverse_functional")
        cls._spec["relation"]["inverse_functional"] = _one_or_many(cls, value)
        _RelationClass._now_said(cls)
        if was and not cls._spec["relation"]["inverse_functional"]:
            _reopen_what_the_world_ended(cls, "object")

    @property
    def changes(cls):
        return cls._spec["relation"].get("functional") == "at_any_time"

    @changes.setter
    def changes(cls, value):
        rel = cls._spec["relation"]
        for side in ("functional", "inverse_functional"):
            if rel.get(side):
                rel[side] = "at_any_time" if value else True
        _RelationClass._now_said(cls)
        note_hint(f"{cls.__name__}: a new one "
                  + ("ends the last, both true in their turn"
                     if value else "corrects the last, only one of them so"))


def _one_or_many(cls, value):
    """True/False on a side, keeping whether a new one ends the last or corrects it."""
    if not value:
        return False
    return "at_any_time" if cls._spec["relation"].get("functional") == "at_any_time" else True


def _relation_rules(nature: str) -> list[str]:
    from terraweaver import relations

    return sorted(relations.BY_NATURE.get(nature, {}))


def _lend_relations(classes: dict, defined: str) -> None:
    """Give every class the relations it can stand in, as methods of its own.

    `anna.born_in(london)` reads as the sentence and turns up where a host actually looks — in
    the class, beside its attributes. `anna.relate(london, "born_in")` says the same thing and
    is what stays for a link with no type yet, but nothing in a class's description ever
    mentioned it, so a host had to know the type existed before it could find out that it did.

    Called after any class is built, for that class and for anything already here, because a
    relation type may be defined before or after the classes it runs between.
    """
    from terraweaver import relations as rel_module

    types = {name: cls._spec["relation"] for name, cls in classes.items()
             if cls._spec.get("relation") and not cls._spec["relation"].get("free")}
    touched = [defined] if defined not in types else list(classes)
    for class_name in touched:
        cls = classes.get(class_name)
        if cls is None or cls._spec.get("relation"):
            continue
        for type_name, rel in types.items():
            for side, other in (("from", "to"), ("to", "from")):
                ends = rel.get(side) or ["any"]
                if class_name not in ends and "any" not in ends:
                    continue
                word = rel["kind"] if side == "from" else (rel.get("reverse") or "")
                # A declared attribute lives in the instance, so `hasattr(cls, word)` does not
                # see it and the method would be lent over the top of it — invisibly, until the
                # attribute happened to be unset and `vacancy.location` handed back a function.
                declared = {a["name"] for a in cls._spec.get("attributes", [])}
                if not word or hasattr(cls, word) or word in declared:
                    continue
                setattr(cls, word, _relation_method(type_name, rel, backwards=side == "to"))


def _relation_method(type_name: str, rel: dict, backwards: bool):
    """`anna.born_in(london)` — the same as `anna.relate(london, "born_in")`, said as a sentence."""
    kind = rel["kind"]

    def say(self, other=None, **attrs):
        world = current_world()
        if other is None:                       # asked with no other end: read, don't write
            return self.related(rel.get("reverse") if backwards else kind)
        a, b = (other, self) if backwards else (self, other)
        return world.relate(a, b, kind, **attrs)

    say.__name__ = rel.get("reverse") if backwards else kind
    say.__doc__ = (f"{rel.get('reads') or kind}. Written: "
                   f"a.{kind}(b). With no argument, reads instead of writing.")
    return say


def _relation_property(class_name: str, attr: dict):
    """An attribute read from relations (Person.organization from the primary Membership)."""
    from terraweaver import relations

    getter, setter, _ = relations.DERIVED[(class_name, attr["name"])]

    def refuse(self, value):
        raise TypeError(f"{class_name}.{attr['name']} is derived from relations and can't be set directly")

    def read(self):
        try:
            return getter(self)
        except ValueError as unknown:
            # A world may not have the type this attribute is read from — a minimal one has
            # Person before it has Membership. There being no links of a type that does not
            # exist is simply true, and an attribute that raises instead of saying so makes
            # the entity unusable for everything else it does hold.
            if "no relation type" not in str(unknown):
                raise
            return [] if attr["type"].startswith("list[") else None

    return property(read, setter or refuse, doc=attr.get("description", ""))


def _same_entity_property(class_name: str, attr: dict):
    """A second word for something this entity already holds — read as the latest, written as one more.

    Three slots held free text: `descriptions`, `notes` and `description`. A host wrote into
    whichever it remembered, so the same kind of fact ended up in three places, only one of which
    carries a date, a source and a period — and the other two could not be superseded or
    crystallised out of. One word for one place: the text lives in `descriptions`, and these read
    and write it.
    """
    held = attr["derived"].split(".", 1)[1]

    def get(self):
        texts = getattr(self, held, None) or []
        return texts[-1] if texts else None

    def put(self, value):
        if value is None:
            return
        if not isinstance(value, str):
            raise TypeError(f"{class_name}.{attr['name']} is free text — got {type(value).__name__}. "
                            f"Anything with parts of its own wants an attribute of its own.")
        # Through the list, not through describe(): the list is the one door, and whatever is
        # recording this run — a conclusion with its basis, a held write — goes through it too.
        setattr(self, held, list(getattr(self, held, None) or []) + [value])

    return property(get, put, doc=attr.get("description", ""))


def _derived_property(class_name: str, attr: dict):
    """A relationship's second side, computed from the one side that is stored.

    Storing both sides (Person.organization and Organization.employees) meant keeping them in
    sync by hand, and every gap in that was an inconsistency: a person who changed jobs stayed
    on the old company's list, a contact added twice was listed twice. Now only the single
    reference is stored; the list is whoever currently points here.
    """
    source_class, source_attr = attr["derived"].split(".", 1)
    many = attr["type"].startswith("list[")

    def get(self):
        world = current_world()
        pointing = [e for e in world.all(source_class, limit=None)
                    if _refers(getattr(e, source_attr, None), self)]
        if many:
            return pointing
        return pointing[0] if pointing else None

    def refuse(self, value):
        raise TypeError(_derived_message(class_name, attr))

    return property(get, refuse, doc=attr.get("description", ""))


def _refers(value, target) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return any(_refers(v, target) for v in value)
    return value is target or (getattr(value, "id", None) is not None and getattr(value, "id", None) == target.id)


def _intentional(impl):
    """Calling a method is a deliberate change, not new information to check against the old.

    `vacancy.apply()` moves the status from not_applied to applied by definition; treating that
    as a contradiction to settle with the user would make every action method unusable. The
    write guard stays on for direct assignment, where a new value may well be a mistake.
    """
    @wraps(impl)
    def method(self, *args, **kwargs):
        with trusted_writes():
            return impl(self, *args, **kwargs)

    return method


def _make_stub(class_name: str, method_name: str):
    def stub(self, *args, **kwargs):
        raise NotImplementedError(
            f"{class_name}.{method_name} has no implementation registered in terraweaver.impls"
        )

    return stub


# Every class can be described and tagged, relations included. A relation is an entity here —
# it has its own attributes, its own period, its own history — and "rent is $2,100 a month" is
# said about the landlord link, not about either person. Declaring these in nine JSON files and
# forgetting them in eleven others is how relations ended up unable to hold a remark at all.
COMMON_SLOTS = (
    {"name": "descriptions", "type": "list[text]", "required": False,
     "description": "How this one has been described, in whoever's words — several are normal."},
    {"name": "tags", "type": "list[str]", "required": False,
     "description": "Loose ties to other things, for what no attribute or relation says."},
)


def with_common_slots(spec: dict[str, Any]) -> dict[str, Any]:
    """The spec as declared, plus the slots every class has whether it says so or not."""
    declared = {a["name"] for a in spec.get("attributes", [])}
    missing = [dict(slot) for slot in COMMON_SLOTS if slot["name"] not in declared]
    if not missing:
        return spec
    return {**spec, "attributes": list(spec.get("attributes", [])) + missing}


def build_classes(specs: dict[str, dict[str, Any]], impls: dict[tuple[str, str], Any] | None = None) -> dict[str, type]:
    impls = impls or {}
    classes: dict[str, type] = {}
    for name, spec in specs.items():
        define_class(classes, spec, name=name, impls=impls)
    return classes


def define_class(classes: dict[str, type], spec: dict[str, Any], name: str | None = None,
                 impls: dict[tuple[str, str], Any] | None = None) -> type:
    """Build one class from its spec and register it in `classes`. Returns the class.

    The same call for a class and for a relation type — a relation section in the spec is what
    makes it one — so a type defined while the world is running is the same kind of thing as one
    given at the start, with the same attributes, periods, history and checks. Storage needs no
    warning: every class's table is made the first time something is written to it.

    An identity is registered here too, from the spec's `identified_by`, because identification
    is per class and a class nobody hand-tuned has none: without it `new()` never sees a twin
    and the world fills with duplicates of the same thing.
    """
    from terraweaver import matching

    impls = impls or {}
    name = name or spec["name"]
    spec = with_common_slots({**spec, "name": name})
    if spec.get("identified_by"):
        wanted = spec["identified_by"]
        wanted = wanted if isinstance(wanted, dict) else {"name_keys": list(wanted)}
        matching.register_identity(name, **wanted)
    if True:
        namespace = {
            "__doc__": spec.get("description", ""),
            "_spec": spec,
            # Shared, mutated-in-place: lets a method implementation reach sibling
            # classes (e.g. Person.add_fact needs to construct a Preference).
            "_classes": classes,
        }
        base = Entity
        if "relation" in spec:
            from terraweaver.relations import Relation

            base = Relation
            # The ends take anything. What classes a relation runs between is not a promise the
            # world holds a host to — it is something the world watches and can count, and it was
            # wrong as a promise: declared from the first example anybody saw, it refused the
            # second, and a host told its type does not take these ends defines a second type
            # with the class names in it. `relation["from"]` and `["to"]` stay, to describe the
            # type and to measure an odd link against; they no longer stop one being written.
            ends = [
                {"name": "subject", "type": "ref:any", "required": True,
                 "description": "Where the relation starts — "
                                + (spec["relation"].get("reads") or "the subject")},
                {"name": "object", "type": "ref:any", "required": True,
                 "description": "Where the relation leads."},
            ]
            if not any(a["name"] == "subject" for a in spec["attributes"]):
                spec["attributes"] = ends + spec["attributes"]
            for end in spec["attributes"][:2]:
                if "any" in end["type"]:
                    end["type"] = "ref:any"
        for attr in spec.get("attributes", []):
            if attr.get("derived") == "relation":
                namespace[attr["name"]] = _relation_property(name, attr)
            elif str(attr.get("derived", "")).startswith("self."):
                namespace[attr["name"]] = _same_entity_property(name, attr)
            elif "derived" in attr:
                namespace[attr["name"]] = _derived_property(name, attr)
        for method in spec.get("methods", []):
            mname = method["name"]
            impl = impls.get((name, mname))
            namespace[mname] = _intentional(impl) if impl else _make_stub(name, mname)
        # Everything shared comes from Entity; a generated class carries only its own
        # spec and methods.
        made = _RelationClass if spec.get("relation") else type
        classes[name] = made(name, (base,), namespace)
        _lend_relations(classes, name)
        return classes[name]
