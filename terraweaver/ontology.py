"""Loads class specs from ontology/core/*.json and builds real Python classes from them.

Attributes come purely from the JSON spec (generic). A class a world starts with declares no
methods: what a class can do is written by the world itself (`procedures.py`) and bound onto it
there. A method a spec declares with nothing bound to it gets a stub that raises
NotImplementedError, so a gap fails loudly instead of silently doing nothing.
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

# What a side of a relation says when it holds one: **one at a time**, and a new one ends the
# standing one's period where it begins. Nothing is deleted and nothing is called a mistake; if
# only one can hold, the periods do not overlap, and that is the whole of it.
#
# It is the only value the two sides take besides False. A side once also took `True`, meaning
# "one ever", and that was withdrawn: history only accumulates, because a record is only ever
# added to, and nothing in a record is one forever — a birthplace changes in the record when
# sources disagree or somebody was wrong. Specs written while `True` existed are read as this.
AT_A_TIME = "at_any_time"


def set_write_guard(guard) -> None:
    global _WRITE_GUARD
    _WRITE_GUARD = guard


def now_utc() -> datetime:
    """The world's now — the clock it has been told, or the one on the wall.

    Not `datetime.now` any more. `created_at` is written from here, and `created_at` is what
    "when did this link begin" falls back to when nobody said: read off the wall clock while the
    world was recording a fact as of 2020, every such comparison was against a moment six years
    later, so nothing could be ordered against it (docs/archive/now.md, item 2).
    """
    from terraweaver import timeutil

    return timeutil.now()


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
    global _CHANGED, _SAYING
    previous, saying = _CHANGED, _SAYING
    _CHANGED, _SAYING = None, False
    try:
        yield
    finally:
        _CHANGED, _SAYING = previous, saying


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


def _name_of_me(entity) -> str:
    """What to call this one in a message to whoever wrote the line."""
    word = str(getattr(entity, "name", None) or getattr(entity, "full_name", None) or "it")
    return "".join(ch if ch.isalnum() else "_" for ch in word.lower()).strip("_").split("_")[0] or "it"


def _is_a_sentence(how: str) -> bool:
    """Words about a fact, or the name of a type this world holds.

    A type is a word this world knows; everything else is words the user said. Decided by asking
    the world and by nothing else: `born_in` is a sentence nowhere and a type here, and which it
    is depends on what has been defined, not on the shape of the string.

    It used to fall back to counting words, and the shape decided: `relate(b, "died in")` went in
    as a link with its words, `relate(b, "founded")` was refused for naming a type that does not
    exist. One word or five, the host cannot know which side of that line it is on — measured, it
    cost five lines of a block at a time and left the fact recorded nowhere, neither typed nor as
    it was said. The word is the description, the engineer makes the type from the description,
    and refusing it throws away the only account of that link there will ever be.
    """
    if not isinstance(how, str):
        return False
    said = how.strip()
    world = current_world()
    if world is not None:
        for name, cls in getattr(world, "classes", {}).items():
            rel = (getattr(cls, "_spec", {}) or {}).get("relation") or {}
            if said in (rel.get("kind"), rel.get("reverse"), name):
                return False
    return bool(said)


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
# Whether a write outside a host's run is said, not only shown. Inside a run every write is stated;
# outside one only what is under `stating(...)` — the world's own passes. Without it they changed
# the image and nothing else: measured 2026-10-03, rebuilding var/run11 from its record brought
# back 121 bare links the reading had ended in the image only (experiments/image_vs_record.py).
_SAYING = False


@contextmanager
def stating(source: str, run_id: str | None = None):
    """Whose word the writes inside this block are, and what run they belong to.

    The default is `agent`: everything that arrives through the assistant, whether it was
    relayed or concluded. The world can't tell those apart and doesn't try — what the assistant
    passes on is the assistant's responsibility. The world's own work says `stating("world",
    ticket)`, and what it writes then carries the lowest standing and comes back off in one
    move."""
    global _STATING, _SAYING
    before, saying = _STATING, _SAYING
    _STATING, _SAYING = (source, run_id), True
    try:
        yield
    finally:
        _STATING, _SAYING = before, saying


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


_SAID_IN_WORDS = False


@contextmanager
def said_in_words():
    """A link being made from the host's sentence, to be typed when the task closes.

    It goes in untyped on purpose — `related`, carrying the words — and the world asks, once
    per type, whether a link recorded that way has a word of its own. Here it does not: the
    word is in the sentence and is read at the close, minutes later. Asking would hold the task
    open on a question the close itself answers, which deadlocked every run of the sentence
    door: seven facts recorded, seven links standing, the task refusing to close.
    """
    global _SAID_IN_WORDS
    was, _SAID_IN_WORDS = _SAID_IN_WORDS, True
    try:
        yield
    finally:
        _SAID_IN_WORDS = was


def is_said_in_words() -> bool:
    return _SAID_IN_WORDS


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


# The preset: what a new world starts with, and the least a world can be. A Thing is somewhere to put anything at all, so nothing waits for a
# class to exist; a Related is a link with no type yet, so no fact waits for a relation type. And
# every world is between two parties who are in it as entities — without a Person and an Agent
# there is no "me" and no "you", and "my dentist" has no "my".
#
# Everything else — Organization, Place, Event, Vacancy — is filling: useful, probably, but it
# has to earn its place by making the work easier than the base alone, or it is not help but
# noise. `Idea` was noise: seventy things were forced into a class meant for notes, ten were lost
# saying so, and the rest got through by inventing what the host did not know.
# Three kinds of thing, and a world is made of them: entities (Thing, Person), the links
# between them (Related), and events. An event is not an entity that happens to
# have a date — it is the one kind whose time is part of what it is, which is why `start_time`
# is required on it and required nowhere else. A world without Event has nowhere to put "when"
# except on links that merely hold, and asking a link that merely holds when it began cost a
# 455-fact run most of its capitals and every one of its marriages.
# `PartOf` and `Kind` were here as two links every world was thought
# to need, and they are not: a part and a whole is a relation like any other and the world finds
# the word for it from what was said. Kept in the base they were two words a reading could reach
# for instead of the one the fact used — "the capital of France" went in as `part_of`, true and
# unanswerable, because `part_of` was there and `capital_of` was not.
#
# A starting set, not a rank. Nothing downstream asks whether a class came from here: it is built,
# read, extended and changed exactly as a class the world defines for itself (`growth.py`), and
# carries `source: "preset"` so the difference can be seen when it matters — never so it can be
# acted on. Task is here too, and is not the person's picture of anything: it is the world's own
# record of the work done on it, which its spec says with `own`.
def base_specs(ontology_dir: Path) -> dict[str, dict[str, Any]]:
    """The preset a new world starts with — whatever `ontology/core` holds.

    It used to cut five classes out of a larger core of twenty-three, and the rest kept surfacing as
    though it were part of the world. The files are the classes as a world starts with them now.
    """
    return load_specs(ontology_dir, grown_dir=Path("/nonexistent"))


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
        # Two clocks, on purpose. `created_at` is when the thing entered the *world*, so it is on
        # the world's clock: it is what "when did this begin" falls back to when nobody said, and
        # that is compared against `valid_from`, which is the world's time. Read off the wall
        # while the world recorded facts as of 2020, every such comparison was against 2026, and
        # the hand-over could not tell an earlier telling from a later one (docs/archive/now.md, item 2).
        # `accessed_at` is when *we* last worked with it — attention, not history — and is only
        # ever compared with itself, so it stays on the wall clock that `touch` uses.
        self.created_at = kwargs.pop("created_at", None) or now_utc()
        self.accessed_at = (kwargs.pop("accessed_at", None)
                            or datetime.now(timezone.utc).replace(tzinfo=None))
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
    def all(cls, limit: int | None = 50, *, any_time: bool = False, history: bool = False,
            kinds: bool = True) -> list:
        """Entities of this class and of every kind of it, most recently worked with first — the
        ones that hold now; any_time=True adds those whose period has ended or hasn't started,
        kinds=False leaves out the classes beneath this one."""
        return current_world().all(cls, limit=limit, history=history or any_time, kinds=kinds)

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
    def identify(cls, **attrs) -> list:
        """Who this could be — the candidates, best first, for you to read and choose between.

        On the class like every other door here, because a host thinks in the class it is
        talking about. `get` is the one that must already be here and shouts when it is not;
        this one settles who a task is about before anything is written about them, and a name
        nobody here has is recorded rather than refused — there is no other branch to take when
        the user has just spoken about a city this world has never heard of.
        """
        return current_world().identify(cls, **attrs)

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
        return current_world().history.of(self, attr)

    def relate(self, other, how: str, /, *, starts=None, until=None, ttl=None,
               permanent: bool = False, every=None, lasting=None,
               **attrs):
        """Say what joins this entity to another, in the words the fact came in.

            paris.relate(france, "Paris is the capital of France")    the fact, in words
            paris.set_capital_of(france)                              the word, where there is one

        This one takes the words. A word the record already holds has a call of its own on the
        class — `set_capital_of` — which is where a host looks and what the class's description
        shows; this is what stays for a fact there is no word for yet, and it is the form for a
        host telling what happened rather than modelling it. The word, the roles, how many hold
        at a moment, what follows and when it began are worked out afterwards, by an engineer
        whose whole task that is.

        A word this world already knows is taken here too, rather than refused for being said
        the shorter way — but it is not what this door is for.

        Asking the host for a type before the fact can be said asks a storyteller to do an
        engineer's work, and it was measured: two ideas collected under one word, three links
        written backwards because an argument order had to be got right, how many there may be
        answered by guess. None of that was carelessness.

        A relation takes a period like anything else, and a cyclic one the same way: a cleaner
        every other week, a class every Tuesday term-time."""
        if isinstance(self_first := other, str) and hasattr(how, "id"):
            # Said the other way round — `a.relate("associated_with", b)`. Both a host and the
            # reading's own engineer write it like that, and the world used to answer
            # "no relation type Thing(id=…)", printing the entity where the word should be.
            # Measured 2026-09-28, it was one of the two lines that killed a reading phase. Which
            # of the two is the word and which is the thing is not in doubt here, so it is taken.
            other, how = how, self_first
        if _is_a_sentence(how):
            return current_world().said_of(self, other, how, starts=starts)
        # A word this world already holds has a call of its own on the class, and that is where
        # a host looks for it — in the class's own description, beside its attributes. Taken
        # here as well, there were two ways to say one thing and the texts could only teach one
        # of them: a live host read a primer that never mentions this door, found it anyway,
        # and wrote most of a run through it.
        word = str(how).strip()
        if hasattr(self, f"set_{word}"):
            raise TypeError(
                f"say it with the word: {_name_of_me(self)}.set_{word}(other) — that is where "
                f"{word} lives, and it reads back as .{word}. This call is for a fact there is "
                f"no word for yet: relate(other, \"<the fact, in the words the user used>\").")
        made = current_world().relate(self, other, how, starts=starts, until=until, ttl=ttl,
                                      permanent=permanent, **attrs)
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
        # Whose word it is, kept with it. Left to the default this went in as the agent's telling
        # even when the world itself was placing the thing, and the world's own work has to be
        # retractable in one move and ranked below what it was told (`stating`, `retract_run`).
        source, run_id = stated_by()
        world.facts.state(self.subject_id, assembly.IS_A, name, valid_from=when,
                          source=source, run_id=run_id, class_name=type(self).__name__)
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
        moment = now_utc()            # "what holds now" is the world's now, as everywhere else
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
        `about` is the attribute or relation it hangs over ("aliases", "born_in"): a later read of
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
        # is: `report(owner.name)` makes no calls yet is perfectly grounded.
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
        if _called_its_name(type(self), name):
            # `person.full_name`, `event.title`: the name, said the way it once was.
            return self.__dict__.get("name")
        if name.startswith("set_"):
            # A word this world holds, reached on a class it was not declared between. The call
            # lives on the ends the type names (`_lend_relations`) and nowhere else, so this is
            # the place to say which those are — Python's own "has no attribute … did you mean
            # set_kinds?" reads as the class being wrong, and a host told that in one session
            # stopped using the class altogether.
            world = current_world()
            word = name[len("set_"):]
            for cls in (getattr(world, "classes", {}) or {}).values():
                rel = cls._spec.get("relation") or {}
                if not rel or rel.get("free"):
                    continue
                if word in (rel.get("kind"), rel.get("reverse")):
                    # Watched, not enforced — which the refusal that used to stand here said in
                    # its own last clause and then contradicted by raising. The ends a type names
                    # are what it has been seen between, so a call from a new end is news about
                    # the word and not an error in the link: the call is handed over and the
                    # world notes what it has learned. Measured 2026-09-28: refusing it killed
                    # 24 readings of 54, and the advice it gave — say it in the words it came in —
                    # is a circle when it is the reading being told, since the words are what the
                    # reading is reading.
                    ends = " → ".join(("/".join(rel.get(side) or ["any"]) for side in ("from", "to")))
                    note_hint(f"{word} had run between {ends} and has now been said of a "
                              f"{type(self).__name__} — the word's ends are what it has seen.")
                    return _sets_the_role(cls.__name__, rel,
                                          word == rel.get("reverse")).__get__(self, type(self))
        spec = type(self)._spec
        known = [a["name"] for a in spec.get("attributes", [])]
        from terraweaver import matching

        calls_it = matching.NAME_KEYS.get(type(self).__name__)
        synonyms = {w: calls_it for w in ("name", "title", "label", "full_name")} if calls_it else {}
        if name in known or name in _MANAGED_ATTRS or name in ("subject", "object"):
            # Declared, and not on this one. Two different things wear the same exception, and
            # saying the wrong one is worse than saying nothing: "CapitalOf has no 'subject' —
            # did you mean 'subject'? It has: subject, object" is what a host was told eighteen
            # times in one session about a link whose ends were missing from its image. It read
            # as the class being wrong, and the host stopped using the class.
            raise AttributeError(
                f"this {type(self).__name__} has no {name!r} in the image — the class declares "
                f"it, so the value is missing from this one rather than from the class. If the "
                f"record has it, `world.rebuild()` reads every image again from what was said "
                f"and brings it back; if nothing ever said it, say it now."
            )
        near = did_you_mean(name, known, synonyms)
        # `set_<word>` for a word this world has no type for is a *link* being written, and the
        # answer is the link door. Answered with "give the class the attribute", the host went
        # looking for an attribute: measured 2026-09-30, the same 25 facts took 24 turns against
        # 3, most of them spent on `set_born_in` — a fact about two things — being sent towards
        # `world.attribute`. Which of the two it is is not a guess: `set_` says a link.
        if name.startswith("set_") and len(name) > 4:
            word = name[len("set_"):].replace("_", " ")
            raise AttributeError(
                f"{type(self).__name__} has no {name!r}, because this world has no word "
                f"{word!r} for a link yet. A fact about two things is written by saying it: "
                f"`this.relate(other, \"{word}\")` — the world finds or makes the word, and "
                f"`set_{name[len('set_'):]}` exists from then on. If it is not about two things "
                f"but a value this one holds, it is an attribute: "
                f"world.attribute({type(self).__name__}, \"<name>\", \"<what it is>\").")
        raise AttributeError(
            f"{type(self).__name__} has no {name!r}"
            + (f" — did you mean {near!r}? " if near else ". ")
            + (f"It has: {', '.join(known)}." if known else "")
            + " If this is a value worth asking about later, give the class the attribute and "
            + f"then set it: world.attribute({type(self).__name__}, {name!r}, \"<what it is>\")."
            + " A description is for what no attribute should hold — a sentence about why this "
            + "thing is here, not a fact somebody will want to look up.")

    def __setattr__(self, name, value):
        if _called_its_name(type(self), name):
            name = "name"
        spec = type(self)._spec
        class_name = type(self).__name__
        if not name.startswith("_") and _is_a_question(value):
            # A lookup that came back a question, written in as if it were a thing. It reached
            # `json.dumps` and raised `Object of type NeedsResolution is not JSON serializable`
            # — nine of ninety failed readings in one world, and the reason said nothing about
            # what had happened. The question is what the door is for: it says which candidates
            # there were and how to settle it, and nothing is written until somebody has.
            raise TypeError(
                f"{class_name}.{name} was given the answer to a lookup that did not settle: "
                f"{getattr(value, 'reason', 'two or more things could be meant')}. Nothing is "
                f"written from a question. Look again with more to go on — another attribute, a "
                f"fuller name — or settle it: world.settle(<the question>, <the one meant>). "
                f"{getattr(value, 'question', '')}".strip())
        if name in ("valid_from", "valid_until", "created_at", "accessed_at") and value is not None:
            # A moment, whatever it was written as. These are managed attributes, so they skip every
            # check below — and a string written straight into one is stored as a string and then
            # every time-filtered read of that class raises `'str' object has no attribute 'year'`
            # from deep inside `holds_at`. Measured 2026-09-28: one such value killed the whole
            # reading phase of a 455-fact run on its first link, and the hundred questions after it
            # were put to a world with nothing typed in it at all. A period is a moment or it is
            # refused here, where the reason can be said.
            from terraweaver import timeutil

            if not isinstance(value, datetime):
                read, _sure = timeutil.told(value)
                if read is None or getattr(read, "moment", None) is None:
                    raise TypeError(
                        f"{name} is a moment, and {value!r} does not read as one. Say it as a date "
                        f"— date(2019, 3, 1), datetime(2019, 3, 1) or \"2019-03-01\" — or say when "
                        f"it holds through the door that takes it: "
                        f"entity.keep(starts=..., until=...).")
                value = read.moment
        if name not in _MANAGED_ATTRS and not name.startswith("_"):
            declared = next((a for a in spec["attributes"] if a["name"] == name), None)
            # An attribute the class doesn't have used to be accepted and then lost on save —
            # a write that looked fine and never happened.
            if declared is None:
                # A name the class already answers with a call is not a value it can hold. Written
                # as an assignment — `person.set_speaks = "Japanese"`, which is what a host reaches
                # for — the growth took it for a new attribute, and the old value history then read
                # off the class for it was the bound setter itself: `json.dumps` raised on a method
                # and every write to any Person in that world raised after it. Storage no longer
                # breaks over it (store._encode), and the write is refused here, where the reason
                # can be said: a link is one link, and an assignment would say all of them.
                already = getattr(type(self), name, None)
                # `set_` is this world's own form for writing a link, whether or not the word
                # exists yet. Checking only for a method that is already there left the other
                # order open, and it is the one a host takes: assign to `set_performed_by` first,
                # define `performed_by` second, and now the instance carries an attribute whose
                # name the class answers with a method — the next save reads the method and
                # `json.dumps` raises on it, for good. Measured 2026-09-28: eleven such attributes
                # across two classes in one 455-fact world, and over a thousand rows.
                if name.startswith("set_") and len(name) > 4:
                    raise TypeError(
                        f"say it with the call, not an assignment: "
                        f"{_name_of_me(self)}.{name}(other) — {name[len('set_'):]} is how a link "
                        f"is written, one at a time, and `set_…` is never the name of a value. "
                        f"If the word does not exist yet, define it: "
                        f"world.define_relation({name[len('set_'):]!r}, \"<what this link is>\", "
                        f"nature=\"related_to\", cardinality=\"many-to-one\").")
                if callable(already) and not isinstance(already, type):
                    me = _name_of_me(self) if "_name_of_me" in globals() else "it"
                    if name.startswith("set_"):
                        raise TypeError(
                            f"say it with the call, not an assignment: {me}.{name}(other) — "
                            f"{name[len('set_'):]} is a word for a link, and a link is written one "
                            f"at a time while the end reads back every one of them. "
                            f"{me}.{name[len('set_'):]} is how it reads.")
                    raise TypeError(
                        f"{name!r} is something a {class_name} does, not a value it holds: "
                        f"{me}.{name}(...). If a value of that name is wanted, it needs another "
                        f"name — this one is taken by the call.")
                near = did_you_mean(name, [a["name"] for a in spec["attributes"]])
                if near:
                    setattr(self, take_as(class_name, name, near), value)
                    return
                # Taken on the fly where the world can take it. Refusing is right about the
                # ontology and wrong about the cost: a raise stops the block, everything after
                # it goes unrecorded, and a host that keeps hitting a wall writes prose, which
                # is where a fact stops being one. So the word is taken with its type guessed
                # from the value, and the two things no value can tell you — what it means and
                # whether it supersedes — are asked for at the close, where the host is free.
                taken = _take_the_word(self, class_name, name, value)
                if taken is not None:
                    declared = taken
                else:
                    raise AttributeError(
                        f"{class_name} has no attribute '{name}'"
                        + (f" — did you mean '{near}'? " if near else ". ")
                        + "Its attributes are: "
                        + ", ".join(a["name"] for a in spec["attributes"])
                        + f".\nThis world does not let its classes grow, so there is nowhere "
                        f"to put it. What no attribute holds goes into a description: "
                        f"entity.describe(...)."
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
        # What is *stored* under that name, read without running anything. `getattr` here ran the
        # reading property of a relation's word — `related()`, which loads the entities at the far
        # end, each of whose loads came back through here for its own words. On a 455-fact world
        # the chain ran the length of the graph: `RecursionError` in the middle of a load, and the
        # whole names pass lost with it (2026-10-02, var/run9). Whether this is an overwrite is a
        # question about the stored value; a computed one is not an old value of anything.
        stored = self.__dict__.get(name)
        overwrite = (
            _WRITE_GUARD is not None
            and not name.startswith("_")
            and name not in _MANAGED_ATTRS
            and getattr(self, "id", None) is not None  # only entities the world already knows
            and stored is not None                     # only overwrites, not first assignment
        )
        if overwrite:
            _WRITE_GUARD(self, name, stored, value)  # keeps the old value in history
        object.__setattr__(self, name, value)
        # When a record holds is data about it like any other, so it is stated too; only the
        # world's own bookkeeping (id, when we first saw it, when it was last touched) isn't.
        given = value if "given" not in dir() else given
        if ((_CHANGED is not None or _SAYING) and not name.startswith("_")
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
        now = now_utc()               # the world's now: a stretch holds or not in the world's time
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
    world = current_world()          # raises when nothing is bound; it never comes back None
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
            # And how that bound was meant. `_hand_over` writes `until_is = BEFORE` when nothing
            # said the day, and left behind it says a link with no end ends "some time before" —
            # a side to a bound that is not there (docs/archive/code-review-2026-09-30.md 3.2.14).
            if getattr(link, "until_is", None) is not None:
                link.until_is = None
            world.save(link)
        brought += 1
    if brought:
        note_hint(f"{brought} {cls.__name__} link(s) had been ended because one per {side} was "
                  f"said; that is withdrawn, so they hold again. Anything a person ended "
                  f"themselves stays ended.")


def _keep_spec(spec: dict) -> None:
    """Write a changed class to the world's own place, whoever wrote it first.

    A class the world started with is changed exactly as one it made is — and kept the same way:
    its version goes beside the world's database and is what the world opens with next time. This
    used to write only classes the world had grown, on the grounds that the preset was not the
    world's to change, so an amendment to a class it started with held for the session and was
    gone on reopening. The preset file itself is never touched; it is what a new world starts from.
    """
    world = current_world()
    where = getattr(world, "grown_dir", None) if world is not None else None
    if not where:
        return
    Path(where).mkdir(parents=True, exist_ok=True)
    (Path(where) / f"{spec['name']}.json").write_text(json.dumps(spec, indent=2))


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


def _one_or_many(cls, value):
    """What a side says about how many: one at a time, or as many as there are.

    `changes` stood here as a second switch — does a new one end the last, or correct it — and it
    is gone with the category it belonged to. A new one always ends the last: the record keeps
    both, with periods that do not overlap, and which of them was a change in the world and which
    a change of somebody's mind is not a thing a record can tell or has to.
    """
    return AT_A_TIME if value else False


def _relation_rules(nature: str) -> list[str]:
    from terraweaver import relations

    return sorted(relations.BY_NATURE.get(nature, {}))


def _lend_relations(classes: dict, defined: str) -> None:
    """Give every class the relations it can stand in, as methods of its own.

    Two of them per word: `anna.born_in` reads the end back, `anna.set_born_in(london)` states
    it. Both turn up where a host actually looks — in the class, beside its attributes — while
    `anna.relate(london, "...")` stays for a fact there is no word for yet, and nothing in a
    class's description ever mentioned that, so a host had to know a type existed before it
    could find out that it did.

    Read and written apart, because the two are not the same shape: writing is always one link,
    this thing to that one, and reading a plural end is every link there is. An assignment would
    claim replacement over an addition.

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
                if not word or hasattr(cls, word):
                    continue
                backwards = side == "to"
                if word in declared:
                    # The same word is an attribute of the class and an end of a link, and the
                    # empty attribute hid the link: `country.capital` read None while the world
                    # held "Russellville capital of Soviet Union", and a host told "Not recorded".
                    # Found 2026-10-05 on seven classes of a 250-fact world — `Country.capital`,
                    # `Book.author`, `PoliticalOrganization.chairperson` — the words the questions
                    # are asked in. One word reads one way: the link where one holds, the
                    # attribute where none does.
                    setattr(cls, word, _AttributeOrLink(word, rel, backwards))
                else:
                    setattr(cls, word, _relation_role(type_name, rel, backwards))
                if not hasattr(cls, f"set_{word}"):
                    setattr(cls, f"set_{word}", _sets_the_role(type_name, rel, backwards))


class _AttributeOrLink:
    """A declared attribute that is also the word of a link reaching this class.

    Read, it gives what the link holds now and the attribute only where no link does — the link
    is the structured telling, handed over when corrected, and an attribute beside it is at best
    a snapshot. Written, it is the attribute and nothing else, so storage keeps exactly what was
    said into it: `stored_value` reads the attribute's own value, never the link.
    """

    def __init__(self, word: str, rel: dict, backwards: bool):
        self.word, self.rel, self.backwards = word, rel, backwards

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        from terraweaver import relations

        # Strictly from this end. A link word with nothing at this end answers from the other one,
        # which is right for a word and wrong for an attribute: every city would read the country
        # it is the capital of as its own `capital`.
        try:
            links = relations.relations_of(current_world(), instance, self.word, strict=True)
        except Exception:  # noqa: BLE001 - an end that cannot be read leaves the attribute to answer
            links = []
        others = [r.other(instance) for r in links]
        if others:
            reads_one = self.rel.get("inverse_functional") if self.backwards else self.rel.get("functional")
            return others[0] if reads_one else others
        return instance.__dict__.get(self.word)

    def __set__(self, instance, value):
        instance.__dict__[self.word] = value


def stored_value(instance, name: str):
    """The value an attribute itself holds, for storage: the attribute, never a link of the same word."""
    if isinstance(getattr(type(instance), name, None), _AttributeOrLink):
        return instance.__dict__.get(name)
    return getattr(instance, name, None)


def _is_a_question(value) -> bool:
    """Whether this is an unsettled lookup rather than something that can be written down."""
    from terraweaver.resolution import NeedsResolution

    return isinstance(value, NeedsResolution)


def _relation_role(type_name: str, rel: dict, backwards: bool):
    """The end of a relation, on the class, read as the attribute it reads like.

        rome.capital_of  -> Italy            anna.mother_of -> [Boris, Vera]

    One at each end or several: the type says which, so this gives a value where only one can
    hold at a moment and a list where more can. Each end reads by its own word — the city is
    the capital of the country, the country has the city as its capital — so a host asking
    about either one asks in the words of that end.

    **Reading only.** There is one way to state a link and it is to say the fact in words:
    `rome.relate(italy, "Rome is the capital of Italy")`, and the world finds the word for it.
    Assignment looked like the short way to say the same thing and is not: on a single end it
    reads as replacement, on a plural one it would either quietly accumulate (and then `=` is a
    lie) or end every link left out of the list (and then a short list erases what somebody
    said). Neither is what the host means, and the world already knows which of them applies —
    from the type, not from the syntax. So it is not offered.
    """
    kind = rel["kind"]
    word = (rel.get("reverse") or kind) if backwards else kind

    def read(self):
        # Which end may hold several at one moment, read from the spec now rather than captured
        # when the property was lent. `functional` says a subject has one object;
        # `inverse_functional` says an object has one subject — and either can be changed while
        # the world runs (`Type.one_per_subject = False`), after which two links stand and this
        # went on handing back the first of them as if it were the only one
        # (docs/archive/code-review-2026-09-30.md 3.2.5).
        got = self.related(word)
        if rel.get("inverse_functional") if backwards else rel.get("functional"):
            return got[0] if got else None
        return got

    def refuse(self, value):
        """An assignment where the word wants a call — taken as the call, and said so.

        This raised, and the raising was measured: of 285 names read in one world, **49** ended on
        it, every one of them the engineer writing `x.citizen_of = y` instead of
        `x.set_citizen_of(y)`. The engineer cannot read the message and try again the way a host
        can — it has three goes and then the thing stays unplaced — so a door that only says no
        loses the fact. What the assignment means is not in doubt: one link, this thing to that one.

        Taken, then, and the difference is noted rather than enforced: an assignment reads as
        replacement and this adds one link, which is the type's rule to decide and not the
        syntax's. Nothing is guessed — `set_` does exactly this — and nothing is lost.
        """
        if value is None:
            # Nothing to write, and nothing to complain about either. The engineer writes
            # `it.located_in = None` where the words gave no place — measured 2026-09-30, five of
            # 41 names ended on this refusal of mine, and everything under that line went with it.
            # Saying "there is no value" is not a mistake; it is an answer, and the lines after it
            # are somebody's work.
            note_hint(f"{_name_of_me(self)}.{word} = None says there is no such link to write, so "
                      f"nothing was written. To end one that is there: rel.keep(until=...).")
            return None
        note_hint(f"{_name_of_me(self)}.{word} = … was taken as "
                  f"{_name_of_me(self)}.set_{word}(…) — a link is written one at a time, and an "
                  f"assignment adds this one rather than replacing what is there. Whether a second "
                  f"corrects the first is the type's rule.")
        return getattr(self, f"set_{word}")(value)

    # The docstring is written once, when the property is lent, and says what the type says now.
    reads_one = rel.get("inverse_functional") if backwards else rel.get("functional")
    return property(read, refuse, doc=(f"{rel.get('reads') or kind}. Reads "
                                       f"{'one' if reads_one else 'a list'}; "
                                       f"written with set_{word}(other)."))


def _sets_the_role(type_name: str, rel: dict, backwards: bool):
    """`rome.set_capital_of(italy)` — state this link, from this end, one at a time.

    A method and not an assignment, because the two sides are not the same shape. Writing is
    always one link: this thing to that one. Reading a plural end is every link there is. `=`
    would claim replacement over an addition — `anna.mother_of = vera` reads as though Boris
    were gone — and the one place it would be honest, a single end, is the one place it gains
    nothing over saying it plainly.

    What a second statement does is the type's rule and is not repeated here: one value per
    subject and the later corrects the earlier; one at a time and the later ends the earlier;
    several and they stand together.
    """
    kind = rel["kind"]
    word = (rel.get("reverse") or kind) if backwards else kind

    def state(self, other, *, starts=None, until=None, ttl=None, permanent: bool = False,
              **attrs):
        a, b = (other, self) if backwards else (self, other)
        return current_world().relate(a, b, kind, starts=starts, until=until, ttl=ttl,
                                      permanent=permanent, **attrs)

    state.__name__ = f"set_{word}"
    state.__doc__ = (f"{rel.get('reads') or kind}. Written: a.set_{word}(b). "
                     f"Reads back as a.{word}.")
    return state


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
            f"{class_name}.{method_name} is declared and has no implementation bound to it"
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


def _take_the_word(entity, class_name: str, name: str, value):
    """Declare an attribute nobody declared, if this world is one whose classes may grow.

    Returns the attribute spec, or None where growth is not on — a world with a fixed ontology
    refuses as it always did, because there the class list is the promise.
    """
    world = current_world()
    grow = (world.extras or {}).get("attribute")
    if grow is None or name.startswith("_"):
        return None
    made = getattr(grow, "__self__", None)
    if made is None or not hasattr(made, "provisional"):
        return None
    try:
        return made.provisional(type(entity), name, value)
    except Exception:  # noqa: BLE001 - a word the world cannot take is a word it refuses
        return None


# Asked of a host when something of this class has nothing on it but a name. Used when the class
# itself says nothing, and deliberately plain: a class that has not said what to say about one of
# these is a class that has not been thought about, and the fallback should not hide that.
SAY_SOMETHING = ("what sort of thing it is and why it is in this world — what the user said "
                 "about it, not what you happen to know")


def what_to_say(cls, classes: dict | None = None) -> str:
    """The line that asks a host to describe one of these — the class's own, or what it falls to.

    Per class, because "describe it" means different things: a person is described so they can be
    recognised when the name is said differently, an event so it can be placed in time, a link so
    it can be read as the fact it is. Asking all of them the same thing gets all of them the same
    answer, which is the encyclopaedia entry nobody asked for.

    A class that says nothing falls back to what it is a kind of. There is no class inheritance
    in this world yet, so the chain is the one that does exist: a relation type falls to the base
    relation whose nature it carries, an entity class to `Thing`, which is what anything is when
    nothing better fits. When a real parent arrives it goes at the head of the same walk.
    """
    spec = getattr(cls, "_spec", cls if isinstance(cls, dict) else {})
    seen = set()
    while spec:
        said = spec.get("what_to_say")
        if said:
            return said
        name = spec.get("name")
        if name in seen:
            break
        seen.add(name)
        classes = classes if classes is not None else getattr(cls, "_classes", None) or {}
        relation = spec.get("relation") or {}
        parent = spec.get("parent") or (_BASE_FOR.get(relation.get("nature") or relation.get("kind"))
                                        if relation else "Thing")
        nxt = classes.get(parent) if parent else None
        spec = getattr(nxt, "_spec", None) if nxt is not None else None
    return SAY_SOMETHING


# The three base relations are natures wearing a type's clothes (relations.py), so a type that
# carries one of those natures is a kind of it, and that is the whole of the inheritance here.
_BASE_FOR = {"related_to": "Related", "related": "Related"}


def _called_its_name(cls, word: str) -> bool:
    """Is `word` this class's name said another way — `full_name` on a Person, `title` on an Event?

    Only where the class has no attribute of that name of its own: a link's `label` is its label.
    """
    from terraweaver import matching

    if word == matching.NAME or word not in matching.NAME_WORDS:
        return False
    names = {a["name"] for a in getattr(cls, "_spec", {}).get("attributes", [])}
    return matching.NAME in names and word not in names


# Classes whose name was once kept under another word, and that word: what a world written
# before 2026-10-02 holds in its record and its images, for `store.one_name` to carry over.
NAMED_OTHERWISE: dict[str, str] = {"Person": "full_name", "Event": "title"}


def one_name(spec: dict) -> dict:
    """What a thing is called is its `name`, whatever the spec called it.

    A spec written as `identified_by: "title"` (a host's, or one grown in an older world) keeps
    its class and its attributes; the attribute that names the thing is `name`. What else it
    said identifies one — a code, an ISBN — stays an attribute of its own and is not the name.
    """
    from terraweaver import matching

    if spec.get("relation"):
        return spec
    attributes = [dict(a) for a in spec.get("attributes", [])]
    declared = [a.get("name") for a in attributes]
    wanted = spec.get("identified_by")
    if not isinstance(wanted, str) or wanted not in matching.NAME_WORDS:
        # Said nothing, or named something else: the name is whichever of the name's words the
        # class has, when it has no `name` — `Person` in a world grown before 2026-10-02 carries
        # its own copy of the spec, with `full_name` in it.
        wanted = next((w for w in matching.NAME_WORDS if w in declared), None) \
            if matching.NAME not in declared else None
        if wanted is None:
            return spec
    if wanted == matching.NAME:
        return spec
    if not any(a.get("name") == matching.NAME for a in attributes):
        for one in attributes:
            if one.get("name") == wanted:
                one["name"] = matching.NAME
                break
    NAMED_OTHERWISE.setdefault(spec["name"], wanted)
    out = {**spec, "attributes": attributes}
    if spec.get("identified_by") in (None, wanted) or spec.get("identified_by") in matching.NAME_WORDS:
        out["identified_by"] = matching.NAME
    return out


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
    spec = with_common_slots(one_name({**spec, "name": name}))
    if spec.get("identified_by"):
        wanted = spec["identified_by"]
        if isinstance(wanted, str):
            # `list("name")` is `['n', 'a', 'm', 'e']`, so the class came back from a reopened world
            # identified by an attribute called `n`, which nothing has. Measured 2026-09-28 on the
            # 455-fact world: **twenty** classes the reading had made — City, Country, Language,
            # Sport, Religion, University, Work — every one of them keyed on `'n'`, and the reading
            # moves entities into those classes. So a thing findable by name as a `Thing` stopped
            # being findable at all the moment it was placed, and the host answered "not recorded"
            # about facts the world held. It is why the read world scored *below* the unread one.
            wanted = {"name_keys": [wanted]}
        elif not isinstance(wanted, dict):
            wanted = {"name_keys": list(wanted)}
        if spec.get("strong_keys") and "strong_keys" not in wanted:
            wanted = {**wanted, "strong_keys": list(spec["strong_keys"])}
        matching.register_identity(name, **wanted)
    namespace = {
        "__doc__": spec.get("description", ""),
        "_spec": spec,
        # Shared, mutated-in-place: lets a method implementation reach sibling classes.
        "_classes": classes,
    }
    base = Entity
    if "relation" in spec:
        from terraweaver.relations import Relation

        base = Relation
        # A side that says it holds one holds one at a time. Specs on disk from when "one
        # ever" was a category say `True`, and there is nothing to migrate: read as what the
        # world now does, which is the only thing it ever did — the "one ever" branch printed
        # a note and ended nothing, so a world reopened here loses no behaviour it had.
        for side in ("functional", "inverse_functional"):
            if spec["relation"].get(side) is True:
                spec["relation"][side] = AT_A_TIME
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
        if str(attr.get("derived", "")).startswith("self."):
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
    standing = classes.get(name)
    if standing is not None and (standing.__bases__ == (base,)):
        # Grown, not replaced. A new class object leaves every instance already in hand —
        # and the name bound in the run's namespace — pointing at the old spec, so a host
        # that does exactly what the world just told it to do gets the same refusal twice:
        #     world.attribute(Person, "email", "...")
        #     person.email = "ada@example.org"      -> Person has no attribute 'email'
        # There is no way past that from inside the run, and the way out of a refusal that
        # repeats itself is prose. Same class, new spec: what was made before the growth
        # keeps working, and isinstance still means what it says.
        for key, value in namespace.items():
            if key != "_classes":
                setattr(standing, key, value)
        return standing
    classes[name] = made(name, (base,), namespace)
    _lend_relations(classes, name)
    return classes[name]
