"""Conversations to read, in one shape — [{"role": "user" | "agent", "text": ...}], in order — with
whatever gold each source carries kept beside it."""
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dialogue(path: str) -> list[dict]:
    """A dialogue run (run.json): its history sessions and its task, one after another, each
    message marked with its session."""
    run = json.loads(Path(path).read_text())
    out = []
    for n, sitting in enumerate(run["history"] + [run["task"]]):
        for turn in sitting:
            out += [{"role": "user", "text": turn["say"], "session": n},
                    {"role": "agent", "text": turn.get("reply", ""), "session": n}]
    return out


def memops(name: str) -> list[dict]:
    """A MemOps sample (data/memops): its segments' dialogue; each user turn carries `gold`, the
    operations whose trigger quote stands in it."""
    path = ROOT / "data" / "memops" / "raw" / "generated_result" / "2-evidence_conversation" / f"{name}.json"
    sample = json.loads(path.read_text())
    out = []
    for segment in sample["conversations"]:
        for n, turn in enumerate(segment["dialogue"]):
            m = {"role": "agent" if turn["role"] == "assistant" else "user", "text": turn["content"]}
            if m["role"] == "user":
                m["gold"] = [{"type": op["type"], "validity": op.get("validity"), "quote": op["trigger_span"]["quote"]}
                             for op in sample["operations"]
                             if op.get("trigger_span", {}).get("quote", "\0") in turn["content"]]
            out.append(m)
    return out


def memops_names() -> list[str]:
    return sorted(Path(f).stem for f in glob.glob(str(ROOT / "data" / "memops" / "raw" / "generated_result"
                                                        / "2-evidence_conversation" / "*.json")))


def longmemeval(index: int) -> list[dict]:
    """A LongMemEval question's sessions, in order; a user turn with `has_answer` holds the
    evidence the question is about (gold: something to keep)."""
    question = json.loads((ROOT / "data" / "longmemeval" / "longmemeval_oracle.json").read_text())[index]
    out = []
    for session in question["haystack_sessions"]:
        for turn in session:
            m = {"role": "agent" if turn["role"] == "assistant" else "user", "text": turn["content"]}
            if turn.get("has_answer"):
                m["gold"] = [{"type": "keep"}]
            out.append(m)
    return out
