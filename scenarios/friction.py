"""What the world makes hosts stumble on, counted across saved scenario runs.

Stability is the world's job, not the model's. Every run a host wastes — an attribute that isn't
there, a call shaped the way any reasonable person would shape it and the world refuses — is a
fork in the road: two runs of the same scenario diverge there and one of them ends somewhere
else. So the friction is counted, ranked, and worked off, and the count is the measure.

    .venv/bin/python scenarios/friction.py                 # every saved run
    .venv/bin/python scenarios/friction.py 20260920-13     # runs whose stamp starts with this
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "experiments" / "results" / "scenarios"


def results(prefix: str = "") -> list[Path]:
    return sorted(d for d in RESULTS.iterdir() if d.is_dir() and d.name.startswith(prefix))


def tool_results(transcript: Path):
    """Every result the world sent back in one scenario transcript."""
    for line in transcript.read_text().splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message")
        for item in (message.get("content") or []) if isinstance(message, dict) else []:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                content = item.get("content")
                text = content if isinstance(content, str) else "".join(
                    part.get("text", "") for part in content if isinstance(part, dict))
                if text:
                    yield text


def failure(text: str) -> str | None:
    """The error a run came back with, reduced to its shape so like ones count together."""
    if "[error" not in text:
        return None
    tail = text[text.index("[error"):]
    match = re.search(r"((?:[A-Za-z_.]+)?(?:Error|Violation|Exception|RunTimeout))\b:?\s*([^\\\"\n]{0,90})", tail)
    if not match:
        return "unknown"
    kind, detail = match.group(1).split(".")[-1], match.group(2).strip()
    detail = re.sub(r"'[^']{20,}'", "'…'", detail)
    detail = re.sub(r"\b[0-9a-f]{16,}\b", "<id>", detail)
    return f"{kind}: {detail}" if detail else kind


def main() -> int:
    prefix = sys.argv[1] if len(sys.argv) > 1 else ""
    dirs = results(prefix)
    if not dirs:
        print(f"no saved runs under {RESULTS}" + (f" starting {prefix}" if prefix else ""))
        return 1
    kinds: Counter = Counter()
    runs = failed = 0
    per_scenario: Counter = Counter()
    for directory in dirs:
        for transcript in sorted(directory.rglob("*.jsonl")):  # repeat runs keep each try in its own folder
            for text in tool_results(transcript):
                if "This is the user's personal world" in text[:300]:
                    continue  # the world description, not a run
                runs += 1
                shape = failure(text)
                if shape:
                    failed += 1
                    kinds[shape] += 1
                    per_scenario[transcript.name.split(".")[0]] += 1
    share = f"{failed / runs:.0%}" if runs else "—"
    print(f"{len(dirs)} saved run set(s), {runs} runs sent to the world, {failed} came back as errors ({share})\n")
    print("What hosts stumble on, most often first:")
    for shape, count in kinds.most_common(20):
        print(f"  {count:4}  {shape}")
    print("\nWhere it costs most:")
    for name, count in per_scenario.most_common(8):
        print(f"  {count:4}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
