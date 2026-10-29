"""The registry of tasks: the programs the world has written, each a file that says what it solves.

    var/programs/<name>.py     a program; its docstring is the kind of task it solves
    var/programs/runs.jsonl    every run: the task, the program it used or made, whether it answered,
                               its attempts and seconds — the registry's statistics are read off it

    .venv/bin/python -m proto.programs        # the registry, with each program's statistics

A task is a program, literally: before writing one, the world looks for a program kept for a task
of the same kind, and the programmer starts from it instead of from nothing. Written from nothing,
the same task got a different program every run, and a different answer (2026-10-26).

Which program fits is a closed question, asked of the decision model about each kept program: is
the task the same kind as the one it was written for?
"""
import ast
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from proto.ttl import TTL
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "var" / "programs"
# A kept program is the same kind as a task when the judge says so with at least this: it is
# careful — the right ones read 0.39 and 0.52, the wrong ones 0.11 to 0.25 (2026-10-27).
SAME_KIND = 0.35
SHOWN = 50  # the newest kept programs asked about


def description(program: str) -> str:
    """The program's docstring, or "" when it has none or doesn't parse."""
    try:
        return (ast.get_docstring(ast.parse(program)) or "").strip()
    except SyntaxError:
        return ""


class Programs:
    def __init__(self, path: Path = HERE):
        self.path = path

    def all(self) -> dict[str, str]:
        """{name: description} of every kept program, newest first."""
        files = sorted(self.path.glob("*.py"), key=lambda f: f.stat().st_mtime, reverse=True) if self.path.exists() else []
        return {f.stem: d for f in files if (d := description(f.read_text()))}

    def text(self, name: str) -> str:
        return (self.path / f"{name}.py").read_text()

    def find(self, task: str, judge) -> str | None:
        """The kept program for a task of the same kind, or None: each kept program asked about
        by the decision model, with the task it was written for; the likeliest, if likely enough.

        Chosen from a list with "none" among the options, the judge sent "find out what the concert
        my wife mentioned is" to the product-picking program; asked of each program, it gave that
        0.16, a kettle 0.39, a laptop 0.52, colleagues 0.11, a Saturday concert 0.25 (2026-10-27)."""
        def p(name: str, said: str) -> float:
            try:
                return judge.noul(f"A program: {said.splitlines()[0]}\nIt was written for the task: "
                                  f"\"{self.task_of(name) or said.splitlines()[0]}\"\n\nA new task: \"{task}\"",
                                  "Is the task the same kind of task as the one the program was written for?",
                                  true="yes, the same kind of task", false="no, the task asks something else")["p"]["yes"]
            except Exception:  # noqa: BLE001 - not finding one only means writing a new one
                return 0.0
        kept = list(self.all().items())[:SHOWN]
        if not kept:
            return None
        with ThreadPoolExecutor(8) as pool:
            ps = list(pool.map(lambda kv: p(*kv), kept))
        best = max(range(len(kept)), key=lambda i: ps[i])
        return kept[best][0] if ps[best] >= SAME_KIND else None

    def task_of(self, name: str) -> str | None:
        """The task the program was last kept for."""
        return next((r["task"] for r in reversed(self.runs()) if r.get("program") == name and r.get("kept")), None)

    def keep(self, program: str, task: str, answered: bool, based_on: str | None = None,
             attempts: int = 1, seconds: float = 0, useful: bool = True) -> str | None:
        """Keep a program whose answer was useful: over the one it was based on (its newer
        version), else as a new one named from its description. Every run is logged, kept or not
        — a kept program that failed this time is a use of it all the same."""
        name = None
        self.path.mkdir(parents=True, exist_ok=True)
        if answered and useful and (said := description(program)):
            name = based_on or self._name(said)
            (self.path / f"{name}.py").write_text(program)
        with open(self.path / "runs.jsonl", "a") as f:
            f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "task": task,
                                "program": name or based_on, "based_on": based_on, "kept": bool(name),
                                "answered": answered, "useful": useful, "attempts": attempts, "seconds": round(seconds)},
                               ensure_ascii=False) + "\n")
        return name

    def expire(self, now: datetime | None = None) -> list[str]:
        """Remove every program last used more than TTL ago (never logged: since its file was
        written). Its runs stay in the log, and its removal is logged too. Returns the names."""
        cut = ((now or datetime.now()) - TTL).isoformat(timespec="seconds")
        used = {}
        for r in self.runs():
            if r.get("program"):
                used[r["program"]] = max(used.get(r["program"], ""), r["at"])
        gone = []
        for name in self.all():
            file = self.path / f"{name}.py"
            last = used.get(name) or datetime.fromtimestamp(file.stat().st_mtime).isoformat(timespec="seconds")
            if last < cut:
                file.unlink()
                gone.append(name)
        if gone:
            with open(self.path / "runs.jsonl", "a") as f:
                for name in gone:
                    f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "removed": name,
                                        "why": f"not used since {used.get(name) or 'it was written'}"}) + "\n")
        return gone

    def runs(self) -> list[dict]:
        path = self.path / "runs.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []

    def stats(self) -> dict[str, dict]:
        """{name: {"created", "last_used", "uses", "reuses", "answered", "versions", "first_attempt",
        "seconds", "tasks"}} for every kept program: when it was made and last used, how many runs
        used it and how many of those started from it, how many answered, how many replaced it
        with a newer version, how many ran on the first attempt, the median seconds, the last tasks."""
        out = {}
        for name, said in self.all().items():
            mine = [r for r in self.runs() if r.get("program") == name and "task" in r]
            seconds = sorted(r["seconds"] for r in mine if r.get("seconds"))
            out[name] = {
                "about": said.splitlines()[0],
                "created": min((r["at"] for r in mine), default=None),
                "last_used": max((r["at"] for r in mine), default=None),
                "uses": len(mine),
                "reuses": sum(1 for r in mine if r.get("based_on") == name),
                "answered": sum(1 for r in mine if r.get("answered")),
                "versions": sum(1 for r in mine if r.get("kept", r.get("answered"))),
                "first_attempt": sum(1 for r in mine if r.get("answered") and r.get("attempts", 1) == 1),
                "seconds": seconds[len(seconds) // 2] if seconds else None,
                "tasks": [r["task"] for r in mine][-3:],
                "lives_until": (datetime.fromisoformat(max(r["at"] for r in mine)) + TTL).isoformat(
                    timespec="seconds") if mine else None,
            }
        return out

    def _name(self, said: str) -> str:
        stem = "_".join(re.sub(r"[^a-z0-9]+", " ", said.splitlines()[0].lower()).split()[:6]) or "program"
        name, n = stem, 2
        while (self.path / f"{name}.py").exists():
            name, n = f"{stem}_{n}", n + 1
        return name


def main() -> None:
    for name, st in Programs().stats().items():
        print(f"{name}\n  {st['about']}\n  made {st['created']}, last used {st['last_used']}; "
              f"{st['uses']} runs ({st['reuses']} from it), {st['answered']} answered, "
              f"{st['first_attempt']} on the first attempt, {st['versions']} versions, " + (f"~{st['seconds']} s a run" if st["seconds"] else "time not measured"))
        for task in st["tasks"]:
            print(f"    - {task}")
        print(f"  kept until {st['lives_until']}, unless used again")


if __name__ == "__main__":
    main()
