"""The structure a proto run left, as one self-contained page: the graph, the words, the code.

    .venv/bin/python experiments/05_proto_code/graph.py experiments/results/05_proto_code/<stamp>

Writes graph.html beside the run's files. The data goes into the page inline; the page loads
d3 from cdnjs and nothing else.
"""
import json
import sys
from collections import Counter
from pathlib import Path

PAGE = Path(__file__).with_name("graph.html")


def main() -> int:
    run = Path(sys.argv[1])
    graph = json.loads((run / "graph.json").read_text())
    batches = [json.loads(line) for line in (run / "batches.jsonl").read_text().splitlines()]
    asked = sum(b["answer"].count("\n- Is ") for b in batches)
    unnamed = sum(b["answer"].count("does not name") for b in batches)
    stats = {
        "facts": sum(len(b["facts"]) for b in batches),
        "kept": sum(1 for line in (run / "facts.md").read_text().splitlines() if line.startswith("## #")),
        "things": len(graph["nodes"]),
        "kinds": Counter(n["kind"] or "—" for n in graph["nodes"]).most_common(),
        "words": Counter(e["as"] or "—" for e in graph["edges"] if e["as"] not in ("same", "different")).most_common(),
        "asked": asked, "unnamed": unnamed,
        "errors": sum("Error:" in b["answer"] for b in batches),
        "cost": round(sum(b.get("cost", 0) for b in batches), 3),
        "run": run.name,
    }
    data = {"graph": graph, "stats": stats,
            "batches": [{"batch": b["batch"], "code": b["code"], "answer": b["answer"]} for b in batches]}
    html = PAGE.read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    (run / "graph.html").write_text(html)
    print(run / "graph.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
