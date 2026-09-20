"""The third level of change: methods the world writes for itself.

A world changes at three levels, and they are not alike — in how freely they change, what it
costs to be wrong, and how a change is taken back:

    data          a statement is added; a wrong one is retracted and images rebuild (facts.py)
    descriptions  a class gains an attribute; the file is deleted and classes rebuild (growth.py)
    methods       a procedure is written; it is dropped, and nothing but the procedure is lost

This module is the third. A procedure is a named piece of code the world keeps because the same
work kept being written by hand: "everyone at this company", "how this person and I are
connected". It is stored, not hand-edited into the repository, because it is the world's own and
must be as easy to drop as it was to add.

Three things keep it honest:

- it goes through the same sandbox as host code, and is checked when it is defined, not when it
  is first called — a procedure that can't be checked is never stored;
- it counts its uses. A procedure nobody calls is not memory, it is clutter, and `forgotten()`
  names the ones to drop;
- it may only read and write through the object model, like any host code. There is no privileged
  path: the world's own methods are bound by the same rules as the agent's.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from terraweaver import sandbox

SCHEMA = """
CREATE TABLE IF NOT EXISTS procedures (
    name TEXT PRIMARY KEY,
    attaches_to TEXT,            -- a class name, or NULL for a world-level procedure
    signature TEXT NOT NULL,     -- "colleagues(self)" as the host reads it
    body TEXT NOT NULL,          -- the source, checked before it was stored
    because TEXT NOT NULL,       -- why it exists: what kept being written by hand
    added_at TEXT NOT NULL,
    uses INTEGER NOT NULL DEFAULT 0,
    last_used TEXT
);
"""


@dataclass
class Procedure:
    name: str
    attaches_to: str | None
    signature: str
    body: str
    because: str
    added_at: datetime
    uses: int
    last_used: datetime | None

    def __repr__(self):
        where = f"{self.attaches_to}." if self.attaches_to else "world."
        return f"<procedure {where}{self.signature}, used {self.uses}x>"


class Procedures:
    def __init__(self, store):
        self.store = store
        store.conn.executescript(SCHEMA)

    def define(self, name: str, signature: str, body: str, because: str,
               attaches_to: str | None = None) -> Procedure:
        """Keep this piece of work under a name. Checked here, so a procedure that could not run
        is never stored — the world doesn't get to save itself a landmine."""
        if not because.strip():
            raise ValueError("say why this procedure exists — what kept being written by hand")
        sandbox.check(body)  # raises SandboxViolation or SyntaxError, and nothing is stored
        compile(f"def {signature}:\n" + "\n".join("    " + line for line in body.splitlines()),
                f"<procedure {name}>", "exec")
        self.store.conn.execute(
            "INSERT OR REPLACE INTO procedures (name, attaches_to, signature, body, because, added_at, uses) "
            "VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT uses FROM procedures WHERE name = ?), 0))",
            (name, attaches_to, signature, body, because.strip(),
             datetime.now(timezone.utc).isoformat(), name),
        )
        self.store.conn.commit()
        return self.get(name)

    def drop(self, name: str) -> None:
        self.store.conn.execute("DELETE FROM procedures WHERE name = ?", (name,))
        self.store.conn.commit()

    def get(self, name: str) -> Procedure | None:
        row = self.store.conn.execute(
            "SELECT name, attaches_to, signature, body, because, added_at, uses, last_used "
            "FROM procedures WHERE name = ?", (name,)).fetchone()
        return _row(row)

    def all(self) -> list[Procedure]:
        return [_row(r) for r in self.store.conn.execute(
            "SELECT name, attaches_to, signature, body, because, added_at, uses, last_used "
            "FROM procedures ORDER BY uses DESC, name")]

    def used(self, name: str) -> None:
        self.store.conn.execute(
            "UPDATE procedures SET uses = uses + 1, last_used = ? WHERE name = ?",
            (datetime.now(timezone.utc).isoformat(), name))

    def forgotten(self, older_than_days: int = 30, fewer_than: int = 1) -> list[Procedure]:
        """The ones to drop: old enough to have had their chance, and nobody took it.

        The default is never used at all. Raise `fewer_than` to weed harder — a procedure used
        once in two months is barely memory either."""
        cutoff = datetime.now(timezone.utc).timestamp() - older_than_days * 86400
        return [p for p in self.all()
                if p.uses < fewer_than and p.added_at.timestamp() < cutoff]

    def bind(self, classes: dict[str, type]) -> None:
        """Hang the stored procedures on the classes, so host code calls them like any method."""
        for procedure in self.all():
            if procedure.attaches_to not in classes:
                continue
            namespace: dict = {}
            source = f"def {procedure.signature}:\n" + "\n".join(
                "    " + line for line in procedure.body.splitlines())
            exec(compile(source, f"<procedure {procedure.name}>", "exec"), _procedure_globals(), namespace)
            function = namespace[procedure.signature.split("(")[0]]
            function.__doc__ = procedure.because
            setattr(classes[procedure.attaches_to], procedure.signature.split("(")[0],
                    _counting(self, procedure.name, function))


def _counting(book: "Procedures", name: str, function):
    """Every call is evidence that the procedure earns its place."""
    def called(*args, **kwargs):
        book.used(name)
        return function(*args, **kwargs)

    called.__name__ = function.__name__
    called.__doc__ = function.__doc__
    return called


def _procedure_globals() -> dict:
    """What a procedure may reach: the same as host code, and nothing besides."""
    from terraweaver import ontology

    out = dict(sandbox.MODULES)
    out["__builtins__"] = sandbox.BUILTINS
    out["world"] = ontology.current_world()
    for name, cls in ontology.current_world().classes.items():
        out[name] = cls
    return out


def _row(row) -> Procedure | None:
    if row is None:
        return None
    name, attaches_to, signature, body, because, added_at, uses, last_used = row
    return Procedure(name, attaches_to, signature, body, because,
                     datetime.fromisoformat(added_at), uses,
                     datetime.fromisoformat(last_used) if last_used else None)
