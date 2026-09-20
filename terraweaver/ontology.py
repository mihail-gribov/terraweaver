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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Policy hook called before an attribute of an already-known entity is overwritten.
# Installed by the world layer; may raise to refuse the write. Kept as a hook rather
# than an import so the object model stays independent of the consistency layer.
_WRITE_GUARD = None
_TRUSTED = False
# The world the classes currently belong to, so `Person.find(...)` can reach it without
# every class having to be handed a store.
_WORLD = None

# Held by every entity, outside the JSON specs, and maintained by the machinery itself.
_MANAGED_ATTRS = ("id", "created_at", "accessed_at", "valid_from", "valid_until")

# Counts what a running script actually touched. "Did the answer come from the world, or was
# it typed?" can't be judged from the text — but it can be measured at the source.
_TRACK = False
ACCESS = {"entity_reads": 0, "world_queries": 0, "world_writes": 0}
# Entities changed while recording, keyed by id(): a script's writes have to be persisted even
# when the changed object isn't bound to any variable (`Vacancy.find(...).main[0].apply()`).
# Keyed by object identity because an entity's hash changes once it receives an id.
_CHANGED: "Recording | None" = None
# The ones that are stored as values (id is the row key, not a value).
MANAGED_VALUE_ATTRS = ("created_at", "accessed_at", "valid_from", "valid_until")


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
        self.remarks: list[str] = []  # comments added, forgotten or confirmed, as the host should read them
        self.assumed: list[str] = []  # identities taken from what the user settled before
        self.hints: list[str] = []  # what the world suggests about a write that went through
        self.questions: list[str] = []  # doubts recorded about an entity, open until the user answers
        self.ask_now: list[str] = []  # doubts this run's reads actually depend on


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


def _note_changed(entity, attr: str | None = None) -> None:
    if _CHANGED is not None:
        _CHANGED.changed[id(entity)] = entity
        if attr is not None:
            _CHANGED.attrs.setdefault(id(entity), set()).add(attr)


def note_found(entity) -> None:
    if _CHANGED is not None:
        _CHANGED.found[id(entity)] = entity


def note_assumed(text: str) -> None:
    if _CHANGED is not None and text not in _CHANGED.assumed:
        _CHANGED.assumed.append(text)


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
        now = datetime.now(timezone.utc)
        self.created_at = kwargs.pop("created_at", None) or now
        self.accessed_at = kwargs.pop("accessed_at", None) or now
        # When it holds in the world: [valid_from, valid_until). None on either side is open —
        # most things exist from when they're recorded and for good. Nothing is deleted when a
        # period ends; the entity becomes history.
        self.valid_from = kwargs.pop("valid_from", None)
        self.valid_until = kwargs.pop("valid_until", None)
        class_name = type(self).__name__
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
                raise TypeError(f"{class_name}(...) missing required attribute '{name}'")
            else:
                default = attr.get("default")
                if default is None and attr["type"].startswith("list["):
                    default = []
                setattr(self, name, default)
        if kwargs:
            raise TypeError(f"{class_name}(...) got unexpected attribute(s): {', '.join(kwargs)}")

    # --- what every class in the world can do ---

    @classmethod
    def all(cls, limit: int | None = 50, *, any_time: bool = False, history: bool = False) -> list:
        """Entities of this class, most recently worked with first — the ones that hold now;
        any_time=True adds those whose period has ended or hasn't started."""
        return current_world().all(cls, limit=limit, history=history or any_time)

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
    def new(cls, *, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        """A new entity. If one just like it already exists, the user is asked before creating."""
        return current_world().new(cls, starts=starts, until=until, ttl=ttl, permanent=permanent, **attrs)

    @classmethod
    def ensure(cls, *, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        """Existing or new — for when you genuinely can't tell which."""
        return current_world().ensure(cls, starts=starts, until=until, ttl=ttl, permanent=permanent, **attrs)

    def keep(self, *, starts=None, until=None, ttl=None, permanent: bool = False) -> None:
        """Set when this entity holds: starts=date, until=date / ttl=timedelta, permanent=True."""
        current_world().set_period(self, starts=starts, until=until, ttl=ttl, permanent=permanent)

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

    def relate(self, other, kind: str, /, *, starts=None, until=None, ttl=None, permanent: bool = False, **attrs):
        """Record that this entity stands in relation `kind` to `other`; returns the relation."""
        return current_world().relate(self, other, kind, starts=starts, until=until, ttl=ttl,
                                      permanent=permanent, **attrs)

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
        for comment in self.comments(any_time=True):
            moments.append((comment.when or comment.recorded_at, f"remark: {comment.text}"))
        for relation in (relations.relations_of(world, self, None, True) if not isinstance(self, Relation_base()) else []):
            other = relation.other(self)
            what = relation.role_of(other) or type(relation)._spec["relation"]["kind"]
            moments.append((relation.valid_from or relation.created_at, f"{what}: {other.display_name()} — from here"))
            if relation.valid_until:
                moments.append((relation.valid_until, f"{what}: {other.display_name()} — until here"))
        start = timeutil.as_datetime(since) if since is not None else None
        end = timeutil.as_datetime(until) if until is not None else None
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

    def comment(self, text: str, when=None, tentative: bool = False, until=None, ttl=None,
                starts=None, permanent: bool = False):
        """Attach a dated remark to this entity — for what its attributes have no place for.

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

    def comments(self, since=None, until=None, contains: str | None = None, include_expired: bool = False,
                 any_time: bool = False) -> list:
        """This entity's current remarks, newest first; include_expired=True adds the history."""
        return current_world().comments.of(self, since=since, until=until, contains=contains,
                                           include_expired=include_expired or any_time)

    def touch(self) -> None:
        """Mark that this entity was just worked with — the moment, and one more time in the
        count that decides whose open questions are worth the user's attention (usage.py)."""
        with trusted_writes():
            self.accessed_at = datetime.now(timezone.utc)
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

    def __setattr__(self, name, value):
        spec = type(self)._spec
        class_name = type(self).__name__
        if name not in _MANAGED_ATTRS and not name.startswith("_"):
            declared = next((a for a in spec["attributes"] if a["name"] == name), None)
            # An attribute the class doesn't have used to be accepted and then lost on save —
            # a write that looked fine and never happened.
            if declared is None:
                raise AttributeError(
                    f"{class_name} has no attribute '{name}'. Its attributes are: "
                    + ", ".join(a["name"] for a in spec["attributes"])
                    + ". What has no attribute goes into a dated remark: entity.comment(...)."
                )
            if "derived" in declared:
                if declared.get("settable"):
                    object.__setattr__(self, name, value)  # the property's setter records it
                    return
                raise TypeError(_derived_message(class_name, declared))
            _check_type(class_name, spec, name, value)
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
                world.facts.state(self.subject_id, name, _as_statement(value), source=source,
                                  run_id=run_id, class_name=type(self).__name__)
        if not name.startswith("_"):
            _note_changed(self, name)


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
        count = len(entity.comments())
    except Exception:  # noqa: BLE001 - a repr must never fail
        return ""
    return f", {count} remark{'s' if count > 1 else ''} (.comments())" if count else ""


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


def _period_text(starts, until) -> str:
    if starts is None and until is None:
        return ""
    from terraweaver import timeutil
    left = timeutil.show(starts) if starts else "…"
    right = timeutil.show(until) if until else "…"
    return f", holds {left} → {right}"


def _brief(value) -> str:
    """How a value appears inside an entity's repr — references by label, never expanded."""
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
            raise ValueError(
                f"{class_name}.{attr_name} is one of: {', '.join(allowed)} — {value!r} is none of them. "
                + (f"Use '{allowed[-1]}' and say what it is in a remark: entity.comment(...)."
                   if allowed[-1] in ("other", "misc") else
                   "Pick the closest, and put what the user actually said in a remark.")
            )
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


def _relation_property(class_name: str, attr: dict):
    """An attribute read from relations (Person.organization from the primary Membership)."""
    from terraweaver import relations

    getter, setter, _ = relations.DERIVED[(class_name, attr["name"])]

    def refuse(self, value):
        raise TypeError(f"{class_name}.{attr['name']} is derived from relations and can't be set directly")

    return property(lambda self: getter(self), setter or refuse, doc=attr.get("description", ""))


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


def build_classes(specs: dict[str, dict[str, Any]], impls: dict[tuple[str, str], Any] | None = None) -> dict[str, type]:
    impls = impls or {}
    classes: dict[str, type] = {}
    for name, spec in specs.items():
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
            ends = [
                {"name": "subject", "type": "ref:" + "|".join(spec["relation"]["from"]), "required": True,
                 "description": "Where the relation starts."},
                {"name": "object", "type": "ref:" + "|".join(spec["relation"]["to"]), "required": True,
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
            elif "derived" in attr:
                namespace[attr["name"]] = _derived_property(name, attr)
        for method in spec.get("methods", []):
            mname = method["name"]
            impl = impls.get((name, mname))
            namespace[mname] = _intentional(impl) if impl else _make_stub(name, mname)
        # Everything shared comes from Entity; a generated class carries only its own
        # spec and methods.
        classes[name] = type(name, (base,), namespace)
    return classes
