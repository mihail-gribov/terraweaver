"""TerraWeaver: a personal world a model can work with.

Opening one is meant to be a single line, because most of the time — a test, a scratch world to
try something in, a second world to compare against — the ceremony is the whole cost:

    from terraweaver import open_world

    w = open_world()                        # empty, in memory, gone when the process ends
    w = open_world(fixture="job_search")    # with something in it to work on
    w = open_world("var/mine.db")           # on disk, kept
    w = open_world("var/mine.db", rebuild=True)   # from the fixture again, from scratch

What comes back is the runtime: `w.run(code, "session")` is what a host does, `w.world` is the
world itself for code that works on it directly, `w.classes` are the classes it built.

Only one world is current at a time — classes reach their world through a module-level binding,
so `Person.find(...)` knows where to look without every class carrying a store. Use the handle as
a context manager to work with a second one and put the first one back afterwards:

    with open_world(fixture="job_search") as other:
        ...                                  # `other` is the current world in here
                                             # and the previous one is current again out here
"""
from pathlib import Path


def open_world(path: str = ":memory:", *, fixture: str | None = None, rebuild: bool = False,
               ontology_dir: Path | None = None):
    """Open a world and make it the current one. See the module docstring."""
    from terraweaver.runtime import WorldRuntime

    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    return WorldRuntime(path, fixture=fixture, rebuild=rebuild, ontology_dir=ontology_dir)


__all__ = ["open_world"]
