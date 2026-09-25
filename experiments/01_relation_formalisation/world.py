"""A base world, opened in this process, with the two parties it reads by.

The starting world is the base and nothing else: `Thing`, `Related`, `Person`, `AIAgent`,
`Event`, plus `Task`, which is the world's own record of work and not part of anybody's picture.
Not a fixture — `job_search` holds fifteen classes and a `Kin` with fourteen labels, and a run
against it measures a vocabulary somebody wrote by hand rather than one a world arrived at. The
recipe is `terraweaver/server.py --base`, taken as it is, so what is opened here is what a served
base world is.

Everything under test is the world's own code. This module only opens the world and hands over
the two of them: the **engineer**, which answers in words (Nemotron), and the **picker**, which
answers with named options (Jev, and `outside.AsChoices` standing in when there is no key for
one). Named for the role, not for the model.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from terraweaver import authoring, growth, ontology, outside  # noqa: E402
from terraweaver.runtime import WorldRuntime  # noqa: E402

CORE = ROOT / "ontology" / "core"


def keys() -> dict:
    """The keys this machine has, from the places they are kept here.

    Read once and put into the environment, because the connectors take them from there. A key
    that is missing is not an error: the experiment says which of them it is running without, and
    a run with no engineer measures the door that is still switched on, which is worth knowing
    and worth not confusing with the other.
    """
    for env in (ROOT / ".env", Path(os.path.expanduser("~/Projects/ai-safity/.env"))):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            for name in ("NEBIUS_API_KEY", "TYPESAFE_API_KEY"):
                if line.startswith(name) and not os.environ.get(name):
                    os.environ[name] = line.split("=", 1)[1].strip().strip('"')
    return {name: bool(os.environ.get(name))
            for name in ("NEBIUS_API_KEY", "TYPESAFE_API_KEY")}


def open_base(where: Path) -> WorldRuntime:
    """A base world whose database is in `where`, with the definition calls installed.

    `one_door` is left off. It hides `define_relation` from the host's surface, and it hides it
    from `world.extras`, which is where the world's own reading reaches for it — so a world
    started that way cannot define the type it just read. The host here is a script and has no
    habit to measure, which is what that flag exists for.
    """
    where.mkdir(parents=True, exist_ok=True)
    grown = where / "grown"
    specs = growth.apply_growth(ontology.base_specs(CORE), growth.load_grown(grown))
    runtime = WorldRuntime(str(where / "world.db"), fixture=None, specs=specs, selves=True,
                           home=where)
    authoring.install(runtime.world, grown)
    return runtime


def parties(world) -> tuple:
    """The engineer and the picker, put on the world the way a served world gets them.

    The picker is attached as `world.jev`, which is the name the world's own code reads
    (`portraits.formalise`). Nothing in the working code puts one there — so the entity door's
    cheap closed walk has been running on the engineer all along, through `AsChoices`. Here it is
    attached on purpose, so the two kinds of question go to the two kinds of model.
    """
    have = keys()
    # Room to think and room to answer. The question here is long and the answer is code; at the
    # old default of 3000 the engineer spent the lot thinking and returned nothing twice in one run.
    engineer = outside.Nemotron(ttl=180, thinking_room=12000) if have["NEBIUS_API_KEY"] else None
    if engineer is not None:
        world.engineer = engineer
    if have["TYPESAFE_API_KEY"]:
        picker = outside.Jev(ttl=60)
    elif engineer is not None:
        picker = outside.AsChoices(engineer)
    else:
        picker = None
    if picker is not None:
        world.jev = picker
    return engineer, picker
