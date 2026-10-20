"""FactConsolidation facts told through the proto door: what code does an agent write for them?

    .venv/bin/python experiments/05_proto_code/run.py                 # sh/6k, all 455 facts
    .venv/bin/python experiments/05_proto_code/run.py --batches 2     # the first 50

Haiku plays the host. Each batch of the benchmark's facts (25, as the world's runs took them)
comes to it as something the user said, with the skill's text (`proto/SKILL.md`), the variables
it has already made, and what the memory asked after its last run. Its answer is one `run` of
Python, executed in one session with `proto.server.run_code`, exactly as the MCP tool would.
Nothing is asked of the memory: this looks at the code and at the structure it leaves.

Writes experiments/results/05_proto_code/<stamp>/: batches.jsonl (facts, code, the run's
answer), facts.md and structure.jsonl (the memory), graph.json (things and what joins them).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "benchmarks")]

import factconsolidation as fc  # noqa: E402
from baseline import server as base  # noqa: E402
from proto import server  # noqa: E402
from proto.model import Structure, Thing  # noqa: E402

SKILL = (ROOT / "proto" / "SKILL.md").read_text().split("---", 2)[2].strip()

PROMPT = """You are the user's assistant, and the user's personal memory is connected to you. \
This is how it is used:

<skill>
{skill}
</skill>

Variables you have already made in this conversation (they still exist):
{variables}
{asked}
The user has just told you these facts:

{facts}

Record every one of them in the memory. Reply with only the Python code for one `run` call, in \
one ```python block."""


def haiku(prompt: str) -> tuple[str, float]:
    with tempfile.TemporaryDirectory() as where:
        out = subprocess.run(["claude", "-p", "--model", "haiku", "--output-format", "json", "--tools", "",
                              "--strict-mcp-config", "--setting-sources", ""],
                             input=prompt, cwd=where, capture_output=True, text=True, timeout=600)
    result = json.loads(out.stdout)
    return result.get("result") or "", result.get("total_cost_usd") or 0.0


def code_of(answer: str) -> str:
    blocks = re.findall(r"```(?:python)?\n(.*?)```", answer, re.S)
    return "\n".join(blocks) if blocks else answer


def variables(namespace: dict) -> str:
    things = [f"{name} = {value!r}" for name, value in namespace.items()
              if isinstance(value, Thing) and not name.startswith("_")]
    return "\n".join(things) or "(none yet)"


def graph(structure: Structure, held: dict[int, str]) -> dict:
    """Things as nodes; every entry about two or more things as edges between them."""
    nodes = {r["thing"]: {"id": r["thing"], "name": r["name"], "kind": r.get("kind"), "facts": []}
             for r in structure.records if "thing" in r}
    edges = []
    for r in structure.records:
        if "entry" not in r or r["entry"] not in held:
            continue
        text = held[r["entry"]].split(": ", 1)[-1]
        about = r["about"]
        for one in about:
            nodes[one]["facts"].append(text)
        for other in about[1:]:
            edges.append({"source": about[0], "target": other, "as": r.get("as"), "text": text,
                          "entry": r["entry"], "when": r.get("when")})
    for r in structure.records:
        for word in ("same", "different"):
            if word in r:
                edges.append({"source": r[word][0], "target": r[word][1], "as": word, "text": word})
    return {"nodes": list(nodes.values()), "edges": edges}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hops", default="sh")
    parser.add_argument("--context", default="6k")
    parser.add_argument("--batches", type=int, default=0, help="only the first N batches")
    args = parser.parse_args()

    variant = fc.load(args.hops, args.context)
    out = ROOT / "experiments" / "results" / "05_proto_code" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    base.facts = out / "facts.md"
    server.structure = Structure(out / "structure.jsonl", base._keep, server.held)
    session, asked, spent = "fc", "", 0.0
    batches = list(variant.batches())[:args.batches or None]
    for n, (day, facts) in enumerate(batches, 1):
        namespace = server.sessions.get(session, {})
        prompt = PROMPT.format(skill=SKILL, variables=variables(namespace), asked=asked,
                               facts="\n".join(f"- {f}" for f in facts))
        started = time.monotonic()
        answer, cost = haiku(prompt)
        spent += cost
        code = code_of(answer)
        said = server.run_code(code, session)
        asks = said.split("The memory asks:\n", 1)[1] if "The memory asks:" in said else ""
        asked = f"\nAfter your last run the memory asked:\n{asks}\n" if asks else ""
        kept = len(re.findall(r"#\d+", said.split("Kept: ", 1)[1].split("\n")[0])) if "Kept: " in said else 0
        print(f"batch {n}/{len(batches)}: {kept} kept of {len(facts)} facts, "
              f"{'ERROR ' if 'Error:' in said else ''}{time.monotonic() - started:.0f}s ${spent:.3f}", flush=True)
        with (out / "batches.jsonl").open("a") as file:
            file.write(json.dumps({"batch": n, "day": str(day), "facts": facts, "code": code,
                                   "answer": said, "cost": cost}, ensure_ascii=False) + "\n")
    (out / "graph.json").write_text(json.dumps(graph(server.structure, server.held()), ensure_ascii=False, indent=1))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
