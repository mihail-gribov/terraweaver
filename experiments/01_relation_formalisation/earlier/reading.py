"""Two things and a description of what joins them, into the lines that record the link.

The piece under test. Everything it writes with is the world's own — `define_relation` from
`world.extras`, `set_<word>` off the type, the same sandbox, the same store, the same refusals —
and what is new is only where the type comes from.

    look    Is there already a word for this kind of link? A closed question over what the record
            holds, narrowed by the classes at the two ends, with a way out among the options. This
            is the step that makes a vocabulary converge: without it every fact describes a new
            relation and a world ends up holding two words for one idea, each answering for half
            of it. Nothing is defined here and nothing is named twice.

    ask     Only what the look could not place, and then one open call: the lines that record it.
            Code, not a description somebody here renders — see `asking`.

    run     Through the door a host's code goes through (`runtime.run`), with `a` and `b` bound
            before it starts. Which two things is never read out of an answer: identity is handed
            over here as it is everywhere else in this world. It fails, the world says what it
            would say to a host, and that goes back to whoever wrote the line. Three goes.

    end     The bare link stops where the typed one begins. Not erased: what was said was said,
            and the words the host used are the only account of this link the world did not write
            itself.

A link the reading cannot place stays bare, which is true of it. Nothing is marked hopeless.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import asking  # noqa: E402
import checking  # noqa: E402

from terraweaver import ontology, sentences, timeutil  # noqa: E402
from terraweaver.runtime import THE_WORLDS_OWN, format_result  # noqa: E402

# How many times the world hands its own failure back and asks for the next lines. Bounded for
# the reason a host's loop is: past a few goes the writer is writing against a record it has
# misunderstood, and going on spends the budget on copies of one error.
GOES = 3


def words_of(link) -> str:
    """The words the host said this link in — its description, and there is nothing else."""
    for said in (link.__dict__.get("descriptions") or []):
        if isinstance(said, str) and said.strip():
            return said.strip()
    return ""


def words_for(world) -> list:
    """Every relation type this record holds, the free one excepted.

    The free type is what a bare link is an instance of. Offered as an option it is the answer
    that always fits, and a reading that takes it has typed nothing.
    """
    out = []
    for name, cls in sorted(world.classes.items()):
        rel = cls._spec.get("relation")
        if rel and not rel.get("free"):
            out.append((name, cls, rel))
    return out


def look(world, subject, obj, words: str, picker) -> tuple:
    """Is one of the words this record has the word for this link? The word, and what was asked.

    Narrowed by the classes at the ends and never hidden by them: what a type has run between is
    what it has seen, not a rule about what it may see, and a word whose ends were written down
    from one example has to stay reachable for its second. The options are put fitting-first, and
    the rest follow.
    """
    known = words_for(world)
    if not known:
        # A record with no words for links has nothing to be asked about, and an empty question is
        # a call spent on a foregone answer.
        return None, {"asked": False, "why": "the record holds no relation types yet"}
    here = (type(subject).__name__, type(obj).__name__)

    def fits(rel: dict) -> bool:
        ends = (rel.get("from") or ["any"], rel.get("to") or ["any"])
        return all(name in side or "any" in side for name, side in zip(here, ends))

    ordered = [one for one in known if fits(one[2])] + [one for one in known if not fits(one[2])]
    options = {}
    for name, cls, rel in ordered:
        reads = rel.get("reads") or f"{rel['kind']} — {cls._spec.get('description', '')}"
        options[rel["kind"]] = reads[:200]
    options[asking.NOTHING_FITS] = asking.NOTHING_FITS_IS
    state = (f"{words}\n\nIt is about {subject.display_name()} (a {here[0]}) and "
             f"{obj.display_name()} (a {here[1]}).")
    question = asking.WHICH_WORD.format(a=subject.display_name(), b=obj.display_name())
    try:
        scored = picker.choose(state, question, options)
    except Exception as wrong:  # noqa: BLE001 - a look that fails is a look that found nothing
        return None, {"asked": True, "failed": str(wrong)[:200]}
    if not scored:
        return None, {"asked": True, "said": None}
    best = max(scored, key=scored.get)
    asked = {"asked": True, "options": list(options), "said": best,
             "sure": round(float(scored.get(best, 0.0)), 3)}
    if best == asking.NOTHING_FITS or best not in options:
        return None, asked
    return best, asked


def the_ask(world, subject, obj, words: str, word: str | None) -> str:
    """The one open question: the lines that record this link."""
    if word is None:
        class_ask = asking.MAKE_ONE
    else:
        cls = next((c for _, c, r in words_for(world) if r["kind"] == word), None)
        rel = cls._spec["relation"] if cls is not None else {}
        class_ask = asking.USE_ONE.format(
            word=word, reads=rel.get("reads") or cls._spec.get("description", "") if cls else "")
    return asking.ASK.format(
        a=subject.display_name(), a_is=type(subject).__name__,
        b=obj.display_name(), b_is=type(obj).__name__, words=words,
        class_ask=class_ask, held=sentences.held(world, subject, obj),
        classes=_classes_here(world))


def _classes_here(world) -> str:
    """The classes something can be looked up under, so a line does not name one that is not here.

    Shown rather than remembered: an engineer given an example that names a class this world has not
    got copies the example, and `Place.identify(...)` is a NameError in a world whose widest
    classes are Thing and Event.
    """
    from terraweaver import matching

    lines = []
    for name, cls in sorted(world.classes.items()):
        if cls._spec.get("relation") or cls._spec.get("own"):
            continue
        by = cls._spec.get("identified_by") or matching.NAME_KEYS.get(name) or "name"
        lines.append(f"    {name}.identify({by}=\"...\") — "
                     f"{(cls._spec.get('brief') or cls._spec.get('description') or '')[:70]}")
    return "\n".join(lines[:40])


def the_world_writes(runtime, code: str, **bound) -> dict:
    """Run what the reading wrote, by exactly the door a host's code goes through.

    Not a second interpreter, and that is the point of asking for code at all: what the reading
    may say is what a host may say, and every refusal the world makes of a host it makes of
    itself. The two things are bound before the code runs, so the reading never has to name
    them. The writes are the world's own, which is the lowest standing there is.
    """
    session = runtime.session(THE_WORLDS_OWN)
    session.namespace.update(bound)
    with ontology.stating("world"):
        return runtime.run(code, THE_WORLDS_OWN)


def typed_between(world, subject, obj) -> list:
    """Links of a real type joining these two now, either way round.

    How the reading is known to have worked, and it is read from the record rather than from what
    the code appeared to do: a line that ran without an error may still have written nothing.
    """
    out = []
    for name, cls, rel in words_for(world):
        for link in world.all(name, limit=None):
            if getattr(link, "valid_until", None) is not None:
                continue
            ends = {getattr(getattr(link, "subject", None), "id", None),
                    getattr(getattr(link, "object", None), "id", None)}
            if ends == {subject.id, obj.id}:
                out.append(link)
    return out


def end_the_bare_one(world, link) -> None:
    """The bare link is replaced by a typed one: end it, do not erase it.

    What was said is not unsaid. It held the host's own words and the moment they were said; it
    stops holding where the typed one begins, and anybody asking what this was before it was
    typed still has it.
    """
    with ontology.trusted_writes(), ontology.stating("world"):
        link.valid_until = timeutil.now()
        world.save(link)


def formalise_one(runtime, link, engineer, picker) -> dict:
    """One bare link, looked for and then written. Everything that happened, for the record."""
    world = runtime.world
    subject, obj = link.subject, link.object
    words = words_of(link)
    trace = {"words": words, "a": subject.display_name(), "b": obj.display_name(),
             "a_is": type(subject).__name__, "b_is": type(obj).__name__,
             # What was written and what the record answered, go by go. Kept because the answer is
             # the whole diagnosis: a run whose trace held only the code said "nothing came back"
             # about a line the world had refused for a reason nobody could see, and the reason had
             # to be found by writing the line again by hand.
             "wrote": [], "answered": [], "went": "", "typed": []}
    if not words:
        trace["went"] = "nothing was said about it"
        return trace
    word, asked = look(world, subject, obj, words, picker)
    trace["look"], trace["found"] = asked, word
    before = {name for name, _, _ in words_for(world)}
    said = the_ask(world, subject, obj, words, word)
    code, trouble = _code(engineer, said)
    for go in range(GOES):
        if not code:
            trace["went"] = f"nothing came back — {trouble}" if trouble else "nothing came back"
            break
        trace["wrote"].append(code)
        # Before it runs, and that is the whole point of checking here: a claim the sentence does
        # not bear out is never written, so there is nothing to take back. The lines go back to
        # whoever wrote them with what is wrong with them, which is the loop a refusal already uses.
        unsupported, asked_about = checking.what_is_wrong(
            picker, words, code, {"a": subject, "b": obj})
        trace.setdefault("checked", []).append(asked_about)
        if unsupported:
            trace["answered"].append(unsupported)
            if go == GOES - 1:
                trace["went"] = "not borne out by the words"
                break
            code, trouble = _code(engineer, _again(said, code, unsupported))
            continue
        got = the_world_writes(runtime, code, a=subject, b=obj)
        trace["answered"].append(format_result(got)[:2000])
        made = typed_between(world, subject, obj)
        if made:
            trace["went"] = "done" if got.get("ok") else "written, with a refusal on the way"
            trace["typed"] = [one.display_name() for one in made]
            trace["kind"] = type(made[0])._spec["relation"]["kind"]
            trace["defined"] = sorted({n for n, _, _ in words_for(world)} - before) or None
            end_the_bare_one(world, link)
            break
        if got.get("ok"):
            # It ran and joined nothing. Not a failure the world can report — there is no error
            # to hand back — so it is said plainly, which is what a host would be told.
            back = (f"{said}\n\nYou wrote this, and it ran without an error and joined nothing:"
                    f"\n\n{code}\n\n{format_result(got)[:1200]}\n\nThe two things are still "
                    f"unjoined. Write the lines that record the link between `a` and `b`.")
        else:
            back = (f"{said}\n\nYou wrote this, and the record answered:\n\n{code}\n\n"
                    f"{format_result(got)[:1500]}\n\nWrite the lines that still have to run — "
                    f"the ones that finished are done and must not be sent again. Nothing new "
                    f"is invented: only what the words above say.")
        if go == GOES - 1:
            trace["went"] = "gave up"
            break
        code, trouble = _code(engineer, back)
    else:
        trace["went"] = trace["went"] or "gave up"
    return trace


def _again(said: str, code: str, wrong: str) -> str:
    """The same question, with what the record said about the lines that came back."""
    return (f"{said}\n\nYou wrote this, and the record answered:\n\n{code}\n\n{wrong}\n\n"
            f"Write the lines that still have to run — the ones that finished are done and must "
            f"not be sent again. Nothing new is invented: only what the words above say.")


def _code(engineer, asked: str) -> tuple:
    """The lines, with whatever a model wraps them in taken off, and why nothing came if nothing did.

    Why nothing came back is part of the trace. An engineer that timed out, one that answered prose
    and one that answered an empty string are three different things to do something about, and all
    three read as "nothing came back" until the reason is kept.
    """
    try:
        raw = engineer.say(asking.SYSTEM, asked) or ""
    except Exception as wrong:  # noqa: BLE001 - a failure here leaves the words for a later pass
        return "", f"{type(wrong).__name__}: {str(wrong)[:200]}"
    if not raw.strip():
        return "", "the engineer answered with nothing at all"
    said = raw.strip()
    if said.startswith("```"):
        said = said.split("```")[1] if said.count("```") >= 2 else said.removeprefix("```")
        said = said.removeprefix("python").strip()
    if not said:
        return "", f"nothing but a fence came back: {raw.strip()[:200]}"
    return said, ""


def when_said(world, link) -> str:
    """When the host said this link, from the statements about it. The oldest wins.

    Read from the record rather than kept: the words of a link are a prose-fact like any other, and
    a statement carries when it was said.
    """
    try:
        said = world.facts.about(link.id, "descriptions")
    except Exception:  # noqa: BLE001 - a link whose statements cannot be read is as old as any
        return ""
    return min((str(one.stated_at) for one in said if one.stated_at), default="")


def formalise(runtime, engineer, picker, limit: int = 100) -> dict:
    """Every bare link nobody has read, in the order it was said, looked for and then written.

    The order is not housekeeping. Everything the world does with a second fact about the same two
    ends assumes the second one arrived second: a new employer ends the standing one, and the line
    the world offers when it refuses — end that one where this one begins — is written for a fact
    that starts later than what is there. Read newest-first, the same pair becomes unwritable: the
    2019 employment arrived against a 2023 one already standing, and there was no line that would
    have recorded it honestly. Measured, on the run of 2026-09-25: eight of nine typed, and the one
    that was not was that one.
    """
    bare = sorted(sentences.unread(runtime.world, limit),
                  key=lambda link: when_said(runtime.world, link))
    traces = []
    for link in bare:
        traces.append(formalise_one(runtime, link, engineer, picker))
    return {"read": traces,
            "typed": sum(1 for one in traces if one["typed"]),
            "joined": sum(1 for one in traces if one["typed"] and not one.get("defined")),
            "defined": sum(1 for one in traces if one.get("defined")),
            "left": sum(1 for one in traces if not one["typed"])}
