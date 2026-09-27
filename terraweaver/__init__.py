"""TerraWeaver: a personal world a model can work with.

Opening one is meant to be a single line, because most of the time — a test, a scratch world to
try something in, a second world to compare against — the ceremony is the whole cost:

    from terraweaver import open_world

    w = open_world()                        # empty, in memory, gone when the process ends
    w = open_world("mike")                  # a world of one's own, kept in var/worlds/mike/
    w = open_world("var/mine.db")           # or wherever you say, if it looks like a path

Every world starts from the base — `Thing`, `Related`, `Person`, `AIAgent`, `Event`, and the
world's own `Task` — plus whatever it has grown for itself, kept in `grown/` beside its database,
with the calls that define more (`define`, `define_relation`) in reach. There is no fixture: what
a world holds, it was told. This is the one recipe; the server, the tests and the experiments open
a world through it, so there is one answer to "what is a world when it opens".

A bare name is a world of its own: `var/worlds/<name>/`, with its `world.db` and the files that
describe the two parties beside it. Several of them can exist side by side — one to try
something in, one to keep — and the name is the whole ceremony.

What comes back is the runtime: `w.run(code, "session")` is what a host does, `w.world` is the
world itself for code that works on it directly, `w.classes` are the classes it built.

Only one world is current at a time — classes reach their world through a module-level binding,
so `Person.find(...)` knows where to look without every class carrying a store. Use the handle as
a context manager to work with a second one and put the first one back afterwards:

    with open_world() as other:
        ...                                  # `other` is the current world in here
                                             # and the previous one is current again out here
"""
from pathlib import Path


WORLDS = Path(__file__).resolve().parent.parent / "var" / "worlds"


def where(name: str) -> Path:
    """The folder a world of this name lives in."""
    return WORLDS / name


def open_world(path: str = ":memory:", *, home: Path | None = None, grown: Path | None = None,
               one_door: bool = False):
    """Open a world and make it the current one. See the module docstring.

    `grown` is where the classes this world makes for itself are kept — beside its database by
    default, and nowhere for a world in memory, which forgets them with everything else.
    """
    from terraweaver import authoring, growth, ontology
    from terraweaver.runtime import ONTOLOGY_DIR, WorldRuntime

    if path != ":memory:":
        if "/" not in path and not path.endswith(".db"):  # a name, not a path
            folder = where(path)
            folder.mkdir(parents=True, exist_ok=True)
            path, home = str(folder / "world.db"), home or folder
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        grown = Path(grown) if grown is not None else Path(path).parent / "grown"
    specs = growth.apply_growth(ontology.base_specs(ONTOLOGY_DIR),
                                growth.load_grown(grown) if grown is not None else [])
    runtime = WorldRuntime(path, specs=specs, selves=True, home=home)
    authoring.install(runtime.world, grown, one_door=one_door)
    return runtime


def worlds() -> list[str]:
    """Every world kept by name."""
    return sorted(p.name for p in WORLDS.glob("*") if (p / "world.db").exists()) if WORLDS.exists() else []


__all__ = ["open_world", "worlds", "where"]
