"""Every fact of the slice, as it landed in a world: held, ended, in prose, or missing — and what the world answers now.

    .venv/bin/python experiments/fact_audit.py var/run12/world [--upto 455] [--show]

Free, no model. A fact is a sentence; its *frame* is the sentence without its answer ("The capital
of Australia is ___"), and the answer is the end the sentence finishes on. Tellings of one frame are
read in order: the last is what must hold now, the earlier ones are history. That is the
benchmark's own rule, and it is what `check_expected.py` got wrong for "The X of Y is Z": it keyed a
correction on (subject, predicate), so a new chairperson of Fatah was a new subject and the old one
read as a fact the world had lost.

For each fact it says how the link between the frame's thing and the answer stands (typed and
holding, typed and ended, only a bare link, only prose, an end missing), and for each frame what
the world answers now under the word that holds the last telling: the answer alone, the answer
beside others, or something else.
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "experiments")]

from check_expected import open_world, written_down   # noqa: E402


def frames(upto: int) -> dict:
    """frame -> [(fact, answer, asked)] in order, from the written-down expectations."""
    out = collections.defaultdict(list)
    for one in written_down(None):
        if one["fact"] > upto:
            continue
        said = one["said"].strip()
        for gold, asked in ((one["object"], one["subject"]), (one["subject"], one["object"])):
            # The full stop is the sentence's, unless the answer ends in one: "Apple Inc.", "D.C."
            if not said.lower().endswith(str(gold).lower()):
                said = said.rstrip(" .")
            if said.lower().endswith(str(gold).lower()):
                out[said[: len(said) - len(str(gold))]].append((one["fact"], str(gold), str(asked)))
                break
    return {k: sorted(v) for k, v in out.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("world", type=Path)
    parser.add_argument("--upto", type=int, default=455)
    parser.add_argument("--show", action="store_true", help="print every fact, not only the lost")
    args = parser.parse_args()
    world = open_world(args.world.resolve()).world

    by_name = collections.defaultdict(list)
    for name, cls in world.classes.items():
        if cls._spec.get("relation"):
            continue
        for entity in world.all(name, limit=None):
            for key in ("name", "full_name", "title", "label"):
                shown = entity.__dict__.get(key)
                if isinstance(shown, str) and shown.strip():
                    by_name[shown.strip().lower()].append(entity)
                    break

    def look(text: str) -> list:
        return by_name.get(str(text).strip().lower(), [])

    def free(link) -> bool:
        return bool((type(link)._spec.get("relation") or {}).get("free"))

    def standing(link) -> bool:
        try:
            return link.current()
        except Exception:  # noqa: BLE001
            return getattr(link, "valid_until", None) is None

    def links_between(a_list, b_list) -> list:
        out = []
        for a in a_list:
            try:
                rels = a.relations(any_time=True, history=True)
            except Exception:  # noqa: BLE001
                continue
            for link in rels:
                far = link.object if link.subject == a else link.subject
                if any(far == b for b in b_list):
                    out.append(link)
        return out

    def in_prose(a_list, text: str) -> bool:
        wanted = str(text).lower()
        return any(wanted in str(line).lower() for e in a_list
                   for line in (e.__dict__.get("descriptions") or []))

    fact_state = {}
    frame_state = collections.Counter()
    lost_frames = []
    for frame, tellings in frames(args.upto).items():
        last_fact = tellings[-1][0]
        last_gold = tellings[-1][1]
        for fact, gold, asked in tellings:
            a, g = look(asked), look(gold)
            if not a or not g:
                state = "an end was never made a thing" if not in_prose(a or g, asked if not a else gold) \
                    else "only prose (an end is only words)"
            else:
                found = links_between(a, g)
                typed = [l for l in found if not free(l)]
                if typed and any(standing(l) for l in typed):
                    state = "typed, holding"
                elif typed:
                    state = "typed, ended"
                elif found:
                    state = "only a bare link (unread)"
                elif in_prose(a, gold) or in_prose(g, asked):
                    state = "only prose"
                else:
                    state = "both ends, no link"
            role = "now" if fact == last_fact else "history"
            fact_state[fact] = (role, state, frame + gold)
        # What the world answers for this frame now, under every typed word that ever joined the
        # asked thing to the last answer.
        asked, gold = tellings[-1][2], last_gold
        a, g = look(asked), look(gold)
        kinds = {type(l).__name__ for l in links_between(a, g) if not free(l)} if a and g else set()
        values = set()
        for e in a:
            try:
                for link in e.relations():
                    if type(link).__name__ in kinds:
                        far = link.object if link.subject == e else link.subject
                        values.add(far.display_name())
            except Exception:  # noqa: BLE001
                pass
        if not kinds:
            answer = "no typed link to the answer"
        elif values == {g[0].display_name()} if g else False:
            answer = "the answer alone"
        elif g and g[0].display_name() in values:
            answer = "the answer beside others"
        else:
            answer = "something else (the answer ended)"
        if len(a) > 1 or len(g) > 1:
            answer += f" [copies {len(a)}x{len(g)}]"
        frame_state[answer] += 1
        if answer != "the answer alone":
            lost_frames.append((last_fact, answer, frame + gold, sorted(values)[:4]))

    states = collections.Counter((role, state) for role, state, _ in fact_state.values())
    print(f"{len(fact_state)} facts in {sum(frame_state.values())} frames\n")
    for role in ("now", "history"):
        total = sum(n for (r, _), n in states.items() if r == role)
        print(f"facts that must hold {'now' if role == 'now' else 'as history'}: {total}")
        for (r, state), n in states.most_common():
            if r == role:
                print(f"   {n:4}  {state}")
    print("\nwhat the world answers per frame, now:")
    for answer, n in frame_state.most_common():
        print(f"   {n:4}  {answer}")
    print("\n--- frames not answered by the answer alone")
    for fact, answer, said, values in sorted(lost_frames):
        print(f"  {fact:4} {answer:38} {said[:70]:70} {values}")
    print("\n--- facts that must hold now and do not")
    for fact, (role, state, said) in sorted(fact_state.items()):
        if role == "now" and state != "typed, holding" or args.show:
            print(f"  {fact:4} {role:7} {state:34} {said[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
