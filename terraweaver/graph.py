"""Walking the graph: paths, neighbourhoods, what two people have in common.

The line this module sits on is the one that matters most in the whole design. The world does not
decide that whoever heads a department manages its members — that is a judgement, and judgements
belong to whoever is asking. But finding that Kevin belongs to a department whose head is Linda is
not a judgement at all: it is a walk over links that were actually written down, and doing it by
hand costs a host several runs and comes out differently each time.

So: the world computes, the agent concludes. Everything here returns paths and neighbours with
the relations they went through, never an interpretation of them.

    a.path_to(b)        how these two are connected, step by step
    a.near(hops=2)      everyone within a few steps, and how far
    a.shared_with(b)    what both are connected to — the people or places in common
    a.reaches(kind)     everything up or down one kind of link: the whole department tree

None of it invents a link. If nothing was written down, nothing comes back.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class Step:
    """One link on a path: what it was, and where it led."""

    relation: Any
    to: Any

    def __repr__(self):
        from terraweaver import relations

        role = self.relation.role_of(self.to) or relations.spec(type(self.relation))["kind"]
        return f"{role} {self.to.display_name()}"


@dataclass
class Path:
    """A chain of links between two entities, as it was actually recorded."""

    start: Any
    steps: list

    def __len__(self):
        return len(self.steps)

    @property
    def end(self):
        return self.steps[-1].to if self.steps else self.start

    def __repr__(self):
        walk = " → ".join(repr(step) for step in self.steps)
        return f"<{self.start.display_name()} → {walk}>" if self.steps else "<no path>"


def path_to(world, start, target, max_hops: int = 4, kind: str | None = None) -> Path | None:
    """The shortest chain of recorded links from one entity to another, or None.

    What it means is not the world's business — "her sister's husband works there" is a fact
    about the links; whether that makes him a contact worth asking is for whoever asks.
    """
    from terraweaver import relations

    if relations.same(start, target):
        return Path(start, [])
    seen = {start.id}
    frontier = [Path(start, [])]
    for _ in range(max_hops):
        nxt = []
        for path in frontier:
            for relation in relations.relations_of(world, path.end, kind):
                other = relation.other(path.end)
                if other is None or other.id in seen:
                    continue
                walked = Path(start, path.steps + [Step(relation, other)])
                if relations.same(other, target):
                    return walked
                seen.add(other.id)
                nxt.append(walked)
        frontier = nxt
        if not frontier:
            break
    return None


def near(world, start, hops: int = 2, kind: str | None = None) -> list:
    """Everyone within a few links, nearest first, each with the way there."""
    from terraweaver import relations

    seen = {start.id}
    found, frontier = [], [Path(start, [])]
    for _ in range(hops):
        nxt = []
        for path in frontier:
            for relation in relations.relations_of(world, path.end, kind):
                other = relation.other(path.end)
                if other is None or other.id in seen:
                    continue
                seen.add(other.id)
                walked = Path(start, path.steps + [Step(relation, other)])
                found.append(walked)
                nxt.append(walked)
        frontier = nxt
    return found


def shared_with(world, one, other, kind: str | None = None) -> list:
    """What both are connected to: the people, companies or places in common."""
    from terraweaver import relations

    mine = {r.other(one).id: r.other(one) for r in relations.relations_of(world, one, kind)
            if r.other(one) is not None}
    theirs = {r.other(other).id for r in relations.relations_of(world, other, kind)
              if r.other(other) is not None}
    return [entity for entity_id, entity in mine.items() if entity_id in theirs]


def reaches(world, start, kind: str, up: bool = True) -> list:
    """Everything along one kind of link, as far as it goes — a department tree, a family line.

    `up` follows the way the link points (a department to its company); `up=False` follows it
    back (a company to everything under it)."""
    from terraweaver import relations

    name, reverse = relations.resolve_kind(world.classes, kind)
    out, seen, frontier = [], {start.id}, [start]
    while frontier:
        node = frontier.pop()
        for relation in world.all(name, limit=None):
            if up != reverse:
                step = relation.object if relations.same(relation.subject, node) else None
            else:
                step = relation.subject if relations.same(relation.object, node) else None
            if step is None or step.id in seen:
                continue
            seen.add(step.id)
            out.append(step)
            frontier.append(step)
    return out
