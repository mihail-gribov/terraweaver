"""What the world added to itself, kept apart from what we gave it.

Two layers of classes, and the line between them is not negotiable:

    ontology/core/    ours. Fixed, versioned by us, and the world may not touch a line of it.
    ontology/grown/   the world's. Each file extends one core class and adds to it.

A grown class inherits its core class and may only *add*: another attribute, another method,
another label a relation goes by. It may not redefine what the core already declares, narrow it,
or take it away — so anything a host learned to rely on keeps working, and reading the core file
still tells you what the class is.

Why a separate layer at all, rather than editing the class in place: a world that improves itself
is a world that will sometimes be wrong. Growth kept apart is growth that can be read on its own,
diffed, and dropped — and because the facts layer holds what was said rather than what a class
shaped it into (`facts.py`), dropping a grown attribute loses no data. The statements stay; only
the image stops showing them.

Every grown file carries why it exists — what evidence, from when. A proposal nobody can explain
is a proposal nobody can review.
"""
import json
from pathlib import Path
from typing import Any

# What a grown spec may say. Anything else is refused rather than silently ignored: a world that
# quietly drops half a proposal is worse than one that says no.
ALLOWED = {"name", "extends", "description", "because", "added_at", "attributes", "methods", "relations"}


class GrowthRefused(Exception):
    """A proposed change would overwrite what the core declares, or isn't well formed."""


def load_grown(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))]


def apply_growth(core: dict[str, dict], grown: list[dict]) -> dict[str, dict]:
    """Core specs plus what the world added, as one set of specs to build classes from.

    The returned spec for an extended class is the core one with additions merged in, and it
    remembers what came from where (`grown_from`, `grown_attributes`) so a description can show
    the difference and a rollback can take exactly the additions away.
    """
    specs = {name: json.loads(json.dumps(spec)) for name, spec in core.items()}  # never mutate the core
    for addition in grown:
        base = addition.get("extends")
        if base not in specs:
            raise GrowthRefused(f"{addition.get('name', '<unnamed>')} extends {base!r}, which isn't a core class")
        unknown = set(addition) - ALLOWED
        if unknown:
            raise GrowthRefused(f"{addition['name']}: a grown class can't say {', '.join(sorted(unknown))}")
        if not str(addition.get("because", "")).strip():
            raise GrowthRefused(f"{addition['name']}: say why it was added — a change nobody can explain "
                                f"is one nobody can review")
        spec = specs[base]
        declared = {a["name"] for a in spec["attributes"]}
        added = []
        for attr in addition.get("attributes", []):
            if attr["name"] in declared:
                raise GrowthRefused(
                    f"{base}.{attr['name']} is already declared in the core class and can't be redefined; "
                    f"growth adds, it doesn't rewrite"
                )
            spec["attributes"].append(attr)
            added.append(attr["name"])
        methods = {m["signature"].split("(")[0] for m in spec.get("methods", [])}
        for method in addition.get("methods", []):
            if method["signature"].split("(")[0] in methods:
                raise GrowthRefused(f"{base} already has {method['signature']}; growth adds, it doesn't rewrite")
            spec.setdefault("methods", []).append(method)
        for kind, note in (addition.get("relations") or {}).items():
            spec.setdefault("relations", {}).setdefault(kind, note)
        spec.setdefault("grown_from", []).append(
            {"name": addition["name"], "because": addition["because"],
             "added_at": addition.get("added_at"), "attributes": added})
    return specs


def describe_growth(specs: dict[str, dict]) -> str:
    """What this world has added to itself, for a person deciding whether to keep it."""
    lines = []
    for name, spec in specs.items():
        for entry in spec.get("grown_from", []):
            added = f" ({', '.join(entry['attributes'])})" if entry["attributes"] else ""
            when = f" on {entry['added_at']}" if entry.get("added_at") else ""
            lines.append(f"  {name}{added}{when} — {entry['because']}")
    return "The world added to itself:\n" + "\n".join(lines) if lines else ""
