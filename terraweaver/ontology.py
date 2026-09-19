"""Loads class specs from ontology/core/*.json and builds real Python classes from them.

Attributes come purely from the JSON spec (generic). Method bodies are not derivable
from a signature + description alone, so they are looked up in `terraweaver.impls`
by (class_name, method_name); a method with no registered implementation gets a stub
that raises NotImplementedError, so gaps fail loudly instead of silently no-op-ing.
"""
import json
from contextlib import contextmanager
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


def set_world(world) -> None:
    global _WORLD
    _WORLD = world


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


def load_specs(ontology_dir: Path) -> dict[str, dict[str, Any]]:
    specs = {}
    for path in sorted(ontology_dir.glob("*.json")):
        spec = json.loads(path.read_text())
        specs[spec["name"]] = spec
    return specs


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
    def all(cls, limit: int | None = 50, *, history: bool = False) -> list:
        """Entities of this class, most recently worked with first."""
        return current_world().all(cls, limit=limit, history=history)

    @classmethod
    def find(cls, *, history: bool = False, **attrs):
        """Entities of this class matching the attributes, best match first.

        A by-name lookup that isn't a certain match returns a NeedsResolution rather than
        ranked guesses — picking one would be deciding who was meant.
        """
        return current_world().find(cls, history=history, **attrs)

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

    def current(self) -> bool:
        """Whether this entity holds now."""
        from terraweaver import timeutil
        return timeutil.in_period(getattr(self, "valid_from", None), getattr(self, "valid_until", None), timeutil.now())

    def save(self) -> None:
        """Persist this entity and everything it references."""
        current_world().save(self)

    def comment(self, text: str, when=None, tentative: bool = False, until=None, ttl=None, permanent: bool = False):
        """Attach a dated remark to this entity — for what its attributes have no place for."""
        return current_world().comments.add(self, text, when=when, tentative=tentative, until=until, ttl=ttl,
                                            permanent=permanent)

    def comments(self, since=None, until=None, contains: str | None = None, include_expired: bool = False) -> list:
        """This entity's current remarks, newest first; include_expired=True adds the history."""
        return current_world().comments.of(self, since=since, until=until, contains=contains,
                                           include_expired=include_expired)

    def touch(self) -> None:
        """Mark that this entity was just worked with."""
        with trusted_writes():
            self.accessed_at = datetime.now(timezone.utc)

    def __getattribute__(self, name):
        value = object.__getattribute__(self, name)
        # Reading an entity's attribute is contact with the world just as much as querying it
        # is: `report(owner.full_name)` makes no calls yet is perfectly grounded.
        if _TRACK and not name.startswith("_") and not callable(value):
            ACCESS["entity_reads"] += 1
        return value

    def label(self) -> str:
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
        return f"{type(self).__name__}(id={self.id!r}, {fields}{period})"

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
            _check_type(class_name, spec, name, value)
            # Stored as given, only without stray whitespace; comparisons use the kind's normalize.
            if isinstance(value, str):
                value = value.strip()
        guarded = (
            _WRITE_GUARD is not None
            and not _TRUSTED
            and not name.startswith("_")
            and name not in _MANAGED_ATTRS
            and getattr(self, "id", None) is not None  # only entities the world already knows
            and getattr(self, name, None) is not None  # only overwrites, not first assignment
        )
        if guarded:
            _WRITE_GUARD(self, name, getattr(self, name), value)  # may refuse the write
        object.__setattr__(self, name, value)
        if not name.startswith("_"):
            _note_changed(self, name)
        if name not in _MANAGED_ATTRS and not name.startswith("_"):
            _maintain_inverse(self, spec, name, value)


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
        return f"<{type(value).__name__} {value.label()}>"
    if isinstance(value, list) and any(isinstance(v, Entity) for v in value):
        shown = ", ".join(f"<{type(v).__name__} {v.label()}>" if isinstance(v, Entity) else repr(v) for v in value[:3])
        return f"[{shown}{', …' if len(value) > 3 else ''}]"
    return repr(value)


def _check_type(class_name: str, spec: dict[str, Any], attr_name: str, value) -> None:
    """Enforce declared ref types, so a bare string can't land in a relationship field."""
    if value is None:
        return
    declared = next((a["type"] for a in spec["attributes"] if a["name"] == attr_name), None)
    if not declared:
        return
    if declared.startswith("ref:"):
        expected = declared[4:]
        if expected != "any" and type(value).__name__ != expected:
            raise TypeError(
                f"{class_name}.{attr_name} must be a {expected} instance, got {type(value).__name__} "
                f"({value!r}). Get the entity first, e.g. {expected}.ensure(name=...)."
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


def _maintain_inverse(instance, spec: dict[str, Any], attr_name: str, value) -> None:
    """Keep the other side of a declared relationship in sync.

    Without this, `person.organization = acme` leaves acme.employees without the person:
    a half-link that the agent has no reason to notice and the world can't be trusted on.

    The other side's declared type decides the move: a list attribute gets appended to, a
    single reference gets assigned. Appending to everything turned `owner.assistant` into a
    list of assistants.
    """
    declared = next((a for a in spec["attributes"] if a["name"] == attr_name), None)
    if not declared or "inverse" not in declared or value is None:
        return
    _, other_attr = declared["inverse"].split(".", 1)
    other = next((a for a in type(value)._spec["attributes"] if a["name"] == other_attr), None)
    _note_changed(value, other_attr)
    if other is not None and not other["type"].startswith("list["):
        if getattr(value, other_attr, None) is not instance:
            object.__setattr__(value, other_attr, instance)
        return
    current = getattr(value, other_attr, None)
    if current is None:
        current = []
        object.__setattr__(value, other_attr, current)
    if instance not in current:
        current.append(instance)


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
        for method in spec.get("methods", []):
            mname = method["name"]
            impl = impls.get((name, mname))
            namespace[mname] = _intentional(impl) if impl else _make_stub(name, mname)
        # Everything shared comes from Entity; a generated class carries only its own
        # spec and methods.
        classes[name] = type(name, (Entity,), namespace)
    return classes


COMMON_MEMBERS = """\
Every class below shares these, so they aren't repeated for each one:

    id           — how this entity is known in the world
    created_at   — when it entered the world
    accessed_at  — when it was last worked with

    Class.all(limit=50)
        Entities of that class, the ones you dealt with most recently first. Limited by
        default, because a personal world keeps growing; pass limit=None for everything.

    Class.find(**attrs)
        Entities matching every attribute you pass, best match first (ties go to whoever
        you dealt with most recently). Ordinary attributes match exactly, so this is how
        you ask real questions of the world:
            Person.find(organization=acme)      — who works there
            Vacancy.find(remote=True, status="not_applied")
            Person.find(email="ada@example.com")
        Times and numbers take ranges — after(x), before(x), between(a, b) — which compare dates
        and datetimes safely whatever their time zone (use now() and today() for "now"):
            Event.find(start_time=after(now()))                               — upcoming
            Event.find(start_time=between(date(2026, 9, 21), date(2026, 9, 27)))  — that week
            Vacancy.find(salary_max=after(150000))
        Emails, phones and URLs compare in their canonical form, whatever way they're written:
        "+1 (555) 010-2030" finds "+15550102030", "Ada@Example.com" finds "ada@example.com",
        a company website matches on its domain (https://careers.acme.com/jobs ~ acme.com).

        The result comes back in two parts, and the difference matters:
            result.main     — entities that actually match
            result.similar  — entities that merely resemble what you asked for
            result.matched  — False when nothing actually matched
        Iterating the result gives everything, best first, so it still works as a list —
        but `result[0]` may well be a resemblance. When `result.matched` is False, nothing
        in the world matches: say so, rather than serving the closest thing as the answer.
        A person's recorded nicknames count as their names, so "Bob" finds Robert.

        Looking someone up by name gives a NeedsResolution instead of a result whenever it
        isn't settled — several people answer to that name, or nothing matches it exactly
        and only resemblances turned up. Which of them was meant is not yours to decide.

    Recording what the user tells you starts with a decision only you can make from the
    conversation: is it about someone/something already in the world, or new? Say so by the
    call you pick — the world checks the claim instead of deciding silently.

    Class.get(**attrs)
        "The one we already know." Use everything the user said to pick it out:
        Person.get(full_name="Annie", organization=cloudnine). Returns that entity, or a
        NeedsResolution if several fit. Never creates: if nothing matches, it raises NotInWorld
        — then either the user means someone new (use new) or you misidentified them.
    Class.new(**attrs)
        "Someone/something new." Creates it — unless one just like it already exists (same
        email, same name at the same company, the same event on the same day); then you get
        a NeedsResolution asking the user whether it's really new.
    Class.ensure(**attrs)
        "I can't tell." Finds it or creates it; the attributes are new information, so a value
        contradicting what's stored comes back as a question. Prefer get or new whenever the
        conversation tells you which it is.

    After each run the result lists what happened: [created], [updated] with the attributes
    that changed, [found]. Check it matches what you meant.

    entity.save()
        Persist that entity and everything it references.

    When a record holds. An entity holds from when it's recorded and for good, unless told
    otherwise: Class.ensure(..., starts=date(...)) for what begins later (a job from October),
    until=date(...) / ttl=timedelta(...) for what ends (a listing open for a month). Nothing is
    deleted when its period ends — it becomes history. entity.keep(starts=..., until=... |
    ttl=... | permanent=True) changes the period, entity.expire() ends it now,
    entity.current() asks whether it holds. Reads show what holds now; history=True in
    Class.all / Class.find includes ended and not-yet-started ones.
    This is not an event's own time: a past meeting and next week's one both hold — find them
    by their start_time like any attribute.

    entity.comment(text, when=None, tentative=False, until=None, ttl=None, permanent=False)
        Attach a dated remark to any entity: whatever matters about it but has no attribute —
        a friend's allergy, "hiring frozen since March", "might move in spring". `when` is the
        date it happened or holds (a date or datetime), if known; tentative=True for what isn't
        certain yet. Say how long it holds: until=date(...), ttl=timedelta(days=7) ("on vacation
        until Friday", a pickup code), or permanent=True (an allergy). Unsaid, it holds 180 days,
        a tentative one 30. Prefer a real attribute when one exists; never invent attributes.
    entity.comments(since=None, until=None, contains=None, include_expired=False)
        That entity's current remarks, newest first; expired ones are history, shown only with
        include_expired=True. Each has .text, .when, .until, .expired, .recorded_at,
        .tentative, .about, and .forget() (delete for good), .confirm(),
        .keep(until=... | ttl=... | permanent=True) to change how long it holds.
    world.comments(since=None, until=None, contains=None, include_expired=False)
        Remarks across the whole world.
"""


def describe_for_prompt(specs: dict[str, dict[str, Any]]) -> str:
    """Render class specs as compact text for the agent's system prompt."""
    lines = []
    for name, spec in specs.items():
        lines.append(f"class {name}:  # {spec.get('description', '')}")
        for attr in spec["attributes"]:
            req = "required" if attr.get("required") else "optional"
            default = f", default={attr['default']!r}" if "default" in attr else ""
            lines.append(f"    {attr['name']}: {attr['type']}  # {req}{default} — {attr.get('description', '')}")
        for method in spec.get("methods", []):
            lines.append(f"    def {method['signature']}:  # {method.get('description', '')}")
        lines.append("")
    return "\n".join(lines)
