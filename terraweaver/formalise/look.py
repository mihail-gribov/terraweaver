"""Is there already a word for this kind of link? A closed question, to the picker.

The step that makes a vocabulary converge. Without it every fact describes a new relation, and a
world ends up holding two words for one idea, each answering for half of it — measured, one run held
`ChairpersonOf` beside `DirectorOf`. With it, experiment 01 made `capital_of` once and joined it
from the second fact in every run.

The options are the words the record holds, narrowed by the classes at the two ends and never hidden
by them: what a type has run between is what it has seen, not a rule about what it may see, and a
word whose ends were written down from one example has to stay reachable for its second. Fitting
ones come first and the rest follow, and a way out is always among them.
"""
from terraweaver import prompts


def words_for(world) -> list:
    """Every relation type this record holds, the free one excepted — (class name, class, relation).

    The free type is what a bare link is an instance of. Offered as an option it is the answer that
    always fits, and a look that takes it has typed nothing.
    """
    out = []
    for name, cls in sorted(world.classes.items()):
        rel = cls._spec.get("relation")
        if rel and not rel.get("free"):
            out.append((name, cls, rel))
    return out


def look(world, subject, obj, words: str, picker) -> tuple:
    """The word this record already has for this link, or None — and what was asked, for the trace."""
    known = words_for(world)
    if not known:
        # Nothing to be asked about, and an empty question is a call spent on a foregone answer.
        return None, {"asked": False, "why": "the record holds no relation types yet"}
    here = (type(subject).__name__, type(obj).__name__)

    def fits(rel: dict) -> bool:
        ends = (rel.get("from") or ["any"], rel.get("to") or ["any"])
        return all(name in side or "any" in side for name, side in zip(here, ends))

    ordered = [one for one in known if fits(one[2])] + [one for one in known if not fits(one[2])]
    options = {}
    for _, cls, rel in ordered:
        reads = rel.get("reads") or f"{rel['kind']} — {cls._spec.get('description', '')}"
        options[rel["kind"]] = reads[:200]
    options[prompts.NONE_OF_THESE] = prompts.NONE_OF_THESE_IS
    state = (f"{words}\n\nIt is about {subject.display_name()} (a {here[0]}) and "
             f"{obj.display_name()} (a {here[1]}).")
    question = prompts.WHICH_WORD.format(a=subject.display_name(), b=obj.display_name())
    try:
        scored = picker.choose(state, question, options)
    except Exception as wrong:  # noqa: BLE001 - a look that fails is a look that found nothing
        return None, {"asked": True, "failed": str(wrong)[:200]}
    if not scored:
        return None, {"asked": True, "said": None}
    best = max(scored, key=scored.get)
    asked = {"asked": True, "options": list(options), "said": best,
             "sure": round(float(scored.get(best, 0.0)), 3)}
    if best == prompts.NONE_OF_THESE or best not in options:
        return None, asked
    return best, asked
