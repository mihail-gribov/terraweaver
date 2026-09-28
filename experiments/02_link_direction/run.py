"""Which way round — put to each picker in the words the world actually uses.

    .venv/bin/python experiments/02_link_direction/run.py <a world kept by --keep> [--limit 60]

**The question.** A link is written between two things and the account says which way it goes. Can a
closed model tell a link written the right way round from one written backwards — asked as the world
now asks it, and answered well enough to act on?

**Why ask again.** Jev was measured on this in 2026-09-24 and deliberately left unwired: 5/5 on a
picked set of plain sentences but rejecting the benchmark's deliberate falsehoods, 9/12 on "can this
be so at all", 7/12 on "which of A or B". The reason for leaving it out was not the average but the
shape of the errors — the wrong answers came with p=0.93 and p=0.89, and a confidently wrong verdict
corrupts a correct link, which is worse than the error it was meant to catch.

Since then the question changed. It is no longer "is this true" or "which of these two": the world
renders what it is about to hold as a phrase — «Chang'an capital of Tang Empire» — and asks whether
that is the same thing the account says, with `backwards` as a named option. That question has not
been measured with anybody, and it is built here by `check._asking`, the very function the live
reading calls, so what is measured is the real question and not a paraphrase of it.

**What it is graded against.** `experiments/expected/*.json` — what each fact owed, written down once
and corrected by hand: which entity is the subject, which the object. So the verdict a picker gives
is compared with the direction the sentence had, not with the world's opinion of itself.

**What it settles.** Per picker: how often it is right, and — the number that decided this before —
how sure it is when it is wrong. A picker that is wrong at p=0.5 can be wired behind a threshold; one
that is wrong at p=0.93 cannot be wired at all.
"""
import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from experiments.check_expected import open_world, written_down  # noqa: E402
from terraweaver import outside, prompts  # noqa: E402
from terraweaver.formalise import check  # noqa: E402


def pickers(room: int) -> dict:
    """Everybody who can answer a closed question here, and nobody who cannot be reached."""
    import os

    out = {}
    if os.environ.get("TYPESAFE_API_KEY"):
        try:
            out["jev"] = outside.Jev()
        except Exception as wrong:  # noqa: BLE001
            print(f"jev: not reachable — {type(wrong).__name__}: {wrong}", flush=True)
    if os.environ.get("NEBIUS_API_KEY"):
        # The engineer answering a closed question, which is what the live reading falls back to
        # when no picker is configured — so it is the standing arrangement and belongs in the table.
        out["nemotron-as-choices"] = outside.AsChoices(outside.Nemotron(ttl=90, thinking_room=room))
    return out


def by_name(runtime) -> dict:
    """Every entity under the name its own class calls it by. As `check_expected` reads them."""
    found: dict = {}
    for cls in runtime.world.classes.values():
        if cls._spec.get("relation"):
            continue
        declared = [a["name"] for a in cls._spec.get("attributes", [])]
        keys = [k for k in ("name", "full_name", "title", "label") if k in declared]
        for entity in runtime.world.all(cls.__name__, limit=None, history=True):
            said = next((getattr(entity, k, None) for k in keys if getattr(entity, k, None)), None)
            if said:
                found.setdefault(said, []).append(entity)
    return found


def named(found: dict, text: str) -> list:
    if text in found:
        return found[text]
    for name, got in found.items():
        if name and (name in text or text in name) and abs(len(name) - len(text)) < 6:
            return got
    return []


def links_between(runtime, subjects: list, objects: list):
    """(link, whether its subject is the end the sentence made the subject) for each typed link."""
    out = []
    for entity in subjects:
        for link in entity.relations():
            far = link.object if link.subject == entity else link.subject
            if any(far == one for one in objects):
                kind = (type(link)._spec.get("relation") or {}).get("kind")
                if kind and kind != "related":
                    out.append((link, link.subject == entity))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("world", type=Path, help="a world kept by --keep: world.db and grown/")
    parser.add_argument("--limit", type=int, default=60, help="how many links to ask about")
    parser.add_argument("--upto", type=int, default=100, help="facts written down up to this one")
    parser.add_argument("--room", type=int, default=16000, help="thinking room for the engineer")
    args = parser.parse_args()

    runtime = open_world(args.world.resolve())
    found = by_name(runtime)
    asked_of = pickers(args.room)
    if not asked_of:
        print("no picker can be reached: set TYPESAFE_API_KEY or NEBIUS_API_KEY (.env is read by "
              "benchmarks/host.py, not by terraweaver)")
        return 1
    print(f"pickers: {', '.join(asked_of)}\n", flush=True)

    # One row per link the world holds for a fact somebody wrote down, with the direction the
    # sentence gave. A link the world does not hold cannot be asked about, and is not a miss here.
    rows = []
    for one in written_down(args.upto):
        if one.get("superseded"):
            continue
        subjects, objects = named(found, one["subject"]), named(found, one["object"])
        if not subjects or not objects:
            continue
        for link, right_way in links_between(runtime, subjects, objects):
            rows.append({"said": one["said"], "link": link, "right_way": right_way})
            break
        if len(rows) >= args.limit:
            break
    print(f"{len(rows)} link(s) to ask about\n", flush=True)

    tally = {name: {"right": 0, "wrong": 0, "unsure": 0, "sure_when_wrong": [],
                    "sure_when_right": [], "failed": 0} for name in asked_of}
    for n, row in enumerate(rows, 1):
        link = row["link"]
        kind = (type(link)._spec.get("relation") or {}).get("kind")
        claim = {"what": "link", "word": kind, "subject": link.subject, "object": link.object}
        instructions, options = check._asking(claim)
        state = prompts.IS_IT_SAID.format(words=row["said"])
        owed = check.SAYS_SO if row["right_way"] else check.BACKWARDS
        line = [f"{n:>3} {'as written' if row['right_way'] else 'BACKWARDS  '}"]
        for name, picker in asked_of.items():
            try:
                answers = picker.ask(state, {"q0": {"type": "choice", "instructions": instructions,
                                                    "criteria": options}})
            except Exception as wrong:  # noqa: BLE001
                tally[name]["failed"] += 1
                line.append(f"{name}=failed({type(wrong).__name__})")
                continue
            scored = (answers.get("q0") or {}).get("probabilities") or {}
            if not scored:
                tally[name]["unsure"] += 1
                line.append(f"{name}=nothing")
                continue
            verdict = max(scored, key=scored.get)
            sure = float(scored[verdict])
            if verdict == owed:
                tally[name]["right"] += 1
                tally[name]["sure_when_right"].append(sure)
            else:
                tally[name]["wrong"] += 1
                tally[name]["sure_when_wrong"].append(sure)
            line.append(f"{name}={verdict}@{sure:.2f}{'' if verdict == owed else ' <-- wrong'}")
        print("  ".join(line), flush=True)

    print()
    for name, got in tally.items():
        asked = got["right"] + got["wrong"]
        share = f"{100 * got['right'] // asked}%" if asked else "—"
        wrong_at = (f"{statistics.mean(got['sure_when_wrong']):.2f}"
                    if got["sure_when_wrong"] else "never wrong")
        right_at = (f"{statistics.mean(got['sure_when_right']):.2f}"
                    if got["sure_when_right"] else "—")
        print(f"{name}: {got['right']}/{asked} {share}  "
              f"sure when wrong {wrong_at}, when right {right_at}  "
              f"(nothing said {got['unsure']}, failed {got['failed']})")
    print("\nA picker wrong at a low confidence can be wired behind a threshold; one wrong at a high "
          "confidence cannot be wired at all, which is what left this unwired in September.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
