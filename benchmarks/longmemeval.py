"""The LongMemEval data, as this project needs to see it.

One instance is a question plus the chat sessions it must be answered from, each session
carrying the date it happened. That shape is already ours: sessions arrive in order, each is
something the person said on a day, and the question comes later. So the loader's whole job is
to hand the sessions over in the order they happened and to keep the dates attached.

Two things worth knowing about the data. The `oracle` file holds only the sessions that carry
the answer — it is the upper bound on retrieval, so a loss there is a loss of reading, not of
finding. And a question id ending in `_abs` is an abstention case: the history does not contain
the answer and the right response is to say so.
"""
import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "longmemeval"
FILES = {"oracle": "longmemeval_oracle.json", "s": "longmemeval_s.json", "m": "longmemeval_m.json"}

TYPES = ("single-session-user", "single-session-assistant", "single-session-preference",
         "multi-session", "temporal-reasoning", "knowledge-update")


@dataclass
class Session:
    when: str                 # as the dataset writes it: "2023/04/10 (Mon) 17:50"
    turns: list[dict]         # {"role": user|assistant, "content": str}

    @property
    def date(self) -> datetime:
        return datetime.strptime(self.when.split(" (")[0] + self.when.split(") ")[1], "%Y/%m/%d%H:%M")

    def as_text(self) -> str:
        return "\n\n".join(f"{turn['role']}: {turn['content']}" for turn in self.turns)


@dataclass
class Instance:
    id: str
    kind: str                 # question_type
    question: str
    answer: str
    asked_on: str
    sessions: list[Session]   # oldest first

    @property
    def abstention(self) -> bool:
        return self.id.endswith("_abs")

    @property
    def size(self) -> int:
        return sum(len(turn["content"]) for session in self.sessions for turn in session.turns)


def load(which: str = "oracle") -> list[Instance]:
    path = DATA / FILES[which]
    if not path.exists():
        raise SystemExit(f"{path} is missing — run benchmarks/fetch.sh {which}")
    out = []
    for row in json.loads(path.read_text()):
        sessions = [Session(when, turns) for when, turns
                    in zip(row["haystack_dates"], row["haystack_sessions"])]
        sessions.sort(key=lambda session: session.date)
        out.append(Instance(row["question_id"], row["question_type"], row["question"],
                            row["answer"], row["question_date"], sessions))
    return out


def slice_of(instances: list[Instance], count: int, kinds: list[str] | None = None,
             seed: int = 0) -> list[Instance]:
    """A stratified sample: the same number from each question type, so a small run still says
    something per type. A run of 20 over six types is not 20 random draws — three of each is a
    signal, and twelve temporal-reasoning questions plus one of everything else is not."""
    wanted = kinds or list(TYPES)
    pools = {kind: [i for i in instances if i.kind == kind] for kind in wanted}
    picked, rng = [], random.Random(seed)
    for kind, pool in pools.items():
        rng.shuffle(pool)
        picked += pool[:max(1, count // len(wanted))]
    return picked[:count] if count else picked
