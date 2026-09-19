"""Code-writing agent.

The model is driven through fixed stages rather than left to pick how to reply —
each stage asks for one thing and accepts only that:

1. WHICH CLASSES — the model sees the one-line catalog and answers with just the
   class names it needs. No code is possible here.
2. WHICH OBJECTS — it names the entities the task refers to ("Person: full_name=
   \"Annie\""). The harness resolves each against the world *before any code runs*.
   An entity that isn't uniquely determined — five Annies, or one fuzzy Annie — is not
   an error and not something to infer: the task pauses, the resolution skill puts
   the question to the user, and the settled entity comes back bound to a readable
   variable (`anna`) for the code to use.
3. CODE — the model writes one script against those already-resolved objects, so
   its code answers "what to do with them", never "which ones". The script runs
   against a namespace that persists for the whole task, Jupyter-kernel style. A
   task is finished only when a script calls `report(value)`: running without
   raising is NOT enough, since a script that merely inspects data also runs
   cleanly without answering.
     - raised an exception -> error fed back, model sends a fixed script;
     - ran clean but never reported -> told it hasn't answered yet, continues;
     - called report(...) -> that value is the answer, task ends.
   The code stage loops until one of those settles it, capped by MAX_ROUNDS.

The resulting world state is persisted when the task ends. Every message of a
task — including the skill's dialogue with the user — is tagged with that task's
id in `AgentResult.transcript`.
"""
import contextlib
import io
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from terraweaver import matching, resolution
from terraweaver.llm import DEFAULT_MODEL, client
from terraweaver.ontology import COMMON_MEMBERS, Entity, describe_for_prompt, track_access
from terraweaver.resolution import NeedsResolution
from terraweaver.session import Session
from terraweaver.world import describe_world_api

MAX_ROUNDS = 6

STAGE_CLASSES_SYSTEM = """\
You are working against a personal world model made of Python classes.

Available classes (name: one-line description):
{catalog}

Answer with ONLY a comma-separated list of the class names needed for the user's task.
No explanation, no code. If none apply, answer exactly: NONE
"""

STAGE_OBJECTS_SYSTEM = """\
You are working against a personal world model. These classes are in play:

{details}

The user's task may refer to entities that already exist in their world — a person by
name, a company, and so on. List those references so they can be looked up before any
code runs. One per line, in exactly this form and nothing else:

Person: full_name="Annie"
Organization: name="Acme"

Only list entities the task names or describes directly. Do NOT list things that have to
be found by a query ("the three highest-paying remote vacancies", "vacancies I haven't
applied to") — those stay for the code. If the task names no specific entity, answer
exactly: NONE
"""

STAGE_CODE_SYSTEM = """\
You are a coding agent working against a personal world model made of Python classes.

Classes in play:
{details}
{variables_section}{world_section}
Rules:
- Respond with EXACTLY one fenced python code block and nothing else. The classes are
  already available as globals in the exec namespace — do not redefine or import them.
- The task is finished only when your code calls report(value) with the answer, e.g.
  report(3935.75), report(["Title A", "Title B"]), report({{"TechCorp": 5}}), or for a task
  that just changes the world, report the object(s) you created/updated. Running without
  an error is NOT finishing — if a script runs clean but never calls report(...), you'll be
  told you haven't answered yet and asked to continue.
- Use print(...) freely for anything else; only report(...) ends the task.
- Making things up is forbidden, and so is emulating a result: never type a value you believe
  to be true, never hardcode an answer, never stand in for work you didn't do. Every figure,
  name and date you report must be read out of the world in the very script that reports it.
  If you can't get it from the world, say so instead of producing something that looks right.
- If your script raises an error, you'll see the error and may resend a corrected script.
  The namespace persists across attempts — variables your script defined before the error
  are still there, so fix and continue rather than starting over.
- If the task cannot be done with what you have, respond with EXACTLY one line:
  CANNOT_SOLVE: <short reason>
"""

CANNOT_SOLVE_RE = re.compile(r"^\s*CANNOT_SOLVE:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)
OBJECT_REF_RE = re.compile(r"^\s*(\w+)\s*:\s*(.+?)\s*$", re.MULTILINE)
ATTR_RE = re.compile(r"(\w+)\s*=\s*\"([^\"]*)\"")


@dataclass
class AgentResult:
    success: bool
    message: str
    task_id: str = ""
    # "resolved" / "unresolved" — the task-level counterpart of a skill's status.
    status: str = ""
    code: str | None = None  # all executed attempts, concatenated (failed ones included)
    stdout: str | None = None  # stdout of the final attempt
    value: Any = None  # whatever the agent passed to report(...)
    error: str | None = None
    transcript: list[dict] = field(default_factory=list)  # tagged with task_id
    rounds: int = 0  # LLM calls made across all stages
    namespace: dict | None = None
    resolutions: list[dict] = field(default_factory=list)
    # Entities resolved before the code stage: variable name -> description.
    objects: dict = field(default_factory=dict)
    # Everything in the session namespace with its description.
    variables: dict = field(default_factory=dict)


class _Reporter:
    """Injected into the namespace as report(): the agent's explicit 'here is the answer'."""

    def __init__(self):
        self.called = False
        self.value = None

    def __call__(self, value=None):
        self.called = True
        self.value = value
        print(value)  # inside the redirected stdout, so the answer always shows up in output


def _catalog(specs: dict[str, dict[str, Any]]) -> str:
    return "\n".join(f"- {name}: {spec.get('description', '')}" for name, spec in specs.items())


def _unresolved_section(unsettled: list[str], absent: list[str]) -> str:
    """Two very different situations, and confusing them breaks the task either way.

    An *unsettled* reference means we don't know who is meant — inventing one would be a
    guess. An *absent* one simply isn't in the world yet, which is the normal state of
    someone the user is telling you about for the first time; refusing to record them
    turns "put this in my records" into "not found".
    """
    lines = []
    if unsettled:
        lines.append("\nReferences the user has not settled — don't guess at them:")
        lines.extend(f"- {note}" for note in unsettled)
    if absent:
        lines.append("\nNot in the world yet — new to you, not missing. If the task is telling you")
        lines.append("about them, record them with Class.ensure(...); don't report them as not found:")
        lines.extend(f"- {note}" for note in absent)
    return ("\n".join(lines) + "\n") if lines else ""


def _var_name(instance, taken: set[str]) -> str:
    """A readable identifier for a resolved entity: Anna Sullivan -> anna, Ada Lovelace -> ada."""
    label = ""
    for attr in ("full_name", "name", "title"):
        value = getattr(instance, attr, None)
        if isinstance(value, str) and value:
            label = value
            break
    slug = re.sub(r"[^a-z0-9]+", "_", matching.normalize(label)).strip("_")
    base = (slug.split("_")[0] or type(instance).__name__.lower())[:20]
    if not base.isidentifier():
        base = type(instance).__name__.lower()
    candidate, suffix = base, 2
    while candidate in taken:
        candidate = f"{base}_{suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate



def _run_step(code: str, namespace: dict[str, Any]) -> tuple[bool, str, str | None, _Reporter, dict]:
    """Execute one code block. Returns (ok, stdout, error, reporter, world contact counts)."""
    reporter = _Reporter()
    namespace["report"] = reporter
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), track_access() as access:
            exec(compile(code, "<agent_script>", "exec"), namespace)
            touched = dict(access)
    except Exception as exc:  # noqa: BLE001 - reporting any exception is the point
        return False, stdout.getvalue(), f"{type(exc).__name__}: {exc}", reporter, {}
    return True, stdout.getvalue(), None, reporter, touched


def _persist_world(namespace: dict[str, Any], classes: dict[str, type], store) -> None:
    """Write every model instance reachable from the namespace back to the store."""
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


def _parse_object_refs(reply: str, specs: dict) -> list[tuple[str, dict]]:
    refs = []
    for class_name, rest in OBJECT_REF_RE.findall(reply or ""):
        if class_name not in specs:
            continue
        attrs = {key: value for key, value in ATTR_RE.findall(rest)}
        if attrs:
            refs.append((class_name, attrs))
    return refs


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
    session: "Session | None" = None,
) -> AgentResult:
    seed = seed or {}
    task_id = task_id or uuid.uuid4().hex[:8]
    llm = client()
    transcript: list[dict] = []
    rounds = 0
    # A session carries the namespace and its described variables across tasks; without one,
    # the task gets a fresh session of its own.
    if session is None:
        session = Session(classes, seed=seed, world=world)

    def note(role: str, content: str, kind: str) -> None:
        transcript.append({"task_id": task_id, "seq": len(transcript), "role": role, "kind": kind, "content": content})

    def ask_model(system: str, user: str, kind: str) -> str:
        nonlocal rounds
        note("system", system, f"{kind}:prompt")
        note("user", user, f"{kind}:task")
        response = llm.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        rounds += 1
        reply = response.choices[0].message.content or ""
        note("assistant", reply, f"{kind}:reply")
        return reply

    def asking_wrapper(needs: NeedsResolution):
        kind = resolution.SKILL_KINDS.get(needs.skill, needs.skill)

        def asking(question: str, options: list[str]) -> int | None:
            note("assistant", f"[{kind}] {question} {options}", f"{kind}:question")
            choice = ask_user(question, options) if ask_user else None
            settled = choice is not None and 0 <= choice < len(options)
            note("user", f"[{kind}] {options[choice] if settled else '(not settled)'}", f"{kind}:answer")
            status = resolution.RESOLVED if settled else resolution.UNRESOLVED
            note("system", f"[{kind}] {status}", f"{kind}:{status}")
            return choice

        return asking

    # --- Stage 1: which classes ---
    reply = ask_model(STAGE_CLASSES_SYSTEM.format(catalog=_catalog(specs)), task, "stage1_classes")
    chosen = [name for name in specs if re.search(rf"\b{re.escape(name)}\b", reply)]
    selected = {name: specs[name] for name in chosen} or specs
    note("system", f"[stage1] classes in play: {', '.join(selected)}", "stage1_classes:result")
    # If the task is about the world model at all, the answer has to come from it.
    expects_world = bool(chosen)
    details = COMMON_MEMBERS + "\n" + describe_for_prompt(selected)

    # --- Stage 2: which objects (identity settled before any code runs) ---
    object_descriptions: dict[str, str] = {}
    unsettled: list[str] = []
    absent: list[str] = []
    if world is not None:
        reply = ask_model(STAGE_OBJECTS_SYSTEM.format(details=details), task, "stage2_objects")
        for class_name, attrs in _parse_object_refs(reply, specs):
            described = ", ".join(f'{k}="{v}"' for k, v in attrs.items())
            outcome = world.resolve_reference(class_name, **attrs)
            if isinstance(outcome, NeedsResolution):
                outcome = resolution.run_skill(outcome, asking_wrapper(outcome), world)
            if isinstance(outcome, NeedsResolution):
                unsettled.append(f"{class_name} {described}: the user did not settle which one is meant")
            elif outcome is None:
                absent.append(f"{class_name} {described}")
            else:
                var_name = _var_name(outcome, set(session.namespace))
                session.bind(var_name, outcome, "entity the task refers to, identity already settled")
                object_descriptions[var_name] = session.variables[var_name]["description"]
        note(
            "system",
            f"[stage2] resolved: {object_descriptions or 'none'}; "
            f"unsettled: {unsettled or 'none'}; absent: {absent or 'none'}",
            "stage2_objects:result",
        )

    # --- Stage 3: code, executed against the session's namespace ---
    namespace = session.namespace
    if world is not None:
        namespace["world"] = world
        namespace["NeedsResolution"] = NeedsResolution
        namespace["run_skill"] = lambda needs: resolution.run_skill(needs, asking_wrapper(needs), world)

    code_system = STAGE_CODE_SYSTEM.format(
        details=details,
        variables_section=session.describe_for_prompt() + _unresolved_section(unsettled, absent),
        world_section=describe_world_api() if world is not None else "",
    )
    messages = [{"role": "system", "content": code_system}, {"role": "user", "content": task}]
    note("system", code_system, "stage3_code:prompt")
    note("user", task, "stage3_code:task")
    code_log: list[str] = []

    def finish(**kwargs) -> AgentResult:
        if store is not None:
            _persist_world(namespace, classes, store)
        status = resolution.RESOLVED if kwargs.get("success") else resolution.UNRESOLVED
        note("system", f"[task] {status}: {kwargs.get('message', '')}", f"task:{status}")
        return AgentResult(
            task_id=task_id,
            status=status,
            transcript=transcript,
            namespace=namespace,
            resolutions=list(world.resolutions) if world is not None else [],
            objects=object_descriptions,
            variables=dict(session.variables),
            rounds=rounds,
            **kwargs,
        )

    for attempt in range(MAX_ROUNDS):
        response = llm.chat.completions.create(model=model, messages=messages)
        rounds += 1
        reply = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": reply})
        note("assistant", reply, "stage3_code:reply")

        cannot_solve_match = CANNOT_SOLVE_RE.search(reply)
        code_match = CODE_BLOCK_RE.search(reply)
        last_attempt = attempt == MAX_ROUNDS - 1

        if code_match:
            code = code_match.group(1).strip()
            ok, out, err, reporter, touched = _run_step(code, namespace)
            world_contact = sum(touched.values())
            code_log.append(code)
            newly_bound = session.sync()  # whatever the script left behind joins the registry
            if newly_bound:
                note("system", f"[variables] new: {', '.join(newly_bound)}", "variables:new")

            # The script that answers must itself have consulted the world. Measured at the
            # source rather than guessed from the text: an answer typed as literals makes no
            # queries and reads no entity, however plausible it looks. An earlier step having
            # touched the world doesn't count — that's what re-typing the values looks like.
            if ok and reporter.called and expects_world and not world_contact and not last_attempt:
                refusal = (
                    "Not accepted: your script answered without consulting the world — no query, "
                    "no entity read. Making up an answer or emulating the result is forbidden, "
                    "however sure you are of the values. Read them from the world in the very "
                    "script that reports them, and send it again."
                )
                messages.append({"role": "user", "content": refusal})
                note("user", refusal, "stage3_code:not_grounded")
                continue

            if ok and reporter.called:
                return finish(success=True, message="Solved.", code="\n\n".join(code_log), stdout=out, value=reporter.value)
            if not ok:
                if last_attempt:
                    return finish(
                        success=False,
                        message="Agent's script raised an error.",
                        code="\n\n".join(code_log),
                        stdout=out,
                        error=err,
                    )
                feedback = (
                    f"Your script raised an error:\n{err}\n\n"
                    "Variables it defined before the error are still in the namespace. Fix the "
                    "script and resend it as a single python code block, or reply "
                    "CANNOT_SOLVE: <reason> if it can't be fixed."
                )
            else:
                if last_attempt:
                    return finish(
                        success=False,
                        message="Agent never called report(...) with an answer.",
                        code="\n\n".join(code_log),
                        stdout=out,
                    )
                feedback = (
                    f"Your script ran without errors but never called report(...), so the task "
                    f"isn't answered yet. stdout was:\n{out or '(no output)'}\n\n"
                    "Send another code block that finishes the task and calls report(value) with "
                    "the answer, or reply CANNOT_SOLVE: <reason> if it can't be done."
                )
            messages.append({"role": "user", "content": feedback})
            note("user", feedback, "stage3_code:feedback")
            continue

        if cannot_solve_match:
            return finish(success=False, message=cannot_solve_match.group(1).strip(), code="\n\n".join(code_log) or None)

        nudge = (
            "Your previous reply did not match the expected format. Respond now with EXACTLY one "
            "python code block that calls report(value), or EXACTLY one CANNOT_SOLVE: <reason> line."
        )
        messages.append({"role": "user", "content": nudge})
        note("user", nudge, "stage3_code:nudge")

    return finish(success=False, message="Agent did not converge to a reported answer in time.", code="\n\n".join(code_log) or None)
