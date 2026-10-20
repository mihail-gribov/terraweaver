"""A MemOps conversation told through the proto door, then its questions asked of what was kept.

    .venv/bin/python experiments/06_memops/run.py                     # B01_update
    .venv/bin/python experiments/06_memops/run.py --sample A01_update
    .venv/bin/python experiments/06_memops/run.py --answer <results dir>   # only ask again

Haiku plays the host. Each user turn comes to it with the conversation before it, the date (a
week a segment: MemOps gives none), the skill (`proto/SKILL.md`), its variables and what the
memory asked; it answers with the code of one `run`, or with nothing to keep. The turn itself is
heard first (`Structure.heard`), as the world would hear it through `context`.

Then every probe question is asked twice and judged by Sonnet against MemOps's rubric:
- **things** — the texts of every entry about the things the question names, dated;
- **all** — every text in the journal, dated: the baseline's image.

Writes experiments/results/06_memops/<sample>-<stamp>/: turns.jsonl, facts.md, heard.md,
structure.jsonl, graph.json, answers.json.
"""
import argparse
import asyncio
import concurrent.futures
import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from baseline import server as base  # noqa: E402
from proto import server  # noqa: E402
from proto.model import Structure  # noqa: E402

_spec = importlib.util.spec_from_file_location("proto_run", ROOT / "experiments" / "05_proto_code" / "run.py")
p05 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p05)

DATA = ROOT / "data" / "memops" / "raw" / "generated_result" / "2-evidence_conversation"
# The host's own clock is the real one (`claude -p` tells the model today's date), so a replay in
# April, as first written, had the host write "As of 2026-10-15" into a fact told "on April 15".
# By default the conversation is set to end today: a week a segment, back from now. But its
# own dates are spring 2025 ("Saturday, May 10th"), and told in October those plans read as past,
# so `--start 2025-04-07` dates it in its own time, the host's "Now:" carrying it.
START = None

HOST = """You are the user's assistant, and the user's personal memory is connected to you. \
This is how it is used:

<skill>
{skill}
</skill>

Now: {now}.

Variables you have already made in this conversation (they still exist):
{variables}
{asked}
The conversation so far:
{history}

The user has just written:

<message>
{message}
</message>

Before you answer the user, keep in the memory whatever this message says about the user's life. \
Reply with only the Python code for one `run` call, in one ```python block, and pass `now` by \
writing it on the block's first line as a comment: `# now: <date and time>`. If the message says \
nothing worth keeping, reply with an empty block.

If the user asks for something to be forgotten or removed, that is the memory's `forget` tool: \
put what to forget, in words, in a ```forget block after the python one; it runs after your code. \
The memory keeps the request itself, dated, in those words, so name what to forget by what it is \
("the storage unit move with Darren"), not by the detail to be dropped. \
Whatever of it should still be kept (that something changed, why), keep with your code."""

FOLLOW = """You ran this against the user's memory:

```python
{code}
```

The memory answered:

{said}

If its questions show something the user said that you did not keep, keep it now: reply with \
the Python code for one more `run`, in one ```python block, with the same `# now:` line. If \
nothing needs keeping, reply with an empty block."""

ANSWER = """Below is what the memory holds, numbered in the order it was told, each with the date \
it was told. When two entries disagree, the one with the larger number is newer.

{memory}

Now: {now}.

The user asks: {question}

Answer the user from the memory, briefly, as their assistant would."""

JUDGE = """A memory system was asked a question about the user's life.

Question: {question}

Expected answer: {expected}

The answer must include (or say in other words): {must}
It must not: {must_not}

The system answered: {answer}

Does the answer include each of the required points, and nothing it must not? Extra caveats, \
extra detail and different wording do not matter. Reply with one word: yes or no."""


def rubric(a: dict) -> dict:
    """MemOps's own rubric for the question, as the judge's two lists."""
    r = a.get("judge_rubric") or {}
    return {"must": "; ".join(r.get("must_include") or []) or "the key facts of the expected answer",
            "must_not": "; ".join((r.get("must_not_include") or []) + (r.get("harmful_extra") or [])) or "(nothing listed)"}


def history_of(turns: list[dict], upto: int, keep: int = 6) -> str:
    lines = [f"{t['role']}: {t['content']}" for t in turns[max(0, upto - keep):upto]]
    return "\n\n".join(lines) or "(this is the first message)"


def judge(prompt: str) -> str:
    """The verdict, from Sonnet: Haiku as judge passed and failed the same "$148K a year"."""
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as where:
        out = subprocess.run(["claude", "-p", "--model", "sonnet", "--output-format", "json", "--tools", "",
                              "--strict-mcp-config", "--setting-sources", ""],
                             input=prompt, cwd=where, capture_output=True, text=True, timeout=600)
    return json.loads(out.stdout).get("result") or ""


def tell(sample: dict, out: Path) -> None:
    session, asked, spent = "memops", "", 0.0
    turns = []
    for seg in sample["conversations"]:
        for t in seg["dialogue"]:
            turns.append({**t, "segment": seg["segment_index"]})
    for i, turn in enumerate(turns):
        if turn["role"] != "user":
            continue
        last = max(seg["segment_index"] for seg in sample["conversations"])
        start = START or (datetime.now() - timedelta(days=7 * (last - 1))).replace(hour=9, minute=0, second=0, microsecond=0)
        now = start + timedelta(days=7 * (turn["segment"] - 1), minutes=5 * i)
        server.structure.now[session] = now
        server.structure.heard(session, turn["content"], "conversation")
        prompt = HOST.format(skill=p05.SKILL, now=f"{now:%Y-%m-%d %H:%M} ({now:%A})",
                             variables=p05.variables(server.sessions.get(session, {})), asked=asked,
                             history=history_of(turns, i), message=turn["content"])
        answer, cost = p05.haiku(prompt)
        spent += cost
        # A forget block is the host calling the `forget` tool beside `run`.
        forgets = re.findall(r"```forget\n(.*?)```", answer, re.S)
        code = p05.code_of(re.sub(r"```forget\n.*?```", "", answer, flags=re.S))
        given = re.search(r"#\s*now:\s*(\S+(?:[ T]\d\d:\d\d)?)", code)
        said = server.run_code(code, session, given.group(1).replace(" ", "T") if given else None)
        asks = said.split("The memory asks:\n", 1)[1] if "The memory asks:" in said else ""
        if asks:
            # As a host would: it reads the tool's answer and may run once more before replying.
            again, cost = p05.haiku(FOLLOW.format(code=code, said=said))
            spent += cost
            code2 = p05.code_of(again)
            if code2.strip():
                said2 = server.run_code(code2, session, given.group(1).replace(" ", "T") if given else None)
                code, said = f"{code}\n# --- follow-up run ---\n{code2}", f"{said}\n--- follow-up ---\n{said2}"
                asks = said2.split("The memory asks:\n", 1)[1] if "The memory asks:" in said2 else ""
        for what in forgets:
            gone = asyncio.run(base.forget(what.strip(), given.group(1).replace(" ", "T") if given else None))
            said = f"{said}\n--- forget {what.strip()!r} ---\n{gone}"
            code = f"{code}\n# --- forget ---\n# {what.strip()}"
        asked = f"\nAfter your last run the memory asked:\n{asks}\n" if asks else ""
        print(f"turn {i} (segment {turn['segment']}): now={'given' if given else 'MISSING'} "
              f"{'ERROR ' if 'Error:' in said else ''}{said.split(chr(10))[0][:120]}  ${spent:.3f}", flush=True)
        with (out / "turns.jsonl").open("a") as file:
            file.write(json.dumps({"turn": i, "segment": turn["segment"], "message": turn["content"],
                                   "code": code, "answer": said, "cost": cost}, ensure_ascii=False) + "\n")
    held = server.held()
    (out / "graph.json").write_text(json.dumps(p05.graph(server.structure, held), ensure_ascii=False, indent=1))


def dated(numbers: list[int]) -> str:
    entries = {n: (heading, text) for n, heading, text in base._entries(base._memory())}
    lines = []
    for n in numbers:
        heading, text = entries[n]
        told = heading.split(" · ")[1][:10]
        lines.append(f"{n}. ({told}) {' '.join(text.split())}")
    return "\n".join(lines)


def named_in(question: str, things: list[dict]) -> list[dict]:
    """The things the question names: by the whole name, or by one of its words of four letters
    or more written with a capital ("Darren" for Darren Liu)."""
    said = question.lower()
    words = {re.sub(r"'s$", "", w) for w in re.findall(r"\b[A-Z][\w'-]{3,}", question)}
    out = []
    for t in things:
        name = t["name"]
        if re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", said) or \
                any(w in words for w in re.findall(r"[\w'-]{4,}", name)):
            out.append(t)
    return out


def ask(out: Path) -> None:
    sample = json.loads((out / "sample.json").read_text())
    things = [r for r in server.structure.records if "thing" in r]
    every = sorted(base._entries(base._memory()) and [n for n, _, _ in base._entries(base._memory())])
    seen, rows = set(), []
    # The question is asked when the conversation ends: now is the last thing told's date, as
    # the host would pass it — not this clock's, which is months after the conversation.
    last = max(n for n, _, _ in base._entries(base._memory()))
    now = next(h for n, h, _ in base._entries(base._memory()) if n == last).split(" · ")[1]
    questions = []
    for a in sample["answer"]:
        if a["question"] not in seen:
            seen.add(a["question"])
            questions.append(a)

    def one(a):
        # A disambiguation question is asked with its options, as MemOps asks it.
        if a.get("candidate_options"):
            a = {**a, "question": a["question"] + "\nOptions:\n" + "\n".join(f"- {o}" for o in a["candidate_options"])}
        found = named_in(a["question"], things)
        numbers = sorted({int(e.split(" · ")[0][3:]) for t in found
                          for e in server.structure.about(server.structure.thing("q", t["thing"]))})
        row = {"question": a["question"], "type": a["evaluation_type"], "expected": a["expected_answer"],
               "named": [t["name"] for t in found], "shown": len(numbers)}
        for image, picked in (("things", numbers), ("all", every)):
            said, _ = p05.haiku(ANSWER.format(memory=dated(picked) or "(nothing)", now=now, question=a["question"]))
            verdict = judge(JUDGE.format(question=a["question"], expected=a["expected_answer"], answer=said, **rubric(a)))
            row[image] = {"answer": said, "right": verdict.strip().lower().startswith("yes")}
        return row

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        rows = list(pool.map(one, questions))
    for r in rows:
        print(f"[{r['type']}] named={r['named']} shown={r['shown']}")
        print(f"  Q: {r['question'][:160]}")
        print(f"  expected: {r['expected'][:160]}")
        for image in ("things", "all"):
            print(f"  {image:6} {'RIGHT' if r[image]['right'] else 'WRONG'}: {r[image]['answer'][:300]!r}")
    print(f"things {sum(r['things']['right'] for r in rows)}/{len(rows)}, "
          f"all {sum(r['all']['right'] for r in rows)}/{len(rows)}, journal {len(every)} entries")
    (out / "answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", default="B01_update")
    parser.add_argument("--start", type=datetime.fromisoformat,
                        help="the first segment's date (MemOps's own dates are in spring 2025); "
                             "by default the conversation ends today")
    parser.add_argument("--answer", type=Path, help="a results dir: only ask its questions again")
    args = parser.parse_args()
    global START
    START = args.start

    if args.answer:
        out = args.answer
    else:
        out = ROOT / "experiments" / "results" / "06_memops" / f"{args.sample}-{datetime.now():%Y%m%d-%H%M%S}"
        out.mkdir(parents=True)
        (out / "sample.json").write_text((DATA / f"{args.sample}.json").read_text())
    base.facts = out / "facts.md"
    server.structure = Structure(out / "structure.jsonl", base._keep, server.held)
    if not args.answer:
        tell(json.loads((out / "sample.json").read_text()), out)
    ask(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
