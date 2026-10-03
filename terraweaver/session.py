"""A session: the namespace plus a described registry of everything in it.

The namespace persists across tasks (Jupyter-kernel style), and every binding in it
carries a description — resolved entities, pre-loaded collections, and whatever the
agent's own code leaves behind. Together they are the structure of the current
situation: what has already been established and what the next task can build on.

Descriptions are derived by the harness rather than asked of the model, so the
registry stays accurate even when the model doesn't volunteer one.
"""
import time
from typing import Any

from terraweaver.ontology import Entity


class Session:
    def __init__(self, classes: dict[str, type], seed: dict[str, Any] | None = None, world=None):
        self.classes = classes
        # Everything the world holds except its own bookkeeping. A Task is the world's record of
        # the work done on it, written about the agent by the world; handed to the agent as one
        # more class it can make, it reads as somewhere to put things.
        self.namespace: dict[str, Any] = {
            name: cls for name, cls in classes.items()
            if not (getattr(cls, "_spec", {}) or {}).get("own")}
        self.variables: dict[str, dict] = {}
        # Names the harness puts in the namespace besides the classes (helpers, modules); they
        # aren't the agent's variables and aren't reported as such.
        self.preset: set[str] = set()
        self.last_used = time.time()
        # World variables currently injected; they're shared, not this session's own.
        self.world_vars: set[str] = set()
        # Entities this session has worked with: what "the questions left over from this task"
        # means when the task is done.
        self.touched: set[str] = set()
        # The task this session is working through, if one was started. The world cannot see a
        # conversation begin or end — a session key comes from the host's connection settings —
        # but it can see a task, because a task is opened out loud.
        self.task_id: int | None = None
        self.runs: int = 0
        # The sentence the world reads each new type's first link as, gathered over the task
        # and put to the host once, at the close.
        self.readings: dict[str, str] = {}
        # Which of them have already been put to the host, so the close asks once.
        self.read_back: set[str] = set()
        # Statements that write and never ran — failed, or never reached — keyed by their shape,
        # with the text the host wrote. A later run of the same statement settles one. The close
        # will not pass while any stand, once (`runtime._never_ran`).
        self.owed: dict[str, str] = {}
        self.owed_shown: set[str] = set()
        # What each owed statement names, and how much of it has been written about since: once
        # all of it has, the fact was said again in other words and is not owed any more.
        self.owed_about: dict[str, frozenset] = {}
        self.owed_seen: dict[str, set] = {}

        for name, value in (seed or {}).items():
            self.bind(name, value, "pre-loaded data")
        if world is not None:
            self.namespace["world"] = world
            # Every conversation has these two, so they're always to hand.
            # The two parties are in every namespace under the same names, always. They are not
            # variables the host set and can lose: reset_session puts them back, and nothing may
            # rebind them. `me` and `owner` are the older names for the same two.
            for name, value, what in (("agent", world.me, "you — the assistant keeping this world"),
                                      ("me", world.me, "you — the assistant"),
                                      ("user", world.owner, "the person this world belongs to"),
                                      ("owner", world.owner, "the person this world belongs to")):
                if value is not None:
                    self.bind(name, value, what)
                    self.preset.add(name)

    def bind(self, name: str, value: Any, kind: str) -> None:
        self.namespace[name] = value
        self.variables[name] = {"kind": kind, "description": self.describe(value), "at": time.time()}

    def sync(self) -> list[str]:
        """Pick up bindings the agent's code left behind. Returns the newly seen names."""
        ignored = set(self.classes) | {"report", "world", "run_skill", "NeedsResolution"} | self.preset | self.world_vars
        new_names = []
        for name, value in list(self.namespace.items()):
            if name.startswith("_") or name in ignored or callable(value) or type(value).__module__ == "builtins" and callable(value):
                continue
            described = self.describe(value)
            if name not in self.variables:
                self.variables[name] = {"kind": "created while solving", "description": described, "at": time.time()}
                new_names.append(name)
            else:
                self.variables[name]["description"] = described
        return new_names

    def describe(self, value: Any) -> str:
        if isinstance(value, Entity):
            return _describe_instance(value)
        if isinstance(value, list):
            if value and isinstance(value[0], Entity):
                return f"list[{type(value[0]).__name__}] ({len(value)} items)"
            return f"list ({len(value)} items)"
        if isinstance(value, dict):
            return f"dict ({len(value)} keys)"
        text = repr(value)
        return f"{type(value).__name__} = {text if len(text) <= 60 else text[:57] + '...'}"

    def describe_for_prompt(self) -> str:
        if not self.variables:
            return ""
        lines = ["\nIn your namespace right now (already established — build on these, don't redo them):"]
        for name, info in self.variables.items():
            lines.append(f"- {name}: {info['description']}  [{info['kind']}{_age(info.get('at'))}]")
        return "\n".join(lines) + "\n"


def _age(at: float | None) -> str:
    """How long ago a variable appeared — an old one may belong to an earlier task."""
    if at is None:
        return ""
    minutes = int((time.time() - at) // 60)
    return f", {minutes} min ago" if minutes >= 1 else ""


def _describe_instance(instance) -> str:
    parts = [type(instance).__name__]
    for attr in ("full_name", "name", "title"):
        value = getattr(instance, attr, None)
        if isinstance(value, str) and value:
            parts.append(f"«{value}»")
            break
    extras = []
    for attr in ("email", "organization", "status"):
        value = getattr(instance, attr, None)
        if value is None:
            continue
        label = None
        if isinstance(value, Entity):
            for name_attr in ("full_name", "name", "title"):
                candidate = getattr(value, name_attr, None)
                if isinstance(candidate, str):
                    label = candidate
                    break
        extras.append(f"{attr}={label if label is not None else value}")
    return " ".join(parts) + (f" ({', '.join(extras)})" if extras else "")
