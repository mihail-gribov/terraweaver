"""Ask a world that a recording run already built, instead of building one to ask.

`run_fc.py` records the facts and then asks about them, in one sitting, twenty-five facts to a
turn. That measures recording and answering together and pays for the recording every time.
This takes a world some run already left behind — `experiments/full_run.py --into <dir>`, or a
frozen one under `worlds/` — and only asks.

    .venv/bin/python benchmarks/ask_world.py --world experiments/results/batches/dated455 \
        --questions 20 --port 7400

The world is copied first, so a run of questions cannot change the world it is asking about:
answering is not supposed to write, but the world writes its own — questions it raises, what it
worked out, how often a thing was looked at — and the next run should ask the same world this
one did.

Grading is the benchmark's own: a normalised substring match against a list of gold strings, no
model in it. Every system in the published table is graded that way.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

import factconsolidation as fc                      # noqa: E402
import host as hosting                              # noqa: E402
from experiments.base_run import ASK, start_base_server  # noqa: E402

RESULTS = ROOT / "benchmarks" / "results"

PRIMER = """\
This world was filled in by somebody else, and you are being asked to read it. You did not \
define its classes and you do not know its vocabulary — so find out before you answer.

    world.classes_here()              — every class and link type it has, most used first
    world.anything_like("Paris")      — is there anything here called that, of any kind?
    world.like("capital city")        — what reads like this, by meaning
    thing.related("capital_of")       — what stands in that relation to this one
    thing.relations()                 — every link this one is in, with its type and period
    world.where(Cls, attr=value)      — the ones that match

The type a fact was recorded under is the word the question is about, and there may be several \
words for one idea — the recorder defined its own. So look at what the types are called before \
deciding none of them fits, and if the obvious word is not there, try the thing itself and read \
what it is in.

One thing more than anything else: **a fact recorded twice holds the later telling**. Somebody \
who worked at one company and then another has both in the record, one of them ended. \
`related(kind)` gives what holds now; `related(kind, any_time=True)` gives all of it. When the \
question asks what is so, the answer is what holds now.

Open a task before you read and close it after:

    start_task("find out where X works now", "answering")
    ... your runs ...
    finish_task()

Don't write facts — a question is not evidence."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--world", type=Path, required=True,
                        help="a directory holding world.db and grown/")
    parser.add_argument("--hops", default="sh", choices=["sh", "mh"])
    parser.add_argument("--context", default="6k", choices=["6k", "32k", "64k", "262k"])
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--from", dest="start", type=int, default=1)
    parser.add_argument("--port", type=int, default=7400)
    args = parser.parse_args()

    source = args.world.resolve()
    if not (source / "world.db").exists():
        print(f"no world.db in {source}", file=sys.stderr)
        return 2

    variant = fc.load(args.hops, args.context)
    questions = variant.questions[args.start - 1:args.start - 1 + args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-{variant.name}-asked-{source.name}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)

    config = {"benchmark": variant.name, "hops": variant.hops, "world": str(source),
              "questions": len(questions), "asked_from": args.start, "mode": "world (prebuilt)",
              "host_model": args.model, "judge": "string match, no model",
              "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True).stdout.strip(),
              "started": stamp}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config, indent=2), flush=True)

    # A copy, so the questions ask the same world the next run will.
    work = Path(tempfile.mkdtemp(prefix="tw-ask-"))
    shutil.copy(source / "world.db", work / "world.db")
    (work / "grown").mkdir(exist_ok=True)
    for spec in sorted((source / "grown").glob("*.json")):
        shutil.copy(spec, work / "grown" / spec.name)

    log = out_dir / "host.jsonl"
    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    results: list[dict] = []
    try:
        server = start_base_server(work / "world.db", args.port)
        # Outside this repository: Claude Code walks up from its working folder, finds the
        # project and reads our notes about this very measurement.
        elsewhere = Path(tempfile.mkdtemp(prefix="tw-host-"))
        agent = hosting.World(elsewhere, "ask", args.port)

        asked_on = datetime.now().date().isoformat()
        for number, question in enumerate(questions, args.start):
            got = hosting.ask(agent, PRIMER + "\n\n---\n\n"
                              + ASK.format(when=asked_on, question=question.text),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            right = fc.correct(got["text"], question.gold)
            results.append({"id": question.id, "question": question.text, "gold": question.gold,
                            "answer": got["text"][:300], "correct": right,
                            "turns": got["turns"], "cost": round(got["cost"], 3)})
            (out_dir / "answers.jsonl").open("a").write(json.dumps(results[-1]) + "\n")
            print(f"{'ok ' if right else '   '} {number:>3} {question.gold} "
                  f"<- {(got['text'] or '')[:80].replace(chr(10), ' ')}", flush=True)
    finally:
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)
            shutil.rmtree(elsewhere, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)

    summary = {"accuracy": round(sum(r["correct"] for r in results) / max(1, len(results)), 3),
               "questions": len(results), "cost_usd": round(spent["cost"], 2),
               "turns": spent["turns"], "minutes": round((time.monotonic() - started) / 60, 1)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2))
    print(f"\n{out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
