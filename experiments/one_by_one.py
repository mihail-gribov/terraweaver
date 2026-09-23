"""The facts as they come, one at a time, with the world read after each.

The benchmark records twenty-five to a turn and takes an hour before anything can be looked at,
and when something is wrong there is no telling which of the twenty-five did it. Here each fact
is said on its own, in the order the benchmark gives them, and the world is read straight after:
every line of the trace is one fact and one consequence.

Nothing is selected and nothing is reordered. Facts that contradict earlier ones arrive where
they arrive, which is the point — 143 of the 455 do.

    .venv/bin/python experiments/one_by_one.py --facts 40
"""
import argparse
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc              # noqa: E402
import host as hosting                      # noqa: E402

from experiments.base_run import PRIMER, RECORD, start_base_server  # noqa: E402
from experiments.fact_by_fact import VALUE, world_values  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--facts", type=int, default=40, help="how far down the list to go")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--port", type=int, default=7092)
    args = parser.parse_args()

    facts = fc.load("sh", "6k").facts[: args.facts]
    print(f"{len(facts)} фактов, по одному, в том порядке, в каком даны.\n", flush=True)

    work = Path(tempfile.mkdtemp(prefix="tw-one-"))
    db, log = work / "world.db", work / "host.jsonl"
    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    landed = lost = 0
    said_before: dict = {}
    try:
        server = start_base_server(db, args.port)
        agent = hosting.World(work, "one", args.port)
        hosting.ask(agent, PRIMER, agent.conversation(), None, log, args.model)

        for number, fact in enumerate(facts, 1):
            got = hosting.ask(agent, RECORD.format(when=date(2020, 1, 1).isoformat(),
                                                   facts=f"- {fact}"),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]

            frame, value = (VALUE.match(fact).groups() if VALUE.match(fact) else (fact, ""))
            frame, value = frame.strip(), value.strip()
            names, held = world_values(db)
            known = sorted(set(names.values()), key=len, reverse=True)
            subject = next((n for n in known if n.lower() in frame.lower()), None)
            holds = sorted(held["holds"].get(subject, ())) if subject else []
            ok = bool(subject) and any(value.lower() == v.lower() for v in holds)
            landed, lost = (landed + 1, lost) if ok else (landed, lost + 1)
            before = said_before.get(frame)
            said_before[frame] = value
            note = ""
            if before and before.lower() in {v.lower() for v in holds}:
                note = f"  ← прежнее «{before}» всё ещё держится"
            print(f"{'✓' if ok else '✗'} {number:>3}. {fact[:58]:<60}"
                  + (f"{', '.join(holds)[:40]}" if holds else
                     ("субъекта нет" if subject is None else "ничего")) + note, flush=True)
    finally:
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)

    print(f"\nлегло {landed}, не легло {lost} из {len(facts)}")
    print(f"{spent['turns']} ходов, ${spent['cost']:.2f}, "
          f"{(time.monotonic() - started) / 60:.1f} мин")
    print(f"мир: {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
