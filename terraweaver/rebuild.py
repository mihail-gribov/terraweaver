"""Building the entities from what was said.

The basic world is two things and no more: statements, and the entities built from them. Every
other floor — doubts, ticks, growth, procedures, judgements — sits on top and can be taken away.
This is the joint between the two, and it is deliberately the dullest code here: it reads
statements, asks assembly.py who is who and which value shows, and writes the result into the
image tables.

Two properties are worth more than any feature and are tested as such:

- **the same statements build the same entities.** Rebuild twice and nothing differs. A world
  whose images depend on the order things happened is one you cannot reason about.
- **rebuilding states nothing.** It is a derivation, not a conversation: no statement is made,
  nothing is timestamped anew, and running it a hundred times leaves the record as it was.

So `rebuild()` is always available and always safe: after a rule changes, after facts arrive,
after a bad merge, or on a hunch that something is off.
"""
from datetime import datetime

from terraweaver import assembly, ontology


def rebuild(world, rule=None, at: datetime | None = None) -> dict:
    """Throw away the images and build them again from the statements. Returns what was built."""
    images = assembly.assemble(world.facts, rule or assembly.same_name, at, world.specs)
    built: dict = {}
    with world.store.transaction(), ontology.trusted_writes(), ontology.not_recording():
        for class_name in world.classes:
            world.store.clear(class_name)
        # Ids first, values second: an entity may refer to one that hasn't been built yet.
        for image in images.values():
            class_name = _class_of(world, image)
            if class_name not in world.classes:
                continue
            entity = object.__new__(world.classes[class_name])
            entity.id = image.id
            # The image is built from these; new words about it attach to the leading one.
            entity.__dict__["_subject"] = image.id
            entity.__dict__["_subjects"] = list(image.subjects)
            built[image.id] = entity
        for image in images.values():
            entity = built.get(image.id)
            if entity is None:
                continue
            _fill(world, entity, image, built)
            world.store.save(entity)
    return built


def _class_of(world, image) -> str | None:
    for subject in image.subjects:
        known = world.facts.class_of(subject)
        if known:
            return known
    return None


def _fill(world, entity, image, built: dict) -> None:
    """Put the resolved values on the entity, as the class declares them."""
    spec = type(entity)._spec
    declared = {a["name"]: a for a in spec["attributes"] if "derived" not in a}
    for name, attribute in declared.items():
        setattr(entity, name, [] if attribute.get("type", "").startswith("list[") else None)
    entity.valid_from = entity.valid_until = None  # when it holds is stated too, and may be unset
    for slot, value in image.values.items():
        if slot in declared or slot in ("valid_from", "valid_until"):
            kind = declared.get(slot, {}).get("type", "datetime" if slot.startswith("valid_") else "")
            setattr(entity, slot, _value(value, built, kind))
    said = [s for subject in image.subjects for s in world.facts.about(subject)]
    first = min((s.stated_at for s in said), default=None)
    entity.created_at = first or ontology.now_utc()
    entity.accessed_at = max((s.last_said for s in said), default=entity.created_at)


def _value(value, built: dict, kind: str = ""):
    """A stored value as the object model wants it: a subject id becomes the entity it names, and
    a moment written down as text becomes a moment again."""
    if isinstance(value, str) and value in built:
        return built[value]
    if isinstance(value, list):
        return [_value(item, built, kind[5:-1] if kind.startswith("list[") else kind)
                for item in value]
    if isinstance(value, str) and kind in ("datetime", "date"):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value
