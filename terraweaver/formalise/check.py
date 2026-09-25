"""Is every claim in these lines borne out by the sentence? A closed question each, to the picker.

**Before the lines run, not after.** A check that reads the record afterwards has to delete what it
finds, and deleting is the expensive direction: the write is committed, whoever held the instance
holds a stale one, and a link taken back leaves the fact it came from unrecorded. Asked first, a
claim nobody said is simply **never added** — the line does not run, the world hands back what it
would hand a host, and the engineer writes the continuation. The same three goes as any refusal.

What the check is for, measured: the engineer read "Rome is the capital of Italy", which carries no
date, and wrote `starts="1792"` — the French republic, from the Paris fact it had never been shown.
The question says *nothing is worked out from elsewhere* and saying it was not enough. A reading
takes its dates from the sentence and from nowhere else, so that is a check and not an instruction.

**Every attribute that came from the sentence, and nothing else.** The link written — which two
things, by which word, which way round — and every attribute written onto it: when it began, when it
ended, a label, a role, whatever the line sets. Those are the only places a claim nobody made can get
in, because they are the only places that are filled from the text. Everything else on the line is
the world's own structure, which is not read out of a sentence and cannot be wrong about one.

**The picker, not the engineer.** Each of these is one question with named options, which is what a
closed model is for: an order of magnitude cheaper, calibrated, and every question here has two or
three answers and no prose in them.
"""
import ast

from terraweaver import prompts

# Where the claims are put in one call. The state — the sentence and the two things — is billed once
# however many questions ride on it, so a line with a word and a date costs one call and not two.
SAYS_SO = "says_so"
BACKWARDS = "backwards"
NOT_IN_IT = "not_in_it"
ANOTHER = "says_another"

# How sure the picker has to be before a line is refused. Below this the verdict is not acted on and
# the line runs: a false alarm here costs the fact — the engineer spends a go rewriting something
# that was right, and after three it has spent them all — while a missed one costs a claim nobody
# said, which the next pass over the record can still find. Nothing is more wrong than an alarm that
# is wrong, so the doubt goes to the line and not against it.
SURE_ENOUGH = 0.6


def claims_in(code: str, ends: dict) -> list[dict]:
    """Every claim these lines make about the fact: the link, and each date on it.

    Read out of the code rather than out of what the engineer said about it, because the code is
    what will run. `a.set_born_in(b, starts="1558")` is two claims — that a was born in b, and that
    it began in 1558 — and they are refused separately: a date nobody said does not make the link
    wrong, and refusing the pair together would lose a fact that was said.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []                      # a line that cannot be parsed cannot be claimed about
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        word = node.func.attr
        if not word.startswith("set_"):
            continue
        word = word[len("set_"):]
        near = getattr(node.func.value, "id", None)
        far = getattr(node.args[0], "id", None) if node.args else None
        if near not in ends or far not in ends:
            continue                   # not written against the two things we handed over
        out.append({"what": "link", "word": word, "subject": ends[near], "object": ends[far]})
        for keyword in node.keywords:
            # A literal is a claim somebody can check against the sentence. A name or an expression
            # is the world's own value — `starts=now()` is not read out of anything — and there is
            # nothing in the text to hold it against.
            if keyword.arg is None or not isinstance(keyword.value, ast.Constant):
                continue
            said = str(keyword.value.value).strip()
            if not said:
                continue
            what = keyword.arg if keyword.arg in ("starts", "until") else "attribute"
            out.append({"what": what, "name": keyword.arg, "said": said, "word": word,
                        "subject": ends[near], "object": ends[far]})
    return out


def _asking(claim: dict) -> tuple:
    """One claim as a closed question: what to ask, and the options with what each means."""
    a, b = claim["subject"].display_name(), claim["object"].display_name()
    said_as_words = claim["word"].replace("_", " ")
    if claim["what"] == "link":
        return (f"Does that sentence say that {a} {said_as_words} {b}?",
                {SAYS_SO: f"yes — the sentence says {a} {said_as_words} {b}, that way round",
                 BACKWARDS: f"the sentence says this the other way round: {b} {said_as_words} {a}",
                 NOT_IN_IT: "the sentence does not say this at all"})
    if claim["what"] == "attribute":
        return (f"Does that sentence say that, where {a} {said_as_words} {b}, the "
                f"{claim['name'].replace('_', ' ')} is {claim['said']!r}?",
                {SAYS_SO: "yes — the sentence says that, in those words or plainly the same thing",
                 ANOTHER: f"the sentence says what the {claim['name'].replace('_', ' ')} is, and "
                          f"it is something else",
                 NOT_IN_IT: "the sentence does not say this at all"})
    when = "began" if claim["what"] == "starts" else "ended"
    return (f"Does that sentence say that {a} {said_as_words} {b} {when} in {claim['said']!r}?",
            {SAYS_SO: f"yes — the sentence gives that time, in those words or plainly the same "
                      f"time in other words",
             ANOTHER: f"the sentence says when it {when}, and it is a different time",
             NOT_IN_IT: f"the sentence does not say when it {when} — that time is not in it"})


def what_is_wrong(picker, words: str, code: str, ends: dict) -> tuple:
    """What in these lines the sentence does not bear out, as the world would say it. And the trace.

    Returns (what to say back, what was asked and answered). Nothing to say means every claim is
    borne out, or the picker could not be asked at all — a check that cannot run leaves the lines
    alone rather than holding up the record.
    """
    claims = claims_in(code, ends)
    if not claims:
        return "", {"asked": False, "why": "the lines make no claim about these two things"}
    state = prompts.IS_IT_SAID.format(words=words)
    questions = {}
    for n, claim in enumerate(claims):
        instructions, options = _asking(claim)
        questions[f"q{n}"] = {"type": "choice", "instructions": instructions, "criteria": options}
    try:
        answers = picker.ask(state, questions)
    except Exception as wrong:  # noqa: BLE001 - a check that cannot run is not a line refused
        return "", {"asked": True, "failed": str(wrong)[:200]}
    trace, refused = [], []
    for n, claim in enumerate(claims):
        scored = (answers.get(f"q{n}") or {}).get("probabilities") or {}
        if not scored:
            continue
        verdict = max(scored, key=scored.get)
        sure = float(scored.get(verdict, 0.0))
        trace.append({"claim": {k: (v.display_name() if hasattr(v, "display_name") else v)
                                for k, v in claim.items()},
                      "verdict": verdict, "sure": round(sure, 3)})
        if verdict == SAYS_SO or sure < SURE_ENOUGH:
            continue
        refused.append(_why(claim, verdict))
    if not refused:
        return "", {"asked": True, "claims": trace}
    return (prompts.NOT_BORNE_OUT.format(what="\n    ".join(refused)),
            {"asked": True, "claims": trace, "refused": refused})


def _why(claim: dict, verdict: str) -> str:
    """The one line the world says about a claim it will not take."""
    a, b = claim["subject"].display_name(), claim["object"].display_name()
    said_as_words = claim["word"].replace("_", " ")
    if claim["what"] == "link":
        if verdict == BACKWARDS:
            return (f"{a} {said_as_words} {b} — the sentence says it the other way round. Turn it "
                    f"round: the subject is the end the fact starts from.")
        return f"{a} {said_as_words} {b} — the sentence does not say this."
    if claim["what"] == "attribute":
        if verdict == ANOTHER:
            return (f"{claim['name']}={claim['said']!r} — the sentence says something else. Use "
                    f"what it says.")
        return (f"{claim['name']}={claim['said']!r} — the sentence does not say this. Leave it "
                f"out.")
    when = "began" if claim["what"] == "starts" else "ended"
    if verdict == ANOTHER:
        return (f"{claim['what']}={claim['said']!r} — the sentence says when it {when} and it is "
                f"not that. Use the words the sentence used.")
    return (f"{claim['what']}={claim['said']!r} — the sentence says nothing about when it {when}. "
            f"Leave it out; a link with no start is a true record of a fact that came without one.")
