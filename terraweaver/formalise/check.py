"""Is every claim in these lines borne out by the sentence? A closed question each, to the picker.

**On what the record now holds, not on the lines that wrote it.** This read the engineer's source
with `ast` and looked for `a.set_word(b, ...)`, on the argument that a claim refused before the write
never has to be taken back. The argument was sound and the reading of the source was not: measured,
one fact with one invented date written four ways — through `world.relate`, through a renamed
variable, through a one-element loop — made *no claim* three times out of four, and the date went in
unchecked. A fact can be phrased many ways and the record holds one thing, so the record is what is
asked about. What the check will not have is taken back at once (`write.take_back`), which is safe
here for the reason the old argument named: these writes are the world's own, made a moment ago by
the reading, marked `source="world"`, and nobody outside has seen them.

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


def _asking(claim: dict) -> tuple:
    """One claim as a closed question: what to ask, and the options with what each means."""
    a, b = claim["subject"].display_name(), claim["object"].display_name()
    said_as_words = claim["word"].replace("_", " ")
    if claim["what"] == "link":
        # The claim as a phrase, put beside the account, rather than a question about whether a
        # fragment "says" something about two names it does not contain. Asked the old way over the
        # account `capital_of`, the picker answered "does not say this at all" at full confidence
        # about `Chang'an capital of Tang Empire` — and the words "capital of" are right there in it.
        return (f"The record is about to hold this: \u00ab{a} {said_as_words} {b}\u00bb. Is that the "
                f"same thing the account says?",
                {SAYS_SO: f"yes — the account says {said_as_words}, and this way round, or it does "
                          f"not say which way round and this one is not against it",
                 BACKWARDS: f"the account says the other way round: \u00ab{b} {said_as_words} {a}\u00bb",
                 NOT_IN_IT: f"the account is about something else — {said_as_words} is not what it "
                            f"joins these two by"})
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


# --- the same questions, asked of what the world actually holds ---

# Attributes the machinery keeps, which are never read out of a sentence and so are never claims.
KEPT_BY_THE_WORLD = {"subject", "object", "descriptions", "tags", "created_at", "accessed_at",
                     "from_is", "until_is", "id", "subject_id"}


def phrase(link) -> str:
    """What the world is about to hold, said as a phrase: "Chang'an capital of Tang Empire".

    The pseudo-sentence is the point of asking this way round. `capital_of` is what the host said
    and it plainly contains "capital of", so a question that puts the two beside each other can be
    answered; the question that was asked instead — does this fragment *say* that Chang'an is the
    capital of the Tang Empire — cannot be, because a fragment names nobody, and the picker duly
    answered "the sentence does not say this at all" with all its weight behind it.
    """
    word = (spec_of(link).get("kind") or "related").replace("_", " ")
    return (f"{link.subject.display_name()} {word} {link.object.display_name()}")


def spec_of(link) -> dict:
    return (getattr(type(link), "_spec", {}) or {}).get("relation") or {}


def claims_of(links: list) -> list[dict]:
    """Every claim the record now makes about these two things: the link, and what is written on it.

    Read from the instances and not from the lines that made them. The lines are one way of writing
    the fact out of many — measured, `world.relate(a, b, ...)`, a renamed variable and a one-element
    loop each wrote the same fact with the same invented date and each made *no claim* as far as a
    parser of the source could see, so the date went in unchecked. What the world holds is the one
    thing that cannot be written three ways.
    """
    out = []
    for link in links:
        word = spec_of(link).get("kind") or "related"
        out.append({"what": "link", "word": word, "subject": link.subject, "object": link.object,
                    "link": link})
        for name, value in sorted(link.__dict__.items()):
            if name in KEPT_BY_THE_WORLD or value in (None, "", [], {}):
                continue
            said = str(getattr(value, "date", lambda: value)() if hasattr(value, "date") else value)
            said = said.strip()
            if not said:
                continue
            what = name if name in ("valid_from", "valid_until") else "attribute"
            out.append({"what": {"valid_from": "starts", "valid_until": "until"}.get(name, what),
                        "name": name, "said": said[:60], "word": word,
                        "subject": link.subject, "object": link.object, "link": link})
    return out


def not_borne_out(picker, words: str, links: list) -> tuple:
    """Which of the claims the record now makes the words do not bear out. And the trace.

    The same questions and the same threshold as before; what changed is where the claims come from
    and that the link is named as a phrase rather than as three words the picker has to assemble.
    """
    claims = claims_of(links)
    if not claims:
        return "", {"asked": False, "why": "nothing was written between these two things"}
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
        trace.append({"claim": _readable(claim), "verdict": verdict, "sure": round(sure, 3)})
        if verdict == SAYS_SO or sure < SURE_ENOUGH:
            continue
        refused.append(_why(claim, verdict))
    if not refused:
        return "", {"asked": True, "claims": trace}
    return (prompts.NOT_BORNE_OUT.format(what="\n    ".join(refused)),
            {"asked": True, "claims": trace, "refused": refused})


def _readable(claim: dict) -> dict:
    return {k: (v.display_name() if hasattr(v, "display_name") else v)
            for k, v in claim.items() if k != "link"}
