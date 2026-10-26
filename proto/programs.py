"""The registry of tasks: the programs the world has written, each a file that says what it solves.

    var/programs/<name>.py     a program; its docstring is the kind of task it solves
    var/programs/runs.jsonl    which task each program served, and whether it answered

A task is a program, literally: before writing one, the world looks for a program kept for a task
of the same kind, and the programmer starts from it instead of from nothing. Written from nothing,
the same task got a different program every run, and a different answer (2026-10-26).

Which program fits is a closed question, asked of the decision model: one choice among the kept
programs' descriptions and "none — a new kind of task".
"""
import ast
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "var" / "programs"
NONE = "none of these: a new kind of task"


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
        """The kept program for a task of the same kind, or None. At most 25 are offered: the
        decision model chooses among 2–26 options, and one is "none"."""
        kept = list(self.all().items())[:25]
        if not kept:
            return None
        options = [("new", NONE)] + [(n, d.splitlines()[0]) for n, d in kept]
        try:
            got = judge.choice(f"The task: {task}",
                               "Which kept program solves a task of the same kind — the same steps, whatever the "
                               "user, the thing or the numbers?", options)
        except Exception:  # noqa: BLE001 - not finding one only means writing a new one
            return None
        return None if got["choice"] == "new" else got["choice"]

    def keep(self, program: str, task: str, answered: bool, based_on: str | None = None) -> str | None:
        """Keep a program that answered: over the one it was based on (its newer version), else
        as a new one named from its description. Every run is logged, answered or not."""
        name = None
        self.path.mkdir(parents=True, exist_ok=True)
        if answered and (said := description(program)):
            name = based_on or self._name(said)
            (self.path / f"{name}.py").write_text(program)
        with open(self.path / "runs.jsonl", "a") as f:
            f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "task": task, "program": name,
                                "based_on": based_on, "answered": answered}, ensure_ascii=False) + "\n")
        return name

    def _name(self, said: str) -> str:
        stem = "_".join(re.sub(r"[^a-z0-9]+", " ", said.splitlines()[0].lower()).split()[:6]) or "program"
        name, n = stem, 2
        while (self.path / f"{name}.py").exists():
            name, n = f"{stem}_{n}", n + 1
        return name
