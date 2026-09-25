"""The run: a base world, the host's nine facts said in words, and the reading that types them.

    .venv/bin/python experiments/01_relation_formalisation/run.py                 all nine
    .venv/bin/python experiments/01_relation_formalisation/run.py --facts 2       the first two
    .venv/bin/python experiments/01_relation_formalisation/run.py --say-only      neither is called

The world is fresh every time and thrown away unless `--keep` is given: a run against a world that
already holds the words is measuring the look and not the making, and the two have to be told
apart. What is written down is the whole trace — what was asked, what came back, what ran — because
the thing being looked at is the exchange and not the count.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import facts as F  # noqa: E402
from terraweaver import formalise as reading  # noqa: E402  — the world's own, since it moved there
import world as W  # noqa: E402

from terraweaver import outside  # noqa: E402
from terraweaver.runtime import format_result  # noqa: E402

RESULTS = HERE / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts", type=int, default=len(F.FACTS),
                        help="how many of the facts to say, in order")
    parser.add_argument("--keep", type=Path, default=None,
                        help="where to leave the world, instead of a temporary directory")
    parser.add_argument("--say-only", action="store_true",
                        help="say the facts and stop, without reading them — no model is called")
    args = parser.parse_args()

    where = args.keep or Path(tempfile.mkdtemp(prefix="tw-exp01-"))
    runtime = W.open_base(where)
    engineer, picker = (None, None) if args.say_only else W.parties(runtime.world)
    if not args.say_only and engineer is None:
        print("NEBIUS_API_KEY is not set, so there is no engineer and nothing to read with.")
        return 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    said = {"world": str(where), "facts": args.facts, "started": stamp,
            "engineer": outside.NEMOTRON if engineer is not None else None,
            "picker": type(picker).__name__ if picker is not None else None,
            "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                     capture_output=True, text=True).stdout.strip()}
    print(json.dumps(said, indent=2), flush=True)

    # The task the facts are recorded under. Said because the world has no other way to see
    # where a piece of work begins: everything that hangs on the boundary — which names are still
    # the host's, what was left unanswered — hangs on this call, and without it the world opens a
    # task with no name and says so on every run.
    print(runtime.start_task("the host", "record the facts said in words, for the reading to "
                             "type afterwards", "recording"), flush=True)

    print("\n=== the host says the facts\n", flush=True)
    for words, put in F.FACTS[:args.facts]:
        got = runtime.run(F.said(words, put), "the host")
        print(f"  {words}")
        for line in format_result(got).splitlines():
            print(f"      {line}")
        print(flush=True)

    if args.say_only:
        _census(runtime.world)
        return 0

    print("=== the world reads them\n", flush=True)
    started = time.monotonic()
    tally = reading.formalise(runtime, engineer, picker)
    took = time.monotonic() - started
    for one in tally["read"]:
        print(f"  {one['words']}")
        looked = one.get("look") or {}
        if looked.get("asked"):
            print(f"      looked:   {looked.get('said')}  ({looked.get('sure')})")
        else:
            print(f"      looked:   — {looked.get('why', '')}")
        answers = one.get("answered") or []
        for go, code in enumerate(one["wrote"]):
            for line in code.splitlines():
                print(f"      | {line}")
            # What the record said back, shown when it did not simply work: a go that was followed
            # by another go, or a last go that got nowhere. The reply is the diagnosis, and a run
            # whose output held only the code left every refusal to be guessed at.
            # What the picker made of each claim in these lines, before the record was touched.
            checked = (one.get("checked") or [])
            for claim in (checked[go].get("claims") if go < len(checked) else None) or []:
                mark = "✓" if claim["verdict"] == "says_so" else "✗"
                what = claim["claim"].get("said") or claim["claim"].get("word")
                print(f"      {mark} {claim['claim']['what']}: {what}  "
                      f"{claim['verdict']} ({claim['sure']})")
            said = answers[go] if go < len(answers) else ""
            if said and (go + 1 < len(one["wrote"]) or one["went"] != "done"):
                for line in said.splitlines()[:8]:
                    print(f"      > {line}")
        made = ", ".join(one["typed"]) or "nothing"
        print(f"      {one['went']}: {made}")
        if one.get("defined"):
            print(f"      defined:  {', '.join(one['defined'])}")
        print(flush=True)

    print(f"typed {tally['typed']} of {len(tally['read'])} — "
          f"{tally['joined']} under a word already here, {tally['defined']} under a new one, "
          f"{tally['left']} left bare.   {took / 60:.1f} min\n", flush=True)
    _census(runtime.world)

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{stamp}.json"
    out.write_text(json.dumps({"config": said, "took_seconds": round(took, 1),
                               "tally": {k: v for k, v in tally.items() if k != "read"},
                               "read": tally["read"], "world": _as_data(runtime.world)}, indent=2))
    print(f"written: {out}")
    return 0


def _census(world) -> None:
    """The words this world ended up with, and every link under each — periods and all.

    Read out rather than counted: a count said the last run was a success and reading it link by
    link said one in nine had been recorded as something else. A period shown is how a handover is
    told from a second holder standing beside the first.
    """
    print("--- the words this world holds now")
    known = reading.words_for(world)
    if not known:
        print("    (none)")
    for name, cls, rel in known:
        many = []
        if rel.get("functional"):
            many.append("one object" + (" at a time" if rel["functional"] == "at_any_time" else " ever"))
        if rel.get("inverse_functional"):
            many.append("one subject" + (" at a time" if rel["inverse_functional"] == "at_any_time" else " ever"))
        roles = (rel.get("roles") or [{}])[0]
        print(f"    {rel['kind']:18} {roles.get('name') or '?'} ↔ {roles.get('inverse') or '?'}"
              f"   {', '.join(many) or 'many either way'}"
              f"   {'/'.join(rel.get('from') or ['any'])} → {'/'.join(rel.get('to') or ['any'])}")
        for link in world.all(name, limit=None, history=True):
            if getattr(link, "subject", None) is None:
                continue
            until = getattr(link, "valid_until", None)
            print(f"        {link.display_name()[:88]}"
                  + (f"   (ended {until})" if until is not None else ""))

    print("\n--- links still bare")
    from terraweaver import sentences

    bare = sentences.unread(world, 100)
    for link in bare:
        print(f"    {reading.words_of(link) or link.display_name()}")
    if not bare:
        print("    (none)")
    print(flush=True)


def _as_data(world) -> dict:
    """The end state, for the file: the words, their properties, and the links under them."""
    out = {"words": {}, "bare": []}
    for name, cls, rel in reading.words_for(world):
        roles = (rel.get("roles") or [{}])[0]
        out["words"][rel["kind"]] = {
            "class": name, "description": cls._spec.get("description", ""),
            "subject_is": roles.get("name"), "object_is": roles.get("inverse"),
            "functional": rel.get("functional"), "inverse_functional": rel.get("inverse_functional"),
            "nature": rel.get("nature"), "from": rel.get("from"), "to": rel.get("to"),
            "transitive": rel.get("transitive"),
            "links": [{"reads": link.display_name(),
                       "from": str(getattr(link, "valid_from", "") or ""),
                       "until": str(getattr(link, "valid_until", "") or "")}
                      for link in world.all(name, limit=None, history=True)
                      if getattr(link, "subject", None) is not None]}
    from terraweaver import sentences

    out["bare"] = [reading.words_of(link) for link in sentences.unread(world, 100)]
    return out


if __name__ == "__main__":
    sys.exit(main())
