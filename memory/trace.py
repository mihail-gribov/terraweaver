"""What the memory did, step by step, for a look afterwards: one line per step in `trace.jsonl`
beside the journal — what the gate decided of a message, which entry it was kept as, whether the
graph read it, what the reading added (links, topic and portrait layers), and what a question was
answered from. Nothing reads it back; a run can be replayed from it, the journal and the graph.

Secrets never reach it: what is traced is what was kept, and the journal withholds them first.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

_path: Path | None = None
_lock = threading.Lock()


def to(path: Path | None) -> None:
    global _path
    _path = Path(path) if path else None


def step(name: str, **data) -> None:
    if _path is None:
        return
    line = {"at": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "step": name, **data}
    with _lock, _path.open("a") as file:
        file.write(json.dumps(line, ensure_ascii=False, default=str) + "\n")
