"""Experiment 02 — literate dialogue.

The agent doesn't answer the user directly; it writes a *template* of the answer.
A message may carry two kinds of live material:

    ```python
    contacts = world.all(Person)
    ```
    You have {{ len(contacts) }} contacts; the latest is {{ contacts[-1].full_name }}.

The orchestrator runs the code, evaluates the `{{ ... }}` expressions and substitutes
their values, and only the rendered prose reaches the user. The point is that the agent
never states a figure it made up: every number in the delivered text came out of an
executed expression over the real world.

Two rules make the loop work:

- A message that is *only* code, with no prose, is a working step — like a notebook cell
  without narrative. Its stdout goes back to the agent and nothing goes to the user. That's
  how the agent explores the world (`classes()`, `describe("Person")`) before composing.
- Line numbers are the message's own. Code is placed into the executed script at exactly
  the line it occupies in the message, so a traceback's line number *is* the message's line
  number — an error can be pointed at without any remapping. Since only the previous
  message is ever under discussion, the numbering can't drift.

Variables persist for the whole dialogue.
"""
import ast
import contextlib
import io
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from terraweaver import resolution
from terraweaver.llm import DEFAULT_MODEL, client
from terraweaver.ontology import COMMON_MEMBERS, Entity, describe_for_prompt
from terraweaver.resolution import NeedsResolution
from terraweaver.session import Session
from terraweaver.world import describe_world_api

MAX_ROUNDS = 8

EXPR_RE = re.compile(r"\{\{(.+?)\}\}", re.DOTALL)
# Reasoning models wrap their thinking in <think>...</think>. It is not part of the message,
# and a stray closing tag once reached the user verbatim — strip it before anything else.
THINK_RE = re.compile(r"<think>.*?</think>|<think>.*|</think>", re.DOTALL | re.IGNORECASE)

SYSTEM_PROMPT = """\
You are the user's personal assistant — you are `me`, and the person you're talking to
is `owner`. You know their world — the people, companies, events
and facts they've told you about — and you can work with it not only in words, but in code.

You have three things you can do.

1. SAY SOMETHING, WITH REAL VALUES IN IT. Your message is a template: write the prose, and
   put an inline expression in double braces wherever a value belongs. The expression is
   evaluated and replaced before the user sees the text.

   ```python
   contacts = world.all(Person)
   ```
   You have {{ len(contacts) }} contacts; the latest is {{ contacts[-1].full_name }}.

   The user reads only: "You have 3 contacts; the latest is Barbara Liskov."
   Write the prose without knowing the values. Never guess a number or a name and never
   leave a placeholder — put the expression there and the real value will be filled in.

2. JUST RUN SOME CODE. Send a message that is only a ```python block``` and no prose. It
   runs, its output comes back to you, and the user sees nothing. A trailing bare expression
   is echoed back, as in a notebook. Use this whenever you need to act rather than speak —
   creating an entity, recording a fact, changing something. The habit worth keeping: run the
   code, then check that the operation actually took effect, and only then tell the user it's
   done. Don't report success you haven't verified.

3. STUDY THE WORLD MODEL. Inside code you have two tools:
   - classes() — the list of classes with a one-line description of each;
   - describe("Person", "Vacancy") — the full attributes and methods of those classes.
   Use them when you're not sure what a class holds, instead of assuming.

The user must never learn that any of this exists. They see a person who knows their life,
not a system running queries. So in the prose you write for them:
- never mention code, variables, classes, fields, queries, a database or "the system";
- don't retell what you did technically — say in plain words what came of it;
- don't show internal names (full_name, not_applied, Vacancy) — use ordinary words.
Everything technical stays on your side of the line.

Also worth knowing:
- Variables persist for the whole conversation. Build on what you already defined.
- If your code fails, you get your own message back with numbered lines and the line that
  broke. Fix it and resend the whole message.
- Answer in the language the user wrote in.
{world_section}
{common_members}
Available classes:
{catalog}
{variables}"""


@dataclass
class AgentResult:
    success: bool
    message: str
    task_id: str = ""
    status: str = ""
    code: str | None = None
    stdout: str | None = None  # the rendered message the user received
    value: Any = None  # same rendered message, as the delivered answer
    error: str | None = None
    transcript: list[dict] = field(default_factory=list)
    rounds: int = 0
    namespace: dict | None = None
    resolutions: list[dict] = field(default_factory=list)
    objects: dict = field(default_factory=dict)
    variables: dict = field(default_factory=dict)


def _numbered(message: str) -> str:
    return "\n".join(f"{i:>3} | {line}" for i, line in enumerate(message.splitlines(), start=1))


def _split_message(message: str) -> tuple[str, str]:
    """Split a message into (script, prose) in a single pass.

    Deliberately one scan rather than a scan for code and a regex for prose: two parsers
    disagreeing about where a fence ends is how raw ``` and a stray "python" ended up in
    text delivered to the user.

    The script is blank-padded so each code line sits at its line number in the message —
    a traceback's `lineno` is then the number the agent sees, with no remapping.
    """
    lines = message.splitlines()
    script = [""] * len(lines)
    prose: list[str] = []
    inside = False
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if inside:
            script[index] = line
        else:
            prose.append(line)
    return "\n".join(script), "\n".join(prose).strip()


def _ungrounded(prose: str, ran_anything: bool) -> str | None:
    """Why this message may not be delivered as an answer, if it may not.

    The promise of this design is that nothing the user reads was made up. That only holds
    if it's enforced: a figure typed straight into the prose, or an answer produced without
    ever consulting the world, is exactly the fabrication the expressions exist to prevent.
    """
    without_expressions = EXPR_RE.sub("", prose)
    if re.search(r"\d", without_expressions):
        return (
            "there are digits in your text that didn't come from an expression. Every figure "
            "the user reads must be computed — put the expression in the text instead of the number"
        )
    if not ran_anything:
        return (
            "you answered without looking at the world at all. Check first — run the code you "
            "need, then say what you found"
        )
    return None


def _render(prose: str, namespace: dict) -> tuple[str, str | None]:
    """Substitute {{ expressions }}. Returns (rendered, error)."""
    failure: str | None = None

    def substitute(match):
        nonlocal failure
        expression = match.group(1).strip()
        try:
            return str(eval(expression, namespace))  # noqa: S307 - evaluating the agent's own expression
        except Exception as exc:  # noqa: BLE001
            if failure is None:
                failure = f"expression {{{{ {expression} }}}} failed: {type(exc).__name__}: {exc}"
            return match.group(0)

    rendered = EXPR_RE.sub(substitute, prose)
    return rendered, failure


def _run(script: str, namespace: dict) -> tuple[str, str | None, int | None]:
    """Execute the message's code. Returns (stdout, error, failing line number).

    A trailing bare expression is echoed, the way a notebook cell does. Without that,
    `describe("Person")` on its own line produces nothing — exec() discards the value —
    and the agent, quite reasonably, keeps retrying the same look-up.
    """
    stdout = io.StringIO()
    try:
        tree = ast.parse(script, filename="<message>")
        trailing = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            trailing = ast.Expression(tree.body.pop().value)
        with contextlib.redirect_stdout(stdout):
            exec(compile(tree, "<message>", "exec"), namespace)
            if trailing is not None:
                value = eval(compile(ast.fix_missing_locations(trailing), "<message>", "eval"), namespace)
                if value is not None:
                    print(value)
    except SyntaxError as exc:
        return stdout.getvalue(), f"SyntaxError: {exc.msg}", exc.lineno
    except Exception as exc:  # noqa: BLE001 - the error is the product here
        traceback = exc.__traceback__
        lineno = None
        while traceback is not None:
            if traceback.tb_frame.f_code.co_filename == "<message>":
                lineno = traceback.tb_lineno
            traceback = traceback.tb_next
        return stdout.getvalue(), f"{type(exc).__name__}: {exc}", lineno
    return stdout.getvalue(), None, None


def _persist_world(namespace: dict[str, Any], classes: dict[str, type], store) -> None:
    seen: set[int] = set()
    # One script's changes form one subgraph: they are stored together or not at all.
    with store.transaction():
        for key, value in list(namespace.items()):
            if key.startswith("__"):
                continue
            if isinstance(value, dict):
                candidates = list(value.values())
            elif isinstance(value, (list, tuple, set)):
                candidates = list(value)
            else:
                candidates = [value]
            for item in candidates:
                if isinstance(item, Entity):
                    store.save_graph(item, seen)


def _exploration_tools(specs: dict) -> dict:
    def classes_tool() -> str:
        return "\n".join(f"- {name}: {spec.get('description', '')}" for name, spec in specs.items())

    def describe_tool(*names: str) -> str:
        wanted = {n: specs[n] for n in names if n in specs}
        missing = [n for n in names if n not in specs]
        text = describe_for_prompt(wanted) if wanted else ""
        if missing:
            text += f"\nNo such class: {', '.join(missing)}"
        return text or "No matching classes."

    return {"classes": classes_tool, "describe": describe_tool}


def solve(
    task: str,
    specs: dict[str, dict[str, Any]],
    classes: dict[str, type],
    model: str = DEFAULT_MODEL,
    seed: dict[str, Any] | None = None,
    store=None,
    world=None,
    ask_user: Callable[[str, list[str]], int | None] | None = None,
    task_id: str | None = None,
    session: Session | None = None,
) -> AgentResult:
    seed = seed or {}
    task_id = task_id or uuid.uuid4().hex[:8]
    llm = client()
    transcript: list[dict] = []
    rounds = 0

    if session is None:
        session = Session(classes, seed=seed, world=world)
    namespace = session.namespace
    namespace.update(_exploration_tools(specs))
    namespace.setdefault("datetime", datetime)
    namespace.setdefault("timedelta", timedelta)
    if world is not None:
        namespace["world"] = world
        namespace["NeedsResolution"] = NeedsResolution

        def run_skill(needs: NeedsResolution):
            kind = resolution.SKILL_KINDS.get(needs.skill, needs.skill)

            def asking(question: str, options: list[str]) -> int | None:
                note("assistant", f"[{kind}] {question} {options}", f"{kind}:question")
                choice = ask_user(question, options) if ask_user else None
                settled = choice is not None and 0 <= choice < len(options)
                note("user", f"[{kind}] {options[choice] if settled else '(not settled)'}", f"{kind}:answer")
                status = resolution.RESOLVED if settled else resolution.UNRESOLVED
                note("system", f"[{kind}] {status}", f"{kind}:{status}")
                return choice

            return resolution.run_skill(needs, asking, world)

        namespace["run_skill"] = run_skill

    def note(role: str, content: str, kind: str) -> None:
        transcript.append({"task_id": task_id, "seq": len(transcript), "role": role, "kind": kind, "content": content})

    system = SYSTEM_PROMPT.format(
        common_members=COMMON_MEMBERS,
        variables=session.describe_for_prompt(),
        catalog="\n".join(f"- {name}: {spec.get('description', '')}" for name, spec in specs.items()),
        world_section=describe_world_api() if world is not None else "",
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    note("system", system, "system")
    note("user", task, "task")
    scripts: list[str] = []

    def finish(**kwargs) -> AgentResult:
        if store is not None:
            _persist_world(namespace, classes, store)
        session.sync()
        status = resolution.RESOLVED if kwargs.get("success") else resolution.UNRESOLVED
        note("system", f"[task] {status}: {kwargs.get('message', '')}", f"task:{status}")
        return AgentResult(
            task_id=task_id,
            status=status,
            transcript=transcript,
            namespace=namespace,
            resolutions=list(world.resolutions) if world is not None else [],
            variables=dict(session.variables),
            code="\n\n".join(scripts) or None,
            rounds=rounds,
            **kwargs,
        )

    for _ in range(MAX_ROUNDS):
        response = llm.chat.completions.create(model=model, messages=messages)
        rounds += 1
        reply = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": reply})
        note("assistant", reply, "message")

        reply = THINK_RE.sub("", reply).strip()
        script, prose = _split_message(reply)
        if script.strip():
            scripts.append(script)
        out, error, lineno = _run(script, namespace)
        session.sync()

        if error:
            where = f"line {lineno}" if lineno else "somewhere in the code"
            feedback = (
                f"Your message failed at {where}:\n{error}\n\n"
                f"Your message with line numbers:\n{_numbered(reply)}\n\n"
                "Variables defined before the failure are still there. Resend the whole message, fixed."
            )
            messages.append({"role": "user", "content": feedback})
            note("user", feedback, "error")
            continue

        if not prose:
            # A code-only message is a working step: its output is for the agent, not the user.
            feedback = f"Output:\n{out or '(no output)'}\n\nContinue — write the message for the user."
            messages.append({"role": "user", "content": feedback})
            note("user", feedback, "step_output")
            continue

        blocked = _ungrounded(prose, ran_anything=bool(scripts))
        if blocked:
            feedback = (
                f"Not sent to the user: {blocked}.\n\n"
                f"Your message with line numbers:\n{_numbered(reply)}\n\n"
                "Resend the whole message."
            )
            messages.append({"role": "user", "content": feedback})
            note("user", feedback, "ungrounded")
            continue

        rendered, render_error = _render(prose, namespace)
        if render_error:
            feedback = (
                f"Your message ran, but {render_error}\n\n"
                f"Your message with line numbers:\n{_numbered(reply)}\n\n"
                "Resend the whole message with that expression fixed."
            )
            messages.append({"role": "user", "content": feedback})
            note("user", feedback, "render_error")
            continue

        note("assistant", rendered, "delivered")
        return finish(success=True, message="Delivered.", stdout=rendered, value=rendered)

    return finish(success=False, message="Agent never produced a deliverable message.", stdout=None)
