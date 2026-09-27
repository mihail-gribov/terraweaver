"""How a world's classes come together: the preset it started with, and what it has made since.

A class a world started with and a class it made last night are the same kind of thing. The
preset in `ontology/core` is the content a world opens with — any content could be — and it is
read, built and extended exactly as a class the world defined for itself is. What distinguishes
them is recorded, not enforced: a class carries `source`, "preset" for one it started with, and
that is a fact about it like any other, never a rule about what may be done with it.

    ontology/core/    a preset: what a new world starts with. Read, never written to — a world
                      that changes one of these writes its own version beside its database.
    <world>/grown/    the world's own: classes it defined, its own version of any class it
                      changed, and additions to any class it has.

The one rule that holds for every class alike: growth adds, it does not rewrite. An addition may
not redefine an attribute or a method the class already declares — so what a host learned to rely
on keeps working, whoever wrote the class it is on.

Why a separate place at all, rather than editing the preset in place: a world that improves itself
is a world that will sometimes be wrong. What it grew, kept apart, can be read on its own, diffed and
dropped — and because the facts layer holds what was said rather than what a class shaped it into
(`facts.py`), dropping a grown attribute loses no data. The statements stay; only the image stops
showing them.

Every addition carries why it exists — what evidence, from when. A proposal nobody can explain is a
proposal nobody can review.
"""
import json
from pathlib import Path
from typing import Any

# What a grown spec may say. Anything else is refused rather than silently ignored: a world that
# quietly drops half a proposal is worse than one that says no.
ALLOWED = {"name", "extends", "description", "because", "added_at", "attributes", "methods", "relations"}


class GrowthRefused(Exception):
    """A proposed change would overwrite what a class already declares, or isn't well formed."""


def load_grown(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json"))]


def apply_growth(preset: dict[str, dict], grown: list[dict]) -> dict[str, dict]:
    """The classes a world started with plus what it has made since, as one set to build from.

    Two passes, and the order is the whole of the fairness. First every class the world holds a
    version of: one it defined, or its own version of one it started with, which replaces the
    starting one — it began as a copy and was changed. Then every addition, to any class the world
    now has. In one pass, an addition could only land on a class read before it: an extension of a
    class the world made itself was refused as "not a core class" whenever its file sorted first,
    which made the preset the only thing that could be built on.

    An extended class remembers what came from where (`grown_from`) so a description can show the
    difference and a rollback can take exactly the additions away.
    """
    specs = {}
    for name, spec in preset.items():                     # never mutate what was passed in
        specs[name] = json.loads(json.dumps(spec))
        specs[name].setdefault("source", "preset")
    for whole in grown:
        if whole.get("extends") is None and whole.get("name"):
            # What `define` and `define_relation` write, and what a world writes when it changes a
            # class it started with. Both are the class as this world has it now.
            specs[whole["name"]] = json.loads(json.dumps(whole))
    for addition in grown:
        base = addition.get("extends")
        if base is None:
            continue
        if base not in specs:
            raise GrowthRefused(f"{addition.get('name', '<unnamed>')} extends {base!r}, which is not a "
                                f"class in this world")
        unknown = set(addition) - ALLOWED
        if unknown:
            raise GrowthRefused(f"{addition['name']}: an addition can't say {', '.join(sorted(unknown))}")
        if not str(addition.get("because", "")).strip():
            raise GrowthRefused(f"{addition['name']}: say why it was added — a change nobody can explain "
                                f"is one nobody can review")
        spec = specs[base]
        declared = {a["name"] for a in spec["attributes"]}
        added = []
        for attr in addition.get("attributes", []):
            if attr["name"] in declared:
                raise GrowthRefused(
                    f"{base}.{attr['name']} is already declared and can't be redefined; growth adds, "
                    f"it doesn't rewrite"
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
