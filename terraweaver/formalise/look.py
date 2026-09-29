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

# How far ahead "none of these" has to be before a new word is made. The two mistakes here do not
# cost the same, and the measurement says so: a second word for one idea puts the two tellings of a
# fact into different types, and **supersession works inside a type**, so neither ends the other and
# the world answers with whichever it meets first. Measured 2026-09-29 on the FactConsolidation
# slice: `Madonna → AssociatedWith` beside `The Beatles → PerformedBy`, both standing, the question
# "who performed Past Masters" answered with the earlier one — and that shape is most of the
# difference between 64% and 35%. Joining a word that is nearly right costs far less: the link is
# there, it is found, and `take_in` can move it when somebody decides. So the doubt goes to the
# existing word, and a new one is made only when nothing here is close.
A_NEW_WORD_NEEDS = 0.15


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
    words_here = {word: p for word, p in scored.items()
                  if word in options and word != prompts.NONE_OF_THESE}
    nearest = max(words_here, key=words_here.get) if words_here else None
    asked = {"asked": True, "options": list(options), "said": best,
             "sure": round(float(scored.get(best, 0.0)), 3),
             # Kept so the margin below can be argued from data rather than taste.
             "nearest": nearest, "nearest_sure": round(float(words_here.get(nearest, 0.0)), 3)
             if nearest else None}
    if best == prompts.NONE_OF_THESE or best not in options:
        if nearest is not None:
            ahead = float(scored.get(best, 0.0)) - float(words_here[nearest])
            if ahead <= A_NEW_WORD_NEEDS:
                # Close, so the word this record already has wins: two words for one idea is the
                # expensive mistake, and joining a near word is the cheap one.
                asked["taken"] = f"{nearest} — {round(ahead, 3)} behind 'none of these'"
                return nearest, asked
        return None, asked
    return best, asked
