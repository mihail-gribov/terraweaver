"""A base world for the tests, and the few words and attributes a test needs, said the way a host says them.

There is no fixture. A world opens as the base — Thing, Related, Person, AIAgent, Event, and the
world's own Task — and anything a test needs beyond that it declares through the world's own doors:
a word for a link with `define_relation`, an attribute with `attribute`. That is what a host does,
so a test built this way tests the world a host meets, and not a vocabulary somebody wrote by hand
and then forgot was there.

Kept small on purpose. A helper that grows a cast of characters is the thing this replaced.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver import open_world  # noqa: E402


def world(task: str | None = "k", *, kept: bool = False):
    """A fresh base world — on disk when `kept`, so a test can open it again — with a task open."""
    if kept:
        where = Path(tempfile.mkdtemp(prefix="tw-test-"))
        rt = open_world(str(where / "world.db"), home=where)
    else:
        rt = open_world()
    if task:
        rt.start_task(task, "record what the test says, the way a host would", "recording")
    return rt


def word(rt, name: str, description: str, cardinality: str, subject_is: str, object_is: str):
    """Declare a word for a link, every argument by name, as `world.define_relation` takes them."""
    return rt.world.extras["define_relation"](name, description, cardinality=cardinality,
                                              subject_is=subject_is, object_is=object_is)


def attribute(rt, class_name: str, name: str, description: str, type: str = "str"):
    """Grow an attribute on a class, as `world.attribute` does — `type="email"` gives it a value kind."""
    return rt.world.extras["attribute"](rt.world.classes[class_name], name, description, type=type)
