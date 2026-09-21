"""MemoryAgentBench's Conflict Resolution task, in the shape this world needs.

The task is the one place in the field where everybody fails: a list of numbered facts in which
a later number overrides an earlier one about the same thing, and questions that ask what holds
*now*. Single-hop asks one value ("who is Roy Rogers married to" — stated twice, 447 and 452);
multi-hop asks a chain, and every link of the chain has to be the current value too. Published
numbers: Zep/Graphiti 7% single-hop, Mem0 18%, HippoRAG-v2 54%, and no system above 7% on
multi-hop — with a deterministic `max(serial)` recipe reaching 78% (arXiv:2606.01435).

Two decisions about the adaptation, both of which belong in the open:

**The serial becomes a date.** Their rule is "the larger number is newer"; ours is that a
statement holds from when it was said. So fact *n* is stated on day *n* of a made-up calendar,
which is the same rule written in our words — and it lets supersession happen the way it does
for a person who says something new in March.

**The facts arrive in batches, not all at once.** The benchmark's own design is incremental
multi-turn injection, and it is also the only honest way to write them: a world is written over
time, and a batch is a sitting.

Grading needs no judge. The gold answer is a list of strings, so a normalised substring match
settles it — objective, free, and the same rule for every system.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "memoryagentbench" / "Conflict_Resolution.parquet"
DAY_ONE = date(2020, 1, 1)


@dataclass
class Question:
    id: str
    text: str
    gold: list[str]


@dataclass
class Variant:
    name: str                 # factconsolidation_sh_6k …
    facts: list[str]          # in the order they were stated
    questions: list[Question]

    @property
    def hops(self) -> str:
        return "multi" if "_mh_" in self.name else "single"

    def batches(self, size: int = 25):
        """(the day it was said, the facts said that day) — oldest first."""
        for start in range(0, len(self.facts), size):
            yield DAY_ONE + timedelta(days=start // size), self.facts[start:start + size]


def load(hops: str = "sh", context: str = "6k") -> Variant:
    import pyarrow.parquet as pq

    if not DATA.exists():
        raise SystemExit(f"{DATA} is missing — run benchmarks/fetch.sh mab")
    wanted = f"factconsolidation_{hops}_{context}"
    for row in pq.read_table(DATA).to_pylist():
        ids = row["metadata"]["qa_pair_ids"]
        if not ids or not ids[0].startswith(wanted):
            continue
        facts = [line.split(". ", 1)[1].strip() for line in row["context"].splitlines()
                 if re.match(r"^\d+\.\s", line)]
        questions = [Question(qid, text, list(gold))
                     for qid, text, gold in zip(ids, row["questions"], row["answers"])]
        return Variant(wanted, facts, questions)
    raise SystemExit(f"no variant {wanted} in {DATA}")


def _flat(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"[^a-z0-9 ]+", " ", text).strip()


def correct(answer: str, gold: list[str]) -> bool:
    """Any of the accepted answers appearing in the response, ignoring case and punctuation."""
    said = _flat(answer)
    return any(_flat(option) and _flat(option) in said for option in gold)
