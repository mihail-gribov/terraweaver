"""Run MemoryAgentBench's Conflict Resolution (FactConsolidation) against the world.

    benchmarks/fetch.sh mab
    .venv/bin/python benchmarks/run_fc.py --hops sh --questions 20
    .venv/bin/python benchmarks/run_fc.py --hops mh --questions 20 --mode baseline

Unlike LongMemEval, one world serves the whole variant: the benchmark's own design is "inject
once, query many", and it is the right shape here anyway — 455 facts are one person's world,
and a hundred questions are a hundred readings of it. The facts go in batches, each batch a day
later than the last, so that "a larger serial is newer" becomes "this was said later", which is
what the world already understands.

No judge: the gold answer is a list of strings and the match is a normalised substring. Every
system in the published table is graded the same way, which is why this is the number worth
having.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import factconsolidation as fc
import host as hosting

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "benchmarks" / "results"

RECORD = """\
It is {when}. Here are facts I am telling you, in the order I learned them. Record all of them.

If one of them says something different from what is already recorded about the same thing — the \
same person, the same organisation, the same place — then what I am telling you now is what \
holds, and the earlier one stopped holding today. Keep both if you can; what matters is that \
asking later gives today's answer.

{facts}"""

ASK = """\
Today is {when}. {question}

Answer from what is recorded, with the value and nothing else. If a thing was recorded more \
than once over time, give the one that holds now, not the first one."""


def _what_went_wrong(got: dict) -> dict | None:
    """The technical failures of one turn, told apart from anything the host decided.

    A host that could not reach the world, or a turn the CLI itself ended with an error, is not the
    host answering badly — it is our side failing, and the two were indistinguishable in the numbers
    until now. Whatever the host did with the world it could reach is a substantive outcome and is
    measured by the check and by the reading's own record, not here.
    """
    if got.get("unreachable"):
        return {"what": f"the world was unreachable: {', '.join(got['unreachable'])}",
                "kind": "technical", "turns": got.get("turns"), "said": got.get("text", "")[:300]}
    if got.get("trouble"):
        return {"what": got["trouble"], "kind": "technical", "turns": got.get("turns")}
    if got.get("tool_errors"):
        return {"what": f"the world failed {len(got['tool_errors'])} call(s): "
                        f"{got['tool_errors'][0]}", "kind": "technical",
                "turns": got.get("turns"), "all": got["tool_errors"][:5]}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hops", default="sh", choices=["sh", "mh"])
    parser.add_argument("--context", default="6k", choices=["6k", "32k", "64k", "262k"])
    parser.add_argument("--mode", default="world", choices=["world", "baseline"])
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--questions", type=int, default=20)
    parser.add_argument("--chunk", type=int, default=25, help="facts per recording turn")
    parser.add_argument("--facts", type=int, default=0,
                        help="write only the first N facts — a part-wise check of the writing, "
                             "before an hour is spent on all 455")
    parser.add_argument("--from", dest="begin", type=int, default=1,
                        help="start at this fact, adding to the world --keep already holds "
                             "instead of writing it again from the first")
    parser.add_argument("--only", default=None,
                        help="write just these facts (22,28,33) — the aimed re-run of the ones "
                             "that went wrong, at a few cents each. Each keeps the day its own "
                             "batch was said on, so what is later stays later")
    parser.add_argument("--keep", default=None,
                        help="where the world is built, kept afterwards for reask.py "
                             "(a temporary folder by default, also kept but harder to find)")
    parser.add_argument("--port", type=int, default=7050)
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    if args.facts:
        variant.facts = variant.facts[:args.facts]
    only = {int(n) for n in args.only.replace(" ", "").split(",") if n} if args.only else None
    questions = variant.questions[:args.questions]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = RESULTS / f"{stamp}-{variant.name}-{args.mode}-{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    config = {"benchmark": variant.name, "hops": variant.hops, "facts": len(variant.facts),
              "questions": len(questions), "chunk": args.chunk, "mode": args.mode,
              "wrote": sorted(only) if only else f"{args.begin}..{len(variant.facts)}",
              "added_to": str(args.keep) if args.keep and (only or args.begin > 1) else None,
              "host_model": args.model, "judge": "string match, no model",
              # Whether this world can turn what was said in words into types at the close. A run
              # without one records links and never types them, and the number means something
              # else; it is written down here so no number is ever read without it.
              "engineer": hosting.engineer(),
              "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True).stdout.strip(),
              "self_reported": True, "started": stamp}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    print(json.dumps(config, indent=2))

    if args.keep:
        # Resolved, because the host's MCP config path is built from this and a relative one
        # lands inside the agent's own folder: "MCP config file not found: …/var/x/var/x/mcp…".
        work = Path(args.keep).resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = Path(tempfile.mkdtemp(prefix=f"tw-fc-{args.hops}-"))
    print(f"world: {work}/world.db   grown: {work}/grown")
    log = out_dir / "host.jsonl"
    server = agent = None
    spent = {"turns": 0, "cost": 0.0}
    started = time.monotonic()
    try:
        if args.mode == "world":
            server = hosting.start_server(work / "world.db", args.port)
        agent = (hosting.World if args.mode == "world" else hosting.Baseline)(
            work, variant.name, args.port)

        last_day = None
        for batch, (day, facts) in enumerate(variant.batches(args.chunk)):
            first = batch * args.chunk + 1              # the number of this batch's first fact
            due = [fact for number, fact in enumerate(facts, first)
                   if number >= args.begin and (only is None or number in only)]
            if not due:
                continue
            last_day = day
            listed = "\n".join(f"- {fact}" for fact in due)
            if server is not None and not hosting.answering(args.port):
                raise RuntimeError(f"the world stopped answering before the batch of {day} — "
                                   f"nothing was written for it, and a run with a batch missing is "
                                   f"not a measurement")
            got = hosting.ask(agent, RECORD.format(when=day.isoformat(), facts=listed),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            trouble = _what_went_wrong(got)
            if trouble:
                # Technical, not substantive: the host never reached the world, so whatever it
                # answered is not evidence about this world. Said out loud and the run stops, rather
                # than a batch of 25 facts quietly missing from a number.
                (out_dir / "trouble.jsonl").open("a").write(
                    json.dumps({"batch": day.isoformat(), "facts": len(due), **trouble}) + "\n")
                raise RuntimeError(f"batch {day}: {trouble['what']}")
            if (got.get("limited") or {}).get("status") not in (None, "allowed"):
                (out_dir / "trouble.jsonl").open("a").write(
                    json.dumps({"batch": day.isoformat(), "what": "rate limit",
                                **got["limited"]}) + "\n")
            print(f"  recorded {day} ({len(due)} facts)  {got['turns']} turns  "
                  f"${spent['cost']:.2f} so far")

        asked_on = (last_day + timedelta(days=1)).isoformat()
        results = []
        for number, question in enumerate(questions, 1):
            if server is not None:
                hosting.answering(args.port)
            got = hosting.ask(agent, ASK.format(when=asked_on, question=question.text),
                              agent.conversation(), None, log, args.model)
            spent["turns"] += got["turns"]
            spent["cost"] += got["cost"]
            trouble = _what_went_wrong(got)
            right = False if trouble else fc.correct(got["text"], question.gold)
            results.append({"id": question.id, "question": question.text, "gold": question.gold,
                            "answer": got["text"][:300], "correct": right,
                            "turns": got["turns"], "cost": round(got["cost"], 3),
                            # A question the host could not put to the world is not a question this
                            # world answered wrongly, and counted as wrong it lowers the number for a
                            # reason that has nothing to do with the world. Kept apart and reported.
                            **({"trouble": trouble} if trouble else {})})
            if trouble:
                (out_dir / "trouble.jsonl").open("a").write(
                    json.dumps({"question": question.id, **trouble}) + "\n")
            print(f"{'!! ' if trouble else ('ok ' if right else '   ')} "
                  f"{number:>3}/{len(questions)} {question.gold} "
                  f"<- {(trouble['what'] if trouble else got['text'][:80]).replace(chr(10), ' ')}")
    finally:
        if server:
            hosting.stop(server)
        if agent:
            hosting.forget_folder_memory(agent.cwd)

    # Accuracy over the questions that actually reached the world. The ones that did not are
    # reported beside it and never hidden inside it: a technical loss counted as a wrong answer is a
    # number about our plumbing wearing the world's name.
    troubled = [one for one in results if one.get("trouble")]
    answered = [one for one in results if not one.get("trouble")]
    summary = {"accuracy": round(sum(r["correct"] for r in answered) / max(1, len(answered)), 3),
               "questions": len(answered), "never reached the world": len(troubled),
               "cost_usd": round(spent["cost"], 2),
               "turns": spent["turns"], "minutes": round((time.monotonic() - started) / 60, 1)}
    (out_dir / "results.json").write_text(json.dumps(
        {"config": config, "summary": summary, "runs": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print(out_dir)
    print(f"the world it wrote: {work}/world.db  (reask.py --db that --specs {work}/grown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
