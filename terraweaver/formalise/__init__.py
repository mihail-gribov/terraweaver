"""From a host's words to the code that creates the facts. The sentence door's reading.

The host says two things and a sentence — `world.relate(a, b, "Rome is the capital of Italy")` —
and the link is recorded at once, bare, with the words on it (`sentences.comes_in`). This is what
happens to it afterwards, at the close of the task, where nothing waits:

    look     the picker: is there already a word for this kind of link?          look.py
    make     the engineer: the lines that record it — declaring a word if none   make.py
    check    the picker: is every attribute that came from the text borne out?   check.py
    write    run through the host's door with the two things bound; the record   write.py
             says what landed, and the bare link ends where the typed one begins

Each step is its own module because each is its own question, asked of its own party, and each has
been wrong in its own way: the look is what makes a vocabulary converge, the make is where a date was
invented, the check is where that is refused before it is written, the write is where the world's own
refusals come back. Storage is not in here. It takes structured facts and it works; this is the part
in front of it, and the boundary is the lines of code handed to `runtime.run`.

Measured in experiments/01_relation_formalisation: nine facts said in words on a base world, nine
typed, seven words, the employment handover dated from the words, and the one invented date refused.

A link that cannot be placed stays bare, which is true of it. Nothing is marked hopeless.
"""
import time

from terraweaver import sentences, timeutil
from terraweaver.formalise import check, make, record, write
from terraweaver.formalise.look import look, words_for

# How many times the record's answer goes back to the engineer. Bounded for the reason a host's loop
# is: past a few goes the writer is writing against a record it has misunderstood, and going on
# spends the budget on copies of one error.
GOES = 3


def formalise(runtime, engineer, picker=None, limit: int = 100, seconds: float | None = None) -> dict:
    """Every bare link nobody has read, in the order it was said, looked for and then written.

    The order is not housekeeping. Everything the world does with a second fact about the same two
    ends assumes the second one arrived second: a new employer ends the standing one, and the line
    the world offers when it refuses — end that one where this one begins — is written for a fact
    that starts later than what is there. Read newest-first, a 2019 employment arrived against a
    2023 one already standing and there was no honest line that would record it.

    **The division of labour is the point, and it is strict.** The generative model generates: one
    open call, `make`, for the lines that declare the word and write the link. Everything that is a
    decision goes to the decision model — `look`, whether a word for this already exists, and
    `check`, whether the words bear out what is about to be written. Both are one question with
    named options, which is what a closed model is built for: an order of magnitude cheaper,
    calibrated, and it answers in a fraction of the time.

    Measured 2026-09-28 over 355 readings with no picker configured: every closed question went to
    the engineer instead (`outside.AsChoices`) — `look` 355 times, and in 331 of them it only had to
    pick a word the record already held, each time of a reasoning model with sixteen thousand tokens
    of thinking room. Median reading 7.1s, worst 118.8s, 79 minutes in all. That is the generative
    model doing the decision model's work, and paying for it twice over in time and money.

    The fallback stays for a world that can reach nobody else, because a reading that cannot ask is
    a reading that does not happen. It is a fallback and not the arrangement.

    **What to watch, since a decision model was once taken off this very question.** On 2026-09-24
    one answered link direction wrong at p=0.93, and a confidently wrong verdict corrupts a correct
    link. The question has changed since (a phrase put beside the account, `backwards` named), and
    `experiments/02_link_direction` measures both parties on it. `check.SURE_ENOUGH` is the
    threshold that holds the risk, and `readings.verdicts` records every verdict with its
    confidence, so a picker that starts refusing correct links shows up in the distribution rather
    than in a lost fact nobody can trace.
    """
    from terraweaver import outside

    picker = picker or getattr(runtime.world, "jev", None) or outside.AsChoices(engineer)
    bare = sorted(sentences.unread(runtime.world, limit),
                  key=lambda link: when_said(runtime.world, link))
    traces = []
    began = time.monotonic()
    for link in bare:
        # A budget, because "at the close, where nothing waits on it" was not true of the one thing
        # that waits: the host's own call. Twenty links at eight seconds each is minutes inside
        # `finish_task`, and measured on the first batch of a 455-fact run the call timed out three
        # times over and the batch was lost. What does not fit stays in the queue — it is unread,
        # which is what it is, and the next close or `catch_up` takes it.
        if seconds is not None and time.monotonic() - began > seconds:
            break
        started = time.monotonic()
        # Typed as of the moment the fact was said, not the moment it is being read. A
        # one-at-a-time word ends the standing link where the new one begins, so the link written
        # last is the one that stands — and this pass is resumable by design, so what is written
        # last is whichever pass the queue fell into, not what the user said last. Measured
        # 2026-10-01 on a 455-fact world: "Hines Ward plays the position of cornerback" (the
        # telling that stands) was typed at 02:22 and "wide receiver" (the one it replaced) at
        # 02:25, which ended it. Twenty-seven of that world's hundred and five missing facts are
        # this shape. With the clock where the fact was said, the hand-over compares the two
        # facts' own moments — and `_hand_over` refuses to end a link before it began, which is
        # the same guard from the other side.
        with timeutil.as_of(when_said(runtime.world, link)):
            one = formalise_one(runtime, link, engineer, picker)
        # Kept before the next link is read, so a reading that dies mid-run is still measured.
        record.keep(runtime.world, link, one, time.monotonic() - started)
        traces.append(one)
    return {"read": traces,
            "left unread": max(0, len(bare) - len(traces)),
            "typed": sum(1 for one in traces if one["typed"]),
            "joined": sum(1 for one in traces if one["typed"] and not one.get("defined")),
            "defined": sum(1 for one in traces if one.get("defined")),
            "left": sum(1 for one in traces if not one["typed"])}


def formalise_one(runtime, link, engineer, picker) -> dict:
    """One bare link, looked for, written, checked and run. Everything that happened, for the trace.

    The record's answer is kept go by go, because the answer is the whole diagnosis: a trace that held
    only the code once said "nothing came back" about a line the world had refused for a reason
    nobody could see.
    """
    from terraweaver.runtime import format_result

    world = runtime.world
    subject, obj = link.subject, link.object
    words = words_of(link)
    trace = {"words": words, "a": subject.display_name(), "b": obj.display_name(),
             "a_is": type(subject).__name__, "b_is": type(obj).__name__,
             "wrote": [], "answered": [], "checked": [], "went": "", "typed": []}
    if not words:
        trace["went"] = "nothing was said about it"
        return trace
    word, looked = look(world, subject, obj, words, picker)
    trace["look"], trace["found"] = looked, word
    before = {name for name, _, _ in words_for(world)}
    # What already joined these two before this reading wrote anything. Everything below asks
    # "what did *this* go write", and the only way to answer that is to know what was there.
    already = {one.id for one in write.typed_between(world, subject, obj)}
    if already:
        trace["was_typed"] = len(already)
    asked = make.question(world, subject, obj, words, word)
    code, trouble = make.lines(engineer, asked)
    for go in range(GOES):
        if not code:
            trace["went"] = f"nothing came back — {trouble}" if trouble else "nothing came back"
            break
        trace["wrote"].append(code)
        got = write.run(runtime, code, a=subject, b=obj)
        answer = format_result(got)
        made = write.typed_between(world, subject, obj, apart_from=already)
        # Judged on what the record now holds, not on the shape of the lines that wrote it. A claim
        # can be written four ways and a parser of the source saw it in one of them, so an invented
        # date went in whenever the engineer phrased the write differently. What the world holds is
        # the one thing that cannot be phrased three ways — and it is rendered as the phrase it
        # amounts to, which is what makes the question answerable at all.
        # A label is not a sentence, and nothing can be borne out by a word. 124 of 442 bare links
        # in one 455-fact world had `words` like `created_in` or `has_capital` and nothing else —
        # the host wrote `label=` where the fact in words was wanted. Asked anyway, the check
        # refuses whatever was written (217 readings carry `not_in_it`, up to 0.99), the goes run
        # out, and the link is taken back: the fact is lost to a question nobody could answer.
        # So it is not asked, and the trace says why (docs/now.md, item 2).
        if only_a_word(words):
            unsupported, about = "", {"asked": False, "why": "the words are a label, not a fact: "
                                                             "nothing can bear a claim out"}
        else:
            unsupported, about = check.not_borne_out(picker, words, made)
        trace["checked"].append(about)
        if unsupported:
            trace["answered"].append(unsupported)
            if go == GOES - 1:
                # No goes left, so the decision model's answer is the last word and is acted on
                # rather than thrown away: the ends go round where it said backwards, an attribute
                # it did not find in the words comes off, and only a link the words are not about
                # at all is taken back. Measured 2026-09-28: 12 readings of 355 ended here and 71
                # gave up, each one a link the engineer had written and the record then lost.
                settled = write.settle_by_verdict(world, made, about)
                trace["settled"] = settled
                still = write.typed_between(world, subject, obj, apart_from=already)
                if still:
                    trace["went"] = "settled on the picker's verdict"
                    trace["typed"] = [one.display_name() for one in still]
                    trace["kind"] = type(still[0])._spec["relation"]["kind"]
                    trace["defined"] = sorted({n for n, _, _ in words_for(world)} - before) or None
                    write.end_the_bare_one(world, link)
                else:
                    trace["went"] = "not borne out by the words"
                break
            # The world's own conclusion, taken back before anybody reads it: these were written
            # under `stating("world")`, so `retract` will have them, and what the host said is
            # untouched — the bare link and its words are still there to be read again.
            write.take_back(world, made)
            # The second go is the senior's: the junior has written lines the record would not have,
            # and asking the same model the same way again mostly gets the same lines.
            code, trouble = make.lines(again_with(runtime, engineer),
                                       make.again(asked, code, unsupported))
            continue
        trace["answered"].append(answer[:2000])
        if made:
            trace["went"] = "done" if got.get("ok") else "written, with a refusal on the way"
            trace["typed"] = [one.display_name() for one in made]
            trace["kind"] = type(made[0])._spec["relation"]["kind"]
            trace["defined"] = sorted({n for n, _, _ in words_for(world)} - before) or None
            write.end_the_bare_one(world, link)
            break
        if go == GOES - 1:
            trace["went"] = "gave up"
            break
        back = (make.joined_nothing(asked, code, answer[:1200]) if got.get("ok")
                else make.again(asked, code, answer[:1500]))
        code, trouble = make.lines(again_with(runtime, engineer), back)
    return trace


def again_with(runtime, engineer):
    """Who writes the second attempt: the senior engineer, where this world can reach one.

    The junior writes the first go and finishes most of them. When the record refuses its lines,
    asking the same model the same way again mostly gets the same lines back — so the go that
    follows a refusal goes to the larger model, and only that go. `world.better` is set where a
    world is opened with keys (server, catch_up); without it the junior tries again as before.
    """
    return getattr(runtime.world, "better", None) or engineer


def only_a_word(words: str) -> bool:
    """Whether what the host gave is a word for the link rather than the fact in words.

    One token and no spaces — `created_in`, `has_capital`, `citizen_of`. The world takes it (never
    refuse a write) and says at the close what it costs; what it cannot do is ask anybody whether
    a claim is borne out by it.
    """
    said = str(words or "").strip()
    return bool(said) and " " not in said


def words_of(link) -> str:
    """The words the host said this link in — its description, and there is nothing else."""
    for said in (link.__dict__.get("descriptions") or []):
        if isinstance(said, str) and said.strip():
            return said.strip()
    return ""


def when_said(world, link):
    """When the host said this link — the oldest of everything said about it, then its own birth.

    This is what the queue is sorted by, and the sort is not cosmetic: a one-at-a-time word ends
    the standing link at the moment a new one begins, so the link read **last** is the one that
    stands. Read out of order, the older telling wins and the world holds the fact the user
    corrected.

    Measured 2026-10-01 on a 455-fact world: "Hines Ward plays the position of cornerback" (said
    after "wide receiver", and the one that stands) was typed at 02:22:11; "wide receiver" was
    typed at 02:25:31 and ended it. It read `descriptions` only, and a bare link the host wrote
    with `label=` rather than `description=` has no `descriptions` statement at all — so every one
    of those came back `""`, sorted equal, and the queue's order was whatever the rows happened to
    be in. Twenty-seven of the hundred and five facts that world did not hold are this.

    Everything said about the link, then — a label, its ends, a description — and, failing all of
    that, when the link itself was made. A moment, not a string: `min` over two spellings of a
    moment compares them as text.
    """
    from terraweaver import timeutil

    try:
        said = world.facts.about(link.id)
    except Exception:  # noqa: BLE001 - a link whose statements cannot be read is as old as any
        said = []
    moments = [one.stated_at for one in said if one.stated_at]
    if moments:
        return min(timeutil.as_datetime(one) for one in moments)
    born = getattr(link, "created_at", None)
    return timeutil.as_datetime(born) if born else timeutil.ALWAYS


__all__ = ["formalise", "formalise_one", "look", "only_a_word", "words_for", "words_of",
           "when_said", "GOES"]
