"""Ask an existing world the benchmark's questions again, without writing it a second time.

    .venv/bin/python benchmarks/reask.py --db /tmp/tw-blank-x/world.db \
        --specs /tmp/tw-blank-x/grown --questions 20

Recording 455 facts costs most of an hour; the questions cost a minute. So when what changed is
the *structure* — a restructuring pass, a new relation type, a repair — the honest measurement is
to take the world as it stands and ask it the same twenty questions. Before and after, one
variable, no re-ingestion in between to muddy it.
"""
import argparse
import json
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc
import host as hosting

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"

# One wording for the question, the one the full run asks with — a re-ask that words it
# differently measures the wording.
from run_fc import ASK  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True)
    parser.add_argument("--specs", default=None, help="the world's own class specs, if it built them")
    parser.add_argument("--hops", default="sh")
    parser.add_argument("--context", default="6k")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--port", type=int, default=7070)
    parser.add_argument("--label", default="reask")
    parser.add_argument("--own", default=None,
                        help="questions of our own instead of the benchmark's, as written by "
                             "experiments/own_questions.py: [{id, question, gold}]")
    parser.add_argument("--only", default=None,
                        help="ask just these questions, by number in the slice (2,7,19) — the "
                             "aimed re-ask of the ones that went wrong, at cents each")
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    if args.own:
        questions = [fc.Question(one["id"], one["question"], list(one["gold"]))
                     for one in json.loads(Path(args.own).read_text())]
    elif args.only:
        wanted = {int(n) for n in args.only.replace(" ", "").split(",") if n}
        questions = [q for n, q in enumerate(variant.questions, 1) if n in wanted]
    else:
        questions = variant.questions[:args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-{args.label}-{variant.name}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="tw-reask-"))
    log = out_dir / "host.jsonl"
    # The world as every world opens: the base, then what it grew, which sits beside its database.
    # `--specs` is the other thing — a world whose classes are *all* grown — and passing it for a
    # world with base classes killed the server with `KeyError: 'AIAgent'`. The server died, the
    # wait below gave up quietly, and a hundred questions were put to a host with no tools at all:
    # every answer "I don't have access to terraweaver tools", recorded as 1% accuracy. Measured
    # 2026-09-28, and the reason both the open and the wait are no longer silent.
    server = hosting.start_server(Path(args.db), args.port,
                                  specs=Path(args.specs) if args.specs else None)

    agent = hosting.World(work, args.label, args.port)
    results, spent = [], {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    try:
        for number, question in enumerate(questions, 1):
            hosting.answering(args.port)
            # The world's own day (see run_fc.py): a fictional one before every correction was
            # told is a question about what held before them.
            got = hosting.ask(agent, ASK.format(when=datetime.now().date().isoformat(),
                                                question=question.text),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            trouble = hosting.went_wrong(got)
            fumbled = hosting.hosts_own(got)
            right = False if trouble else fc.correct(got["text"], question.gold)
            results.append({"id": question.id, "question": question.text, "gold": question.gold,
                            "answer": got["text"][:300], "correct": right,
                            **({"trouble": trouble} if trouble else {}),
                            **({"the host's own": fumbled[:3]} if fumbled else {})})
            if trouble:
                (out_dir / "trouble.jsonl").open("a").write(
                    json.dumps({"question": question.id, **trouble}) + "\n")
            print(f"{'ok ' if right else '   '} {number:>3}/{len(questions)} {question.gold} "
                  f"<- {got['text'][:70].replace(chr(10), ' ')}", flush=True)
    finally:
        hosting.stop(server)
        hosting.forget_folder_memory(agent.cwd)

    # Over the questions that reached the world. The ones that did not are reported beside the
    # number and never inside it — counted as wrong, a world nobody could reach read as 1% accuracy.
    answered = [one for one in results if not one.get("trouble")]
    summary = {"accuracy": round(sum(r["correct"] for r in answered) / max(1, len(answered)), 3),
               "questions": len(answered), "never reached the world": len(results) - len(answered),
               "the host's own bad calls": sum(1 for one in results if one.get("the host's own")),
               "world": args.db, "label": args.label,
               "cost_usd": round(spent["cost"], 2), "turns": spent["turns"],
               "minutes": round((time.monotonic() - started) / 60, 1)}
    (out_dir / "results.json").write_text(json.dumps({"summary": summary, "runs": results}, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
