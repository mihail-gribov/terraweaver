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

from terraweaver import sentences
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

    No picker configured, the engineer answers the closed questions too (`outside.AsChoices`): the
    same question and options, one answer with all the weight, at an engineer's price.
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
    asked = make.question(world, subject, obj, words, word)
    code, trouble = make.lines(engineer, asked)
    for go in range(GOES):
        if not code:
            trace["went"] = f"nothing came back — {trouble}" if trouble else "nothing came back"
            break
        trace["wrote"].append(code)
        got = write.run(runtime, code, a=subject, b=obj)
        answer = format_result(got)
        made = write.typed_between(world, subject, obj)
        # Judged on what the record now holds, not on the shape of the lines that wrote it. A claim
        # can be written four ways and a parser of the source saw it in one of them, so an invented
        # date went in whenever the engineer phrased the write differently. What the world holds is
        # the one thing that cannot be phrased three ways — and it is rendered as the phrase it
        # amounts to, which is what makes the question answerable at all.
        unsupported, about = check.not_borne_out(picker, words, made)
        trace["checked"].append(about)
        if unsupported:
            # The world's own conclusion, taken back before anybody reads it: these were written
            # under `stating("world")`, so `retract` will have them, and what the host said is
            # untouched — the bare link and its words are still there to be read again.
            write.take_back(world, made)
            trace["answered"].append(unsupported)
            if go == GOES - 1:
                trace["went"] = "not borne out by the words"
                break
            code, trouble = make.lines(engineer, make.again(asked, code, unsupported))
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
        code, trouble = make.lines(engineer, back)
    return trace


def words_of(link) -> str:
    """The words the host said this link in — its description, and there is nothing else."""
    for said in (link.__dict__.get("descriptions") or []):
        if isinstance(said, str) and said.strip():
            return said.strip()
    return ""


def when_said(world, link) -> str:
    """When the host said this link, from the statements about it. The oldest wins."""
    try:
        said = world.facts.about(link.id, "descriptions")
    except Exception:  # noqa: BLE001 - a link whose statements cannot be read is as old as any
        return ""
    return min((str(one.stated_at) for one in said if one.stated_at), default="")


__all__ = ["formalise", "formalise_one", "look", "words_for", "words_of", "when_said", "GOES"]
