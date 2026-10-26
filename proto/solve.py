"""The world solves a task with a program: its model writes it once, whole, and it runs.

    .venv/bin/python -m proto.solve "Pick me a robot vacuum" --memory pick-20261026-154726
    .venv/bin/python -m proto.solve "Who are my colleagues?" --memory main --engine keenable

Nothing here knows any task. The model is told the tools and the task, and writes the program:
whether it searches, what it gathers, which values it wants, what it calls a hard condition, and
what to do when too little is found — as branches in the code, not as turns of a conversation.
Calls to a model are steps of the program (`parse`, `check`, `decide`), like any function.

Not an agent's loop: the program is written before it runs and runs to its end. Only a program
that fails — an exception — goes back to the model with the error, to be fixed (twice at most).
The program is kept with the run (program.py), so it can be read, rerun, and reused for a task
of the same kind.
"""
import argparse
import contextlib
import io
import json
import re
import traceback
from datetime import datetime
from pathlib import Path

from proto.models import role
from proto.programs import Programs
from proto.tools import Shelf, Tools

ROOT = Path(__file__).resolve().parents[1]

SYSTEM = """You are the world: the user's memory, which solves tasks the user's agent brings. \
You solve a task by writing one Python program, in one ```python block, that solves it from start \
to end without you: it runs once, unattended, and ends with reply_to_agent(...). Write the decisions \
the task needs into the code — what to gather, what counts, what to do when too little passes (a \
branch: gather more, or relax a condition) — and print each step's counts briefly. The program \
begins with a docstring: its first line is the kind of task it solves, in general words — no name, \
thing or number of this user's — and the lines after say what it takes from the memory and how it \
solves it. It is kept, and reused for the next task of the same kind.

What the user's memory holds about the task is given with it, sorted: the limits the user \
stated go into must_hold, every one of them, and nothing else does; wishes are conditions to rank \
by. A limit is written as the user put it — "under 400" is value <= 400, "between 200 and 500" is \
200 <= value <= 500. None of it goes into a web query: \
queries name kinds of thing, the market (country, language, currency) and the date. A choice \
among candidates needs many: gather widely (ten or more queries) before ranking. Some tasks need \
no web at all — the user's memory answers them. Never name in the reply anything the program did \
not gather or find in the memory; if nothing fits, say so and what came closest.

The objects your program has (already defined; import nothing but Python's standard library):
{manual}

Classes (what holds for every item of a class, whatever the task):
{classes}

An example, for another task — a light laptop for a student:
```python
\"\"\"Pick one product for the user from the web, within the limits they stated.

Gathers candidates from many queries, ranks them by the user's limits (must hold) and wishes,
and chooses one among the best; says so when nothing known meets the limits.
\"\"\"
limits = user_memory.answer_question("What limits or wishes bear on buying a laptop?")
print(limits)
laptops = new_collection("laptops", of_class="product")
fields = {"weight_kg": "weight in kg", "battery_hours": "battery life in hours"}
for query in ["student laptop test 2026", "Laptop Studium Test 2026", "leichter Laptop unter 800 Euro",
              "best ultrabook 2026 Germany", "Notebook Akkulaufzeit Test 2026"]:
    print(query, laptops.add_from_texts(web.search_pages(query, how_many=5), fields=fields))
conditions = {
    "affordable": lambda i: i.value_of("price_eur") <= 800,
    "light": lambda i: i.value_of("weight_kg") <= 1.5,
    "long battery": lambda i: i.value_of("battery_hours") >= 10,
}
ranking = laptops.all_items().rank_by(conditions, must_hold=["affordable"], keep_top=10)
print(ranking)
if not ranking:
    reply_to_agent("No laptop in what I gathered is known to cost under 800 euros.")
else:
    reply_to_agent(ranking.choose_one_for("a light laptop for a student, under 800 euros"))
```"""


LIMITS = """Facts from the user's memory:
{entries}

The user's agent brings this task: {task}

Sort what the facts say that bears on the task. A limit is only what the user stated as one — a \
budget ("has to stay under 400 euros", "between 200 and 500"), a refusal ("I don't want …"), a \
must ("it has to …"). Everything else that bears on it — needs, circumstances, likes — is a wish, \
even when it matters a lot. Answer with JSON only:
{{"limits": [{{"limit": "the limit, as a condition on the thing", "quote": "the fact's words"}}],
 "wishes": [{{"wish": "what would make the thing fit better", "quote": "the fact's words"}}],
 "context": "anything else the task needs to know, in a sentence or two"}}"""


def run(task: str, memory: str, engine: str, fixes: int, out: Path) -> str:
    tools = Tools(Shelf(ROOT / "var" / "proto" / memory), out, engine=engine)
    writer, programmer = role("reader"), role("programmer")
    entries = "\n".join(f"- {e}" for e in list(tools.memory.journal.entries.values())[-300:])
    tools._recall = lambda q: writer.say(
        "Answer from the facts only; say when they don't say.",
        f"Facts from the user's memory:\n{entries}\n\nQuestion: {q}", room=2000, thinking=False)
    namespace = tools.namespace()
    # What the memory holds for the task comes first, by a fixed step, so the program is written
    # knowing it. Written blind, it recalled the user's limits at run time and never used them:
    # a 450-dollar pick for a 400-euro budget (2026-10-26). And split: only what the user stated
    # as a limit is one. Left to the program, which conditions must hold changed from run to run.
    said = programmer.say("Answer from the facts only, in the form asked.", LIMITS.format(
        entries=entries, task=task), room=3000, thinking=False)
    try:
        sorted_ = json.loads(said[said.find("{"):said.rfind("}") + 1])
    except ValueError:
        sorted_ = {"limits": [], "wishes": [], "context": said}
    known = ("Limits the user stated — each one is a must_hold condition in your code:\n" +
             ("\n".join(f"- {l.get('limit')} (the user: \"{l.get('quote')}\")" for l in sorted_.get("limits") or [])
              or "- none") +
             "\n\nWishes and circumstances — conditions to rank by, not must_hold:\n" +
             ("\n".join(f"- {w.get('wish')} (from: \"{w.get('quote')}\")" for w in sorted_.get("wishes") or [])
              or "- none") +
             (f"\n\nOther things known: {sorted_['context']}" if sorted_.get("context") else "") +
             # What the store holds, so the program reads what is there: told nothing, it read
             # people's "employer" value where the memory holds a works_at link (2026-10-26).
             "\n\nWhat the user's memory holds as structure:\n" + tools.namespace()["user_memory"].describe())
    from proto.tools import CLASSES
    classes = "\n".join(f"  {k}: {c['about']}; fields {list(c['fields'])}; required {c['required']} — {c['why']}"
                        for k, c in CLASSES.items())
    # A program kept for a task of the same kind is where the writing starts: written from
    # nothing, the same task got a different program, and answer, every run (2026-10-26).
    programs = Programs()
    based_on = programs.find(task, role("judge"))
    kept = (f"\n\nA program kept for a task of the same kind. Start from it: keep what worked, change what "
            f"this task and these limits need, and keep its docstring true:\n```python\n{programs.text(based_on)}```"
            if based_on else "")
    print(f"--- kept program: {based_on or 'none, a new kind of task'}")
    messages = [{"role": "system", "content": SYSTEM.replace("{classes}", classes).replace("{manual}", tools.manual())},
                {"role": "user", "content": f"Today is {namespace['today']}. The agent brings this task:\n\n{task}"
                                            f"\n\nWhat the user's memory holds that bears on it:\n{known}{kept}"}]
    log = []
    for attempt in range(1, fixes + 2):
        # The reply is begun for the model, as a program: it continues the code instead of
        # writing about it. With thinking on, a third of replies held no program at all, and the
        # endpoint continues a begun reply only with thinking off (2026-10-26).
        # Begun with the docstring, so every program says what it solves: the registry's description.
        begun = '```python\n"""'
        reply = begun + (programmer.client.chat.completions.create(
            model=programmer.model, temperature=0, max_tokens=16000,
            messages=messages + [{"role": "assistant", "content": begun}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False},
                        "continue_final_message": True, "add_generation_prompt": False}
        ).choices[0].message.content or "")
        program = reply[len("```python\n"):].split("```", 1)[0]
        if program.strip() == '"""':
            program = ""
        (out / "program.py").write_text(program)
        printed, failed = io.StringIO(), None
        try:
            compiled = compile(program, "program.py", "exec")
        except SyntaxError as e:
            compiled, failed = None, f"SyntaxError at line {e.lineno}: {e.msg}\n{(e.text or '').rstrip()}"
        with contextlib.redirect_stdout(printed):
            try:
                if compiled:
                    exec(compiled, dict(namespace))  # noqa: S102 - the world's own program, over its own tools
            except Exception:  # noqa: BLE001 - a failed program goes back to be fixed
                failed = traceback.format_exc(limit=3)[-2000:]
                if "NameError" in failed or "ModuleNotFoundError" in failed:
                    failed += ("\nThe program has these names and no others: user_memory, web, "
                               "new_collection, reply_to_agent, today, Items, and Python's standard library.")
        if not program.strip():
            failed = ("The reply had no program. Answer with the whole program in one ```python block.")
        elif not failed and not tools.answered:
            # Written as a first look rather than a whole solution, as an agent would: it ran,
            # printed, and stopped. That is a program unfinished, and goes back like a failed one.
            failed = ("The program ended without calling reply_to_agent(...). It runs once, unattended: it must "
                      "do everything from gathering to the answer, and end with reply_to_agent(...).")
        seen = printed.getvalue()[-6000:]
        log.append({"attempt": attempt, "program": program, "printed": seen, "failed": failed})
        print(f"\n--- program, attempt {attempt}\n{program}\n>>> {seen}{failed or ''}")
        if tools.answered or not failed:
            break
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": f"The program failed:\n{failed}\nIt printed:\n{seen[-2000:]}\n"
                                                 f"Write the whole program again, fixed."}]
    name = programs.keep(log[-1]["program"], task, bool(tools.answered), based_on)
    print(f"--- kept as: {name or 'not kept'}")
    (out / "solve.json").write_text(json.dumps({"task": task, "memory": memory, "engine": engine, "based_on": based_on,
                                                "kept_as": name, "attempts": log, "answer": tools.answered},
                                               indent=1, ensure_ascii=False))
    return tools.answered or "(the program gave no answer)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("task")
    parser.add_argument("--memory", default="main", help="var/proto/<name>: the user's memory")
    parser.add_argument("--engine", default="tavily")
    parser.add_argument("--fixes", type=int, default=2, help="times a failed program goes back to be fixed")
    parser.add_argument("--out", type=Path, help="where the run goes (program.py, solve.json)")
    args = parser.parse_args()
    out = args.out or ROOT / "var" / "solve" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    print("\nANSWER:\n" + run(args.task, args.memory, args.engine, args.fixes, out))
    print(out)


if __name__ == "__main__":
    main()
