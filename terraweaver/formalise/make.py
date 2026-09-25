"""The lines that record one fact. An open question, to the engineer.

Code, not a description the world renders. It runs through the door a host's code runs through, so
every refusal the world makes of a host it makes of this too, and the engineer can express whatever a
host could rather than whatever a hand-written translator thought of. Asked for data instead, the
sentence door carried a translator of its own, and the translator is where `nature` and `over_time`
survived long after the structure had dropped them.

Only what the look could not place is asked to define anything: the last block of the question
reads either "the word is already here, use it" or "declare one first".
"""
from terraweaver import matching, prompts, sentences
from terraweaver.formalise.look import words_for


def question(world, subject, obj, words: str, word: str | None) -> str:
    """The one open question for this fact: with the word the look found, or with none."""
    if word is None:
        last = prompts.NO_WORD_YET
    else:
        cls = next((c for _, c, r in words_for(world) if r["kind"] == word), None)
        rel = cls._spec["relation"] if cls is not None else {}
        reads = (rel.get("reads") or cls._spec.get("description", "")) if cls is not None else ""
        last = prompts.THE_WORD_IS_HERE.format(word=word, reads=reads)
    return prompts.A_LINK_SAID.format(
        a=subject.display_name(), a_is=type(subject).__name__,
        b=obj.display_name(), b_is=type(obj).__name__, words=words,
        class_ask=last, held=sentences.held(world, subject, obj), classes=classes_here(world))


def classes_here(world) -> str:
    """The classes something can be looked up under, so a line does not name one that is not here.

    Shown rather than remembered: an engineer given an example that names a class this world has not
    got copies the example, and `Place.identify(...)` is a NameError in a world whose widest classes
    are Thing and Event.
    """
    lines = []
    for name, cls in sorted(world.classes.items()):
        if cls._spec.get("relation") or cls._spec.get("own"):
            continue
        by = cls._spec.get("identified_by") or matching.NAME_KEYS.get(name) or "name"
        lines.append(f"    {name}.identify({by}=\"...\") — "
                     f"{(cls._spec.get('brief') or cls._spec.get('description') or '')[:70]}")
    return "\n".join(lines[:40])


def lines(engineer, asked: str) -> tuple:
    """The code, with whatever a model wraps it in taken off — and why nothing came, if nothing did.

    An engineer that timed out, one that answered prose and one that answered an empty string are
    three different things to do something about, and all three read as "nothing came back" until
    the reason is kept. One of them was a budget spent thinking, which is `outside.Nemotron`'s room.
    """
    try:
        raw = engineer.say(prompts.WRITING_A_LINK, asked) or ""
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


def again(asked: str, code: str, answer: str) -> str:
    """The same question, with what the record said about the lines that came back."""
    return prompts.WRITE_AGAIN.format(asked=asked, code=code, answer=answer)


def joined_nothing(asked: str, code: str, answer: str) -> str:
    """It ran and joined nothing: no error to hand back, so it is said plainly, as to a host."""
    return prompts.JOINED_NOTHING.format(asked=asked, code=code, answer=answer)
