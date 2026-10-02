"""AGENT.md: the two upper levels of change, written by a person.

PARKED, and not wired into anything yet — a sketch of the shape, kept so the idea
isn't re-derived later. The world reads USER.md and soul.md today (selves.py); this
file is the next thing to connect, after the write path goes through statements.

The world can add to its own classes and write its own procedures (`growth.py`,
`procedures.py`). A person can do the same, in a file next to the world, and it goes through
exactly the same doors — the same additive-only rule for classes, the same sandbox for code,
the same requirement to say why. Two authors, one mechanism.

    ```class Person
    {"because": "every second person here has a dietary note in a remark",
     "attributes": [{"name": "dietary_notes", "type": "str",
                     "description": "What they don't eat, and why it matters."}]}
    ```

    ```procedure Person.namesakes(self)
    because: asked three times this week — who else here goes by the same first name
    first = self.name.split()[0]
    return [p for p in Person.find(name=first).matches if p != self]
    ```

What the file declares is re-read when the file changes, and what it declared before is taken
away first — so deleting a block removes what it added, rather than leaving it behind forever.

This is not where the person is described (`USER.md`) or the assistant is (`soul.md`). This is
how the world is shaped for the work at hand: what the classes hold, and what shortcuts exist.
"""
import json
import re
from pathlib import Path

from terraweaver import growth

BLOCK = re.compile(r"^```(class|procedure)\s+([^\n`]+)\n(.*?)^```", re.M | re.S)


def parse(text: str) -> tuple[list[dict], list[dict]]:
    """(class additions, procedures) declared in an AGENT.md."""
    additions, procedures = [], []
    for kind, subject, body in BLOCK.findall(text):
        subject = subject.strip()
        if kind == "class":
            spec = json.loads(body)
            spec.setdefault("name", f"{subject}FromFile")
            spec["extends"] = subject
            additions.append(spec)
        else:
            class_name, _, signature = subject.partition(".")
            because, code = _split_reason(body)
            procedures.append({"attaches_to": class_name.strip(), "signature": signature.strip(),
                               "name": signature.split("(")[0].strip(), "because": because,
                               "body": code})
    return additions, procedures


def _split_reason(body: str) -> tuple[str, str]:
    lines = body.splitlines()
    if lines and lines[0].strip().lower().startswith("because:"):
        return lines[0].split(":", 1)[1].strip(), "\n".join(lines[1:]).strip("\n")
    return "", body.strip("\n")


def read(home: Path) -> tuple[list[dict], list[dict]]:
    path = Path(home) / "AGENT.md" if home else None
    if path is None or not path.exists():
        return [], []
    return parse(path.read_text())


def apply_procedures(world, procedures: list[dict], source: str = "AGENT.md") -> list[str]:
    """Define what the file declares, and drop what it used to declare and no longer does."""
    wanted = {p["name"] for p in procedures}
    for existing in world.procedures.all():
        if existing.because.startswith(f"[{source}]") and existing.name not in wanted:
            world.procedures.drop(existing.name)
    defined = []
    for procedure in procedures:
        if not procedure["because"]:
            raise ValueError(f"{source}: procedure {procedure['name']} needs a `because:` line — "
                             f"say what kept being written by hand")
        world.procedures.define(
            procedure["name"], procedure["signature"], procedure["body"],
            because=f"[{source}] {procedure['because']}", attaches_to=procedure["attaches_to"])
        defined.append(procedure["name"])
    return defined


def applied_to(specs: dict[str, dict], additions: list[dict]) -> dict[str, dict]:
    """Class additions from the file, merged the same way the world's own growth is."""
    return growth.apply_growth(specs, additions) if additions else specs
