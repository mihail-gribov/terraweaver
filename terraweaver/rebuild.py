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

from terraweaver import assembly, ontology, tags


# Which subjects each image is made of, as the last whole assembly glued them. Kept, because the
# image after one run is assembled from its own subjects alone (`refresh`) and gluing is a question
# about the whole world, asked at the close.
GLUED = """
CREATE TABLE IF NOT EXISTS image_subjects (
    subject TEXT PRIMARY KEY,
    image_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_image_subjects_image ON image_subjects(image_id);
"""


def _glued(conn) -> None:
    for statement in GLUED.strip().split(";"):
        if statement.strip():
            conn.execute(statement)


def rebuild(world, rule=None, at: datetime | None = None) -> dict:
    """Throw away the images and build them again from the statements. Returns what was built."""
    images = assembly.assemble(world.facts, rule or assembly.same_name, at, world.specs)
    built: dict = {}
    with world.store.transaction(), ontology.trusted_writes(), ontology.not_recording(), \
            ontology.filling_from_record():
        _glued(world.store.conn)
        world.store.conn.execute("DELETE FROM image_subjects")
        world.store.conn.executemany(
            "INSERT OR REPLACE INTO image_subjects (subject, image_id) VALUES (?, ?)",
            [(subject, image.id) for image in images.values() for subject in image.subjects])
        for class_name, cls in world.classes.items():
            # Not what the world is told — what the world keeps for itself. A Task is the one
            # such class: it says where a piece of work started and stopped, which nobody ever
            # states as a fact and which no statement can therefore put back. Clearing it here
            # meant a rebuilt world had run no tasks at all, so every fact in it lost the one
            # thing that said what it had been recorded for.
            if cls._spec.get("own"):
                continue
            world.store.clear(class_name)
        # Ids first, values second: an entity may refer to one that hasn't been built yet.
        for image in images.values():
            class_name = _class_of(world, image)
            if class_name not in world.classes:
                continue
            if world.classes[class_name]._spec.get("own"):
                # Its table was left alone above, so there is nothing here to put back — and
                # building it anyway would overwrite it with a partial reading. Two abandoned
                # tasks carried a single statement each (the note saying why they were dropped)
                # and came back as that note and nothing else: no `stated`, no mode, no work.
                continue
            entity = object.__new__(world.classes[class_name])
            entity.id = image.id
            # The image is built from these; new words about it attach to the leading one.
            entity.__dict__["_subject"] = image.id
            entity.__dict__["_subjects"] = list(image.subjects)
            built[image.id] = entity
            # Under every name it ever went by. When two subjects turn out to be one person the
            # image keeps one id, and anything pointing at the other one was left pointing at
            # nothing — which did not fail where it was written but where it was read, and took
            # every other link of that class down with it.
            for subject in image.subjects:
                built.setdefault(subject, entity)
        for image in images.values():
            entity = built.get(image.id)
            if entity is None:
                continue
            _fill(world, entity, image, built)
            world.store.save(entity)
    # The two parties are not built from statements — they are what a world is between, and a
    # world with neither has no "me" and no "you" to hang anything on. Rebuilding used to be
    # rare enough that losing them went unnoticed; `become` and `take_in` rebuild whenever the
    # host learns a word, and the first run that used them ended with both gone.
    world.ensure_selves()
    return built


class _Leaders:
    """For a subject a value points at, the image it is part of — read from the last gluing."""

    def __init__(self, conn):
        self.conn = conn

    def get(self, subject, default=None):
        if subject is None:
            return default
        row = self.conn.execute("SELECT image_id FROM image_subjects WHERE subject = ?",
                                (subject,)).fetchone()
        return row[0] if row else subject


class _Loaded:
    """The entities a refreshed image points at, loaded as they are — the `built` of a rebuild,
    for a few things rather than for all of them."""

    def __init__(self, world, held: dict):
        self.world, self.held = world, held

    def __contains__(self, value) -> bool:
        # By the table, not by the shape: the two parties are `person:user` and `agent:assistant`,
        # and a link to the user read as a link to nobody.
        if not isinstance(value, str) or not value:
            return False
        if value in self.held:
            return True
        return self.world.store.conn.execute(
            "SELECT 1 FROM instances WHERE id = ?", (value,)).fetchone() is not None

    def __getitem__(self, value):
        if value in self.held:
            return self.held[value]
        return self.world.store.load(value, self.world.classes)


def spoken_of(world, subjects) -> list:
    """The entities these subjects build, as they are held now — each image once."""
    conn = world.store.conn
    _glued(conn)
    out, seen = [], set()
    for subject in subjects:
        row = conn.execute("SELECT image_id FROM image_subjects WHERE subject = ?",
                           (subject,)).fetchone()
        image_id = row[0] if row else subject
        if image_id in seen:
            continue
        seen.add(image_id)
        if conn.execute("SELECT 1 FROM instances WHERE id = ?", (image_id,)).fetchone() is None:
            continue
        try:
            one = world.store.load(image_id, world.classes)
        except Exception:  # noqa: BLE001 - a thing that will not load keeps the image it has
            continue
        if one is not None:
            out.append(one)
    return out


def refresh(world, entities) -> int:
    """The images of these things assembled from the record, into the objects already held.

    Rule 4 of docs/engine/architecture.md, after every run rather than only at the close: whatever a door
    put on an object, what the image holds when the run ends is what the statements say. Into the
    same objects, so every variable a host holds still holds the thing; from the subjects each was
    already made of, so nothing is glued or split here. The two parties are left alone — the tie
    between them is not a statement — and so is the world's own bookkeeping. Returns how many were
    assembled.
    """
    from terraweaver.world import THE_PARTIES

    conn = world.store.conn
    _glued(conn)
    held = {}
    for one in entities:
        if (getattr(one, "id", None) is None or one.id in THE_PARTIES or one._spec.get("own")
                or not world.store.is_live(one)):
            continue
        held[one.id] = one
    if not held:
        return 0
    groups = {}
    for image_id in held:
        rows = conn.execute("SELECT subject FROM image_subjects WHERE image_id = ?",
                            (image_id,)).fetchall()
        groups[image_id] = [r[0] for r in rows] or [held[image_id].subject_id]
    # The classes as they are now — one made during this run is not in the specs the world opened
    # with, and read without it a list slot came back as the letters of its one value.
    specs = {name: cls._spec for name, cls in world.classes.items()}
    images = assembly.assemble_these(world.facts, groups, _Leaders(conn), None, specs)
    loaded = _Loaded(world, held)
    done = 0
    with world.store.transaction(), ontology.trusted_writes(), ontology.not_recording(), \
            ontology.filling_from_record():
        for image_id, entity in held.items():
            image = images.get(image_id)
            if image is None or _class_of(world, image) not in (None, type(entity).__name__):
                continue          # nothing said about it yet, or it is becoming something else
            looked_at = entity.__dict__.get("accessed_at")   # attention, not a fact: kept
            _fill(world, entity, image, loaded)
            if looked_at is not None:
                entity.accessed_at = looked_at
            world.store.save(entity)
            done += 1
    return done


def _class_of(world, image) -> str | None:
    became = assembly.became(world.facts, image.subjects)
    if became and became in world.classes:
        return became
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
    # And what those two moments are — said, or worked out at a hand-over ("before"). Read back
    # like the rest: dropped, a rebuilt world could no longer tell a date somebody gave from one
    # the world inferred, which is the whole of comparing like with like (`_which_is_later`).
    entity.from_is = entity.until_is = None
    for slot, value in image.values.items():
        if slot in ("from_is", "until_is"):
            setattr(entity, slot, value if isinstance(value, str) else None)
            continue
        if slot in declared or slot in ("valid_from", "valid_until"):
            kind = declared.get(slot, {}).get("type", "datetime" if slot.startswith("valid_") else "")
            try:
                read = _value(value, built, kind)
                if slot == "tags":
                    # The record keeps a tag as it was said; the world keeps one form of it
                    # (tags.canonical). Writing one puts the tidied form on the entity, and a
                    # rebuild that skipped this step put the raw one back — so the same thing
                    # read "looked at" after a rebuild and "looked-at" before it.
                    read = tags.tidy(read)
                setattr(entity, slot, read)
            except (TypeError, ValueError) as wrong:
                # A class can be declared after the fact it disagrees with. The record is what
                # was said and the image is a reading of it, so a reading that cannot be made
                # leaves that one attribute unset — it must never stop the world being built.
                # Refusing here made a world unopenable because a type defined on Tuesday did
                # not fit a link written on Monday.
                ontology.note_hint(
                    f"{type(entity).__name__}.{slot} is in the record as something the class no "
                    f"longer allows ({str(wrong).split('.')[0][:90]}) — left unset. What was said "
                    f"is still there; the class or the statement has to give."
                )
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
