"""Keep a world a run built, so the questions can be asked of it without building it again.

A full slice costs two hours and twelve dollars to record. The answering side has no business
paying that every time it wants to try something, and the world it asks of should be one
particular world, the same one, not whatever the last run happened to produce.

    .venv/bin/python experiments/freeze.py <run directory> <name>
"""
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHERE = ROOT / "worlds"


def main() -> int:
    run = Path(sys.argv[1]).resolve()
    name = sys.argv[2] if len(sys.argv) > 2 else run.name
    into = WHERE / name
    if into.exists():
        shutil.rmtree(into)
    (into / "grown").mkdir(parents=True)
    shutil.copy(run / "world.db", into / "world.db")
    for spec in sorted((run / "grown").glob("*.json")):
        shutil.copy(spec, into / "grown" / spec.name)

    conn = sqlite3.connect(into / "world.db")
    conn.execute("VACUUM")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    entities = links = 0
    for table in tables:
        if table.startswith(("facts_", "reasoning_", "sqlite_")):
            continue
        try:
            attrs = {r[0] for r in conn.execute(f"SELECT DISTINCT attr FROM '{table}'")}
        except sqlite3.OperationalError:
            continue
        if not attrs:
            continue
        n = conn.execute(f"SELECT count(DISTINCT instance_id) FROM '{table}'").fetchone()[0]
        if {"subject", "object"} <= attrs:
            links += n
        else:
            entities += n
    said = sum(conn.execute(f"SELECT count(*) FROM '{t}'").fetchone()[0]
               for t in tables if t.startswith("facts_"))
    batches = run / "batches.jsonl"
    given = sum(1 for _ in open(batches)) * 10 if batches.exists() else None

    (into / "README.md").write_text(
        f"# {name}\n\n"
        f"A world one recording run built, frozen so questions can be asked of it without "
        f"building it again.\n\n"
        f"- facts given: {given if given is not None else 'unknown'}\n"
        f"- entities: {entities}\n"
        f"- links: {links}\n"
        f"- statements in the record: {said}\n"
        f"- relation types the recorder defined: {len(list((into / 'grown').glob('*.json')))}\n"
        f"- frozen: {datetime.now():%Y-%m-%d %H:%M}\n"
        f"- size: {(into / 'world.db').stat().st_size // 1024 // 1024} MB, most of it the "
        f"meaning index — the vectors a question searches by, which are derived and could be "
        f"rebuilt, at the cost of a model run.\n\n"
        f"Open it the way a run does — the base classes plus what this world grew:\n\n"
        f"```python\n"
        f"from terraweaver import growth, ontology as ont\n"
        f"from terraweaver.runtime import WorldRuntime\n"
        f"specs = growth.apply_growth(ont.base_specs(Path('ontology/core')),\n"
        f"                            growth.load_grown(Path('worlds/{name}/grown')))\n"
        f"rt = WorldRuntime('worlds/{name}/world.db', specs=specs, selves=True)\n"
        f"```\n\n"
        f"What it holds is what the recorder put there, right and wrong: "
        f"`experiments/check_expected.py worlds/{name}` reads it against what the facts owe.\n")
    print(f"frozen into {into}")
    print(f"  {entities} entities, {links} links, {said} statements, "
          f"{len(list((into / 'grown').glob('*.json')))} grown types")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
