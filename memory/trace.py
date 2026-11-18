"""What the memory did, step by step, for a look afterwards: one line per step in `trace.jsonl`
beside the journal — what the gate decided of a message, which entry it was kept as, whether the
graph read it, what the reading added (links, topic and portrait layers), and what a question was
answered from. Nothing reads it back; a run can be replayed from it, the journal and the graph.

Secrets never reach it: what is traced is what was kept, and the journal withholds them first.
What the user has forgotten leaves it too (`forget`, called with the journal's forget).
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


def forget(taken: list[tuple[int, str]]) -> None:
    """A forget reaches the trace too: every line of a forgotten entry goes — by its number, or by
    its words wherever they were traced (the message at the gate, a fact found for a question)."""
    if _path is None or not taken:
        return
    numbers = {n for n, _ in taken}
    words = set()
    for _, text in taken:
        # A kept entry is the rewrite, with the words as said beside it when they differ.
        rewrite, _, said = text.partition('\n(said: "')
        words |= {w for w in (rewrite.strip(), said.removesuffix('")').strip()) if w}

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v)

    def forgotten(line: str) -> bool:
        try:
            row = json.loads(line)
        except ValueError:
            return False
        return row.get("entry") in numbers or any(w in s for s in strings(row) for w in words)
    with _lock:
        if not _path.exists():
            return
        kept = [line for line in _path.read_text().splitlines() if line.strip() and not forgotten(line)]
        temporary = _path.with_suffix(".tmp")
        temporary.write_text("".join(line + "\n" for line in kept))
        temporary.replace(_path)
