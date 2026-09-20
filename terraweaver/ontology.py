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

    def comment(self, text: str, when=None, tentative: bool = False, until=None, ttl=None, permanent: bool = False):
        """Attach a dated remark to this entity — for what its attributes have no place for."""
        return current_world().comments.add(self, text, when=when, tentative=tentative, until=until, ttl=ttl,
                                            permanent=permanent)

    def comments(self, since=None, until=None, contains: str | None = None, include_expired: bool = False,
                 any_time: bool = False) -> list:
        """This entity's current remarks, newest first; include_expired=True adds the history."""
        return current_world().comments.of(self, since=since, until=until, contains=contains,
                                           include_expired=include_expired or any_time)

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
        if not name.startswith("_"):
            _note_changed(self, name)


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

    Relations link two entities and carry their own data (docs: "Relation types" below).
    Direction is one rule: the subject is the one the label describes, so a.relate(b, kind,
    label=X) reads "a is b's X". maria.relate(michael, "kin", label="mother") says Maria is
    Michael's mother; nina.relate(michael, "service", label="dentist") says Nina is Michael's
    dentist. Read the sentence before you write the call — "my dentist is Nina" puts Nina first,
    not the owner. From the other end, use the reverse name: michael.relate(greg, "served_by",
    label="landlord") says Greg is Michael's landlord. Results show each relation as that
    sentence — check it reads the way you meant. A relation's period
    reads back under the same names it's written with: rel.starts, rel.until. The label is matched to the type's roles ("mom" -> mother,
    "older brother" -> sibling), and the world checks each role's limits — a second mother is
    refused with the alternatives (stepmother). relation.role_of(entity) says what an end is to
    the other ("child" for Michael). a.how_related(b) walks the relations and names the chain
    ("sister's husband" -> sibling in law).
        kevin.relate(b04, "membership", title="vendor logistics lead", starts=date(2026, 1, 15))
        kevin.relate(darren, "kin", label="older brother")
        linda.relate(b04, "authority", label="manager")
        b04.relate(company, "part_of")
    relate returns the relation — assign its attributes like any entity's (m.title = "team lead"),
    comment on it, end it (m.expire()). entity.relations(kind) gives the relations themselves;
    entity.related(kind) the entities at the other end — also by the reverse name (b04.related(
    "members")) and along chains (kevin.related("membership") includes the company B04 is part
    of). What no type fits: a.relate(b, "related", label="godfather", description="…").
    Person.organization / job_title / relationship read from these relations and can be assigned.

    Assigning an attribute (anna.email = "...") is your statement — the user said so or you
    concluded it — and it goes through as it is. The old value isn't lost:
    entity.history("email") lists what it held before and until when.

    Time is one axis for the whole world, and the same words mean the same thing everywhere.
    Three times are easy to confuse, so keep them apart:
      when it's true   — the validity period, starts / until. Every entity and every relation
                         has one. A job that ran March to September, a lease to next June.
      when it happened — the thing's own time, an ordinary attribute: Event.start_time, a
                         comment's when. A past meeting and next week's one are both valid
                         records; find them by that attribute (Event.find(start_time=after(now()))).
      when we learned  — created_at / recorded_at, the world's bookkeeping. A marriage recorded
                         today may have started in 2019; you never set this.
    Writing a period, the same four keywords for entities, relations and comments:
        Class.ensure(..., starts=date(2026, 10, 1))   — begins later
        Class.ensure(..., until=date(...) | ttl=timedelta(days=30))
        kevin.relate(b04, "membership", title="lead", starts=date(2026, 1, 15))
        entity.keep(starts=..., until=... | ttl=... | permanent=True); entity.expire() ends it
        now; entity.current() asks whether it holds. Nothing is deleted when a period ends — it
        becomes history.
    Reading, the default is now — that's why "who is her partner" doesn't return an ex. One
    keyword widens any read: any_time=True in Class.all, Class.find, entity.relations,
    entity.related, entity.comments, world.comments. It adds both ended and not-yet-started
    ones — the future is not history. When a read hides something, you get a [hint] saying so.
    entity.timeline(since=None, until=None)
        Everything dated about one entity or relation, oldest first — when it was recorded, when
        its period starts and ends, what its attributes were changed to and when, its dated
        remarks, its relations starting and ending. Each moment has .when and .what. This is the
        one call for "what happened with this, and when", instead of assembling history(),
        comments() and relations(any_time=True) by hand.
    Conflicts are judged by overlapping periods, not by "now": one employer at a time, one
    mother, one CEO — but divorced in 2020 and married in 2022 contradict nothing.

    entity.comment(text, when=None, tentative=False, until=None, ttl=None, permanent=False)
        Attach a dated remark to any entity: whatever matters about it but has no attribute —
        a friend's allergy, "hiring frozen since March", "might move in spring". `when` is the
        date it happened or holds (a date or datetime), if known; tentative=True for what isn't
        certain yet. Say how long it holds: until=date(...), ttl=timedelta(days=7) ("on vacation
        until Friday", a pickup code), or permanent=True (an allergy). Unsaid, it holds 180 days,
        a tentative one 30. Prefer a real attribute when one exists; never invent attributes.
    entity.comments(since=None, until=None, contains=None, any_time=False)
        That entity's current remarks, newest first; expired ones are history, shown only with
        any_time=True. Each has .text, .when, .until, .expired, .recorded_at,
        .tentative, .about, and .forget() (delete for good), .confirm(),
        .keep(until=... | ttl=... | permanent=True) to change how long it holds.
    world.comments(since=None, until=None, contains=None, any_time=False)
        Remarks across the whole world.
"""


def describe_for_prompt(specs: dict[str, dict[str, Any]]) -> str:
    """Render class specs as compact text for the agent's system prompt.

    Entity classes come first, each with its attributes, methods and the relations it takes part
    in; then the relation types, each with how it behaves and its own attributes.
    """
    from terraweaver.relations import describe_relations

    lines = []
    entities = {n: s for n, s in specs.items() if "relation" not in s}
    relation_types = {n: s for n, s in specs.items() if "relation" in s}
    for name, spec in entities.items():
        lines.append(f"class {name}:  # {spec.get('description', '')}")
        lines += _attribute_lines(spec)
        for method in spec.get("methods", []):
            lines.append(f"    def {method['signature']}:  # {method.get('description', '')}")
        if relation_types:
            lines.append("    relations:  # entity.relate(other, kind, ...), entity.related(kind)")
            lines += describe_relations(specs, name)
        lines.append("")
    if relation_types:
        lines.append("Relation types — instances linking a subject and an object, with their own attributes and")
        lines.append("validity period (starts / until), history and comments.")
        lines.append("")
        lines.append("Direction, one rule for every type: the subject is the one the label describes.")
        lines.append("a.relate(b, kind, label=X) reads as the sentence \"a is b's X\" — so the dentist, the")
        lines.append("manager, the mother stands first. Say it out loud before writing it; each type below")
        lines.append("shows the sentence its example makes, and results print every relation as that sentence.")
        lines.append("To say it from the other end, use the reverse name: michael.relate(nina, \"served_by\",")
        lines.append("label=\"dentist\") records the same relation, read from the client's side.")
        lines.append("")
        for name, spec in relation_types.items():
            rel = spec["relation"]
            traits = [t for t in ("symmetric", "transitive", "acyclic") if rel.get(t)]
            if rel.get("functional") == "at_any_time":
                traits.append("one at a time per subject")
            if rel.get("inverse_functional") == "at_any_time":
                traits.append("one at a time per object")
            if rel.get("transitive_via"):
                traits.append(f"extends through {rel['transitive_via']}")
            if rel.get("reverse"):
                traits.append(f"read from the object's end as '{rel['reverse']}'")
            arrow = "↔" if rel.get("symmetric") else "→"
            lines.append(f"relation {name} ('{rel['kind']}'): {' / '.join(rel['from'])} {arrow} "
                         f"{' / '.join(rel['to'])}  # {spec.get('description', '')}")
            if traits:
                lines.append(f"    # {'; '.join(traits)}")
            if rel.get("example"):
                lines.append(f"    {rel['example']}   # {rel.get('reads', '')}")
            if rel.get("roles"):
                shown = []
                for r in rel["roles"]:
                    limit = f" (at most {r['max']})" if r.get("max") else ""
                    names = ", ".join(r.get("synonyms", [])[:3])
                    shown.append(f"{r['name']}{limit}" + (f" [{names}]" if names and names != r["name"] else ""))
                lines.append(f"    # roles — a.relate(b, '{rel['kind']}', label=...) reads 'a is b's label': {'; '.join(shown)}")
            elif rel.get("labels"):
                lines.append(f"    # typical labels: {', '.join(rel['labels'][:8])}")
            lines += [line for line in _attribute_lines(spec) if not line.lstrip().startswith(("subject:", "object:"))]
            lines.append("")
    return "\n".join(lines)


def _attribute_lines(spec: dict[str, Any]) -> list[str]:
    lines = []
    for attr in spec["attributes"]:
        req = "required" if attr.get("required") else "optional"
        default = f", default={attr['default']!r}" if "default" in attr else ""
        if attr.get("derived") == "relation":
            access = "settable, " if attr.get("settable") else "read-only, "
            lines.append(f"    {attr['name']}: {attr['type']}  # {access}from relations — {attr.get('description', '')}")
        elif "derived" in attr:
            lines.append(f"    {attr['name']}: {attr['type']}  # read-only, from {attr['derived']} — {attr.get('description', '')}")
        else:
            lines.append(f"    {attr['name']}: {attr['type']}  # {req}{default} — {attr.get('description', '')}")
    return lines
