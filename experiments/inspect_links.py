"""Run the link inspector over a world, with Jev as the reader.

    .venv/bin/python experiments/inspect_links.py experiments/results/batches/fixed100

Direction only: whether each end is the kind of thing that belongs at its end. Whether the fact
is true is not asked — this record deliberately holds claims that contradict common knowledge
and they are what it exists to keep.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/home/mike/Projects/ai-safity/experiments/62_jev_noul")

from terraweaver import growth, inspector, ontology as ont          # noqa: E402
from terraweaver.runtime import WorldRuntime                        # noqa: E402

FRAME = """One link out of a record of links. A link has two ends and they are not
interchangeable: the subject is the end it starts from, the object is the end it leads to.

    relation:    {kind} — {type_is}
    subject is:  {subject_is}
    object is:   {object_is}

    subject:  {s_name} (a {s_class}){s_said}
    object:   {o_name} (a {o_class}){o_said}
    {link_said}

Judge only whether each end holds the right KIND of thing for its role. Whether the claim is
TRUE is not asked and must not affect the answer: this record deliberately holds claims that
contradict common knowledge and they are meant to be kept. With subject "a city that is a
capital" and object "the country whose capital it is", the pair Rome / Japan is correct in kind
even though Rome is not Japan's capital."""

YES = "yes — a thing of that sort fills that role"
NO = "no — a thing of that sort does not fill that role"


def reader(client):
    def ask(a: dict):
        subj = a["subject_is"] or f"the end '{a['kind'].replace('_', ' ')}' starts from"
        obj = a["object_is"] or f"the end '{a['kind'].replace('_', ' ')}' leads to"
        state = FRAME.format(
            kind=a["kind"], type_is=a["type_is"] or "(nobody said)",
            subject_is=subj, object_is=obj,
            s_name=a["subject"]["name"], s_class=a["subject"]["class"],
            s_said=(" — " + "; ".join(a["subject"]["described"])) if a["subject"]["described"] else "",
            o_name=a["object"]["name"], o_class=a["object"]["class"],
            o_said=(" — " + "; ".join(a["object"]["described"])) if a["object"]["described"] else "",
            link_said=("said of the link: " + "; ".join(a["link_described"])) if a["link_described"] else "")
        qs = {k: {"type": "noul", "instructions": q, "criteria": {"true": YES, "false": NO}}
              for k, q in (("a_s", f"Is '{a['subject']['name']}' {subj}?"),
                           ("b_o", f"Is '{a['object']['name']}' {obj}?"),
                           ("b_s", f"Is '{a['object']['name']}' {subj}?"),
                           ("a_o", f"Is '{a['subject']['name']}' {obj}?"))}
        g = client.ask(state, qs)["answers"]
        as_written = g["a_s"]["noul"] * g["b_o"]["noul"]
        swapped = g["b_s"]["noul"] * g["a_o"]["noul"]
        said = (f"{a['subject']['name']} {a['kind'].replace('_', ' ')} {a['object']['name']}: "
                f"as written {as_written:.2f}, the other way round {swapped:.2f}")
        if max(as_written, swapped) < 0.30:
            return "impossible", said
        if swapped > as_written * 2:          # clear of it, not merely ahead
            return "reversed", said
        if as_written >= 0.5:
            return "right", said
        return "unsure", said
    return ask


def main() -> int:
    for line in open("/home/mike/Projects/ai-safity/.env"):
        if line.startswith("TYPESAFE_API_KEY"):
            os.environ["TYPESAFE_API_KEY"] = line.split("=", 1)[1].strip().strip('"')
    from jev_api import JevClient

    where = Path(sys.argv[1]).resolve()
    specs = growth.apply_growth(ont.base_specs(ROOT / "ontology" / "core"),
                                growth.load_grown(where / "grown"))
    world = WorldRuntime(str(where / "world.db"), fixture=None, specs=specs, selves=True).world
    waiting = inspector.unread(world, limit=1000)
    print(f"{where.name}: {len(waiting)} link(s) nobody has read")
    tally = inspector.look(world, reader(JevClient()), reader="jev-1.13.0", limit=1000)
    print("  " + ", ".join(f"{k} {v}" for k, v in tally.items() if v))
    print(f"  read again now: {len(inspector.unread(world, limit=1000))} (should be 0)")
    pairs = inspector.twins(world)
    if pairs:
        print("\ntypes that read like each other:")
        for a, b, score in pairs[:10]:
            print(f"  {a} ~ {b}   {score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
