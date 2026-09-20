"""The two parties, described by files the way personal agents are configured.

Every world is between a person and an assistant, and both are in it as ordinary entities — so
a relationship can point at them, a remark can be about them, and "my dentist" has a "my". What
they *are*, though, is not something the world should invent or the host should have to type in:
it is configuration, and personal agents keep configuration in files next to the work.

    USER.md, ABOUT_ME.md, ABOUT.md     who the world belongs to
    soul.md, SOUL.md, AGENT.md         who is keeping it

Every one of them that exists is read, not just the first: a person may keep their character in
soul.md and their working setup in AGENT.md, and both say something about the same entity. Each
file states what it says under its own name, and the ordinary rules build one image out of all
of them — the same way conversation and a register do.

`AGENTS.md` and `CLAUDE.md` are deliberately not read: they describe the project and how to work
in it, not the assistant. A world that read them as "who I am" would file commit conventions as
someone's character.

Either may have a front matter block of plain `key: value` lines for what belongs in attributes;
everything after it is kept as the entity's notes.

    ---
    full_name: Michael Gribov
    email: mike@example.com
    ---
    Works on TerraWeaver. Prefers being asked before anything is recorded about his family.

The world watches both files: when one changes, what it says is stated again. These are facts
like any others — reliable ones, because a person wrote them deliberately, but not a separate
kind of truth. They carry the file as their source, they join what conversation and sources have
said about the same two entities, and the ordinary rules build one image out of all of it. A
line removed from the file is a statement retracted, not a value deleted: what the file used to
say stays in the record like everything else.

Because the file is a named source rather than the user speaking, something the user says in
conversation outranks it — which is right: the file is last year's intention, the sentence is
this morning's. The world says so rather than quietly disagreeing with the file.
"""
import hashlib
import re
from pathlib import Path

# Where each party may be described. All of them are read; later files in the list state later,
# so where two disagree about the same slot the further one down wins.
FILES = {
    "user": ("USER.md", "ABOUT_ME.md", "ABOUT.md"),
    "agent": ("soul.md", "SOUL.md", "AGENT.md"),
}

# Where the part of a file below its front matter belongs. For a person it is a note about them;
# for the assistant it is what the file is for in the first place — who it is.
BODY_GOES_TO = {"user": "notes", "agent": "character"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS self_files (
    role TEXT NOT NULL,
    path TEXT NOT NULL,
    digest TEXT NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (role, path)
);
"""

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)


def parse(text: str) -> tuple[dict, str]:
    """(what the front matter sets, what the rest of the file says)."""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}, text.strip()
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, value = line.split(":", 1)
            if value.strip():
                fields[key.strip()] = value.strip()
    return fields, match.group(2).strip()


def find(home: Path, role: str) -> list[Path]:
    """Every file that describes this party, in the order they are read."""
    return [home / name for name in FILES[role] if (home / name).exists()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


class SelfFiles:
    """What the world remembers about the files, so it only rebuilds when they change."""

    def __init__(self, store):
        self.store = store
        store.conn.executescript(SCHEMA)

    def changed(self, role: str, path: Path) -> bool:
        row = self.store.conn.execute(
            "SELECT digest FROM self_files WHERE role = ? AND path = ?", (role, str(path))).fetchone()
        return row is None or row[0] != digest(path)

    def remember(self, role: str, path: Path) -> None:
        from datetime import datetime, timezone

        self.store.conn.execute(
            "INSERT OR REPLACE INTO self_files (role, path, digest, read_at) VALUES (?, ?, ?, ?)",
            (role, str(path), digest(path), datetime.now(timezone.utc).isoformat()))
        self.store.conn.commit()

    def forget(self) -> None:
        self.store.conn.execute("DELETE FROM self_files")


def refresh(world, home: Path) -> list[str]:
    """State what the files say, for whichever of them has changed. Returns what was read.

    Two steps, and the first is what makes a file editable rather than merely readable: whatever
    this file said before is retracted, then what it says now is stated. Remove a line and the
    value goes with it — without anything being deleted, because a retracted statement is still
    in the record.
    """
    from terraweaver import ontology

    if home is None or not Path(home).exists():
        return []
    files = SelfFiles(world.store)
    read = []
    for role, entity in (("user", world.owner), ("agent", world.me)):
        for path in find(Path(home), role):
            if entity is None or not files.changed(role, path):
                continue
            read.append(_read_into(world, files, role, entity, path))
    return [line for line in read if line]


def _read_into(world, files: "SelfFiles", role: str, entity, path: Path) -> str:
    """Retract what this file said before, state what it says now, and remember its shape."""
    from terraweaver import ontology

    if True:
        fields, body = parse(path.read_text())
        source = path.name
        said_before = set()
        for statement in world.facts.about(entity.id):
            if statement.source == source:
                said_before.add(statement.slot)
                world.facts.retract(statement.id)
        declared = {a["name"] for a in type(entity)._spec["attributes"] if "derived" not in a}
        stated = {name: value for name, value in fields.items() if name in declared}
        body_slot = BODY_GOES_TO.get(role, "notes")
        if body and body_slot in declared:
            stated[body_slot] = body
        for name, value in stated.items():
            world.facts.state(entity.id, name, value, source=source,
                              class_name=type(entity).__name__)
        # Until images are built from statements, the file also writes through to the entity;
        # when assembly takes over (docs/architecture.md, step 2) this half goes away.
        with ontology.trusted_writes():
            for name in said_before - set(stated):  # a line taken out of the file takes its value
                setattr(entity, name, None)
            for name, value in stated.items():
                setattr(entity, name, value)
        world.save(entity)
        files.remember(role, path)
        return f"{role} from {path.name}"
