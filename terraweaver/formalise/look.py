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

# What the look answers is a hypothesis about meaning, so it is checked the way every other claim
# here is checked: the word is spelled out and put beside the words that were said, and the decision
# model is asked whether they say the same. Measured 2026-09-29 over 136 readings of one world, this
# is not a formality — the look answered `author_of` for facts whose words were `performed`, four
# times, at 0.95, 0.92, 0.83 and 0.62. A fact under a word that means something else is worse than a
# second word for one idea: the duplicate still holds the fact with its own meaning and can be
# merged, while `Lou Reed author_of Blood on the Tracks` cannot be found by anybody asking who
# performed it, and supersedes the wrong things.
#
# A margin for "none of these" was tried first and is gone: it fired three times in 136, narrowed no
# vocabulary (10 words made against 9), and it leaned the wrong way — towards taking an existing
# word, which is the error this check exists to catch.
CHECKED = True


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
             "nearest": nearest, "nearest_sure": round(float(words_here.get(nearest, 0.0)), 3)
             if nearest else None}
    if best == prompts.NONE_OF_THESE or best not in options:
        return None, asked
    if CHECKED and not says_the_same(words, best, picker):
        # A word that means something else is not this link's word, and a new one is honest about
        # that. `take_in` moves the links if somebody later decides the two words are one idea.
        asked["refused"] = f"{best} does not say what the words say"
        return None, asked
    return best, asked


# How sure the check has to be that the word is a *different idea* before it refuses it. The two
# mistakes are not equal and both were measured. Refusing a word that fitted sends the engineer off
# to coin a near-copy: at no threshold at all, one reading of one world went from 27 words to 48 —
# `performed`, `performed_as`, `performed_at`, `performed_by`, `performed_on` for one idea, and four
# words where `plays_position` had stood. Letting a wrong word through costs the fact the question
# asks for. So the doubt goes to the word, and only a clear verdict takes it away.
A_DIFFERENT_IDEA = 0.75


def _shares_a_stem(words: str, word: str) -> bool:
    """Whether the account and the word are plainly the same idea said differently.

    Decided without a model, because it needs none and because the model gets it wrong: `performed`
    against `performed_by` and `founded` against `founder_of` were both refused as different ideas,
    and each refusal became another word for an idea the record already had. A shared leading stem
    is not a guess about meaning — it is the same verb, and what follows it is the direction or the
    role, which the type's own ends carry.
    """
    def stems(text: str) -> list[str]:
        out = []
        for part in str(text).replace("_", " ").lower().split():
            if part in ("of", "by", "in", "at", "on", "for", "to", "the", "a", "as", "with"):
                continue
            out.append(part.rstrip("s").removesuffix("ed").removesuffix("er").removesuffix("ing"))
        return out

    said, mine = stems(words), stems(word)
    return bool(said and mine and (said[0] == mine[0] or set(said) & set(mine)))


def says_the_same(words: str, word: str, picker) -> bool:
    """Does the word the look picked say what was said? One closed question, to the decision model.

    Asked as a phrase beside the account, which is the form that works here (`check._asking`): what
    is being compared is a word against words, not a sentence against a claim. A check that cannot
    be asked lets the word stand — the look's answer is the world's best guess and a broken checker
    is no reason to throw it away.
    """
    if _shares_a_stem(words, word):
        return True
    said_as_words = word.replace("_", " ")
    question = (f"The record would file this under the word «{said_as_words}». Is that what the "
                f"account says joins these two?")
    options = {"says_so": f"yes — «{said_as_words}» is what the account says, or plainly the same "
                          f"thing in other words",
               prompts.NONE_OF_THESE: f"no — the account says something else, and "
                                      f"«{said_as_words}» is a different idea"}
    try:
        scored = picker.choose(prompts.IS_IT_SAID.format(words=words), question, options)
    except Exception:  # noqa: BLE001 - a check that cannot run is not a word refused
        return True
    if not scored:
        return True
    against = float(scored.get(prompts.NONE_OF_THESE, 0.0))
    return not (max(scored, key=scored.get) == prompts.NONE_OF_THESE
                and against >= A_DIFFERENT_IDEA)
