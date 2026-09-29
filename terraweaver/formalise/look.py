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
        # "None of these" is put to the same question about the word that came closest, because the
        # look refuses words it should not: measured 2026-09-30 over 25 refusals from two readings of
        # one world, nine were of a word that was the same idea — `famous for` refused against
        # `famous_for`, `child` against `child_of`, `founded` against `founded_by`. Each of those
        # became another word for an idea the record already had, and two words for one idea switch
        # supersession off. Asked as two words the decision model got 13 of those 14 right, and the
        # one it missed is a boundary a person would argue about too.
        if nearest is not None and says_the_same(words, nearest, picker):
            asked["taken"] = f"{nearest} — the look passed it over and it says the same"
            return nearest, asked
        return None, asked
    if CHECKED and not says_the_same(words, best, picker):
        # A word that means something else is not this link's word, and a new one is honest about
        # that. `take_in` moves the links if somebody later decides the two words are one idea.
        asked["refused"] = f"{best} does not say what the words say"
        return None, asked
    return best, asked


# How sure the decision model has to be that the two are different ideas before the word is taken
# away. Measured 2026-09-30 over twenty-four pairs the look had actually answered, hand-labelled:
# asked about the two words it was right 24/24 and never wrong at all, so the bar is here for
# safety and not because anything needed filtering. It stays because twenty-four pairs is twenty-four
# pairs, and because the cost of a wrong refusal has been measured — one reading went from 27 words
# to 48 when refusals ran unchecked.
A_DIFFERENT_IDEA = 0.75


def says_the_same(words: str, word: str, picker) -> bool:
    """Are the words that were said and the word the look picked one idea, or two?

    **Asked about the two words, and not about the account.** The first version of this asked "is
    «author of» what the account says?" and was measured wrong on 4 of 24 pairs — confidently, at
    0.93 that `performed` and `performed_by` are different ideas and 0.99 for `founded` and
    `founder_of`. Refusing those sent the engineer off to coin near-copies, and one reading's
    vocabulary went from 27 words to 48. Asked as two words side by side — "are those the same idea,
    one of them said differently?" — the same model was right **24 of 24** and never wrong.

    So the question is about words, which is what it is. A rule that chopped endings and skipped
    prepositions was tried and is gone: no list of endings and function words is ever complete, a
    real stemmer fails on exactly the hard case (`founded` → `found` while `founder` stays
    `founder`), and any of it ties the world to one language. A closed question does not.

    The one thing still done to the words is turning `_` into a space, and it is worth its place:
    measured on the same pairs, `performed_by` written out as "performed by" gives 24/24 and left as
    it is gives 20/24, the four misses all sitting at 0.50–0.55 — the model hesitating rather than
    being wrong, which is also why the threshold below catches them. This is not morphology and not
    a language: an underscore is **our own** spelling of a word, and undoing it is undoing ours.
    """
    said_as_words = word.replace("_", " ")
    state = (f"Two words a record could file one fact under:\n"
             f"    \u00ab{str(words).replace('_', ' ').strip()}\u00bb\n"
             f"    \u00ab{said_as_words}\u00bb")
    question = "Are those two the same idea, one of them said differently?"
    options = {"says_so": "yes — one idea, said differently: a different ending, a preposition, "
                          "the same verb as a noun",
               prompts.NONE_OF_THESE: "no — two different ideas, or the same idea from the other "
                                      "end, which is its own word and not this one"}
    try:
        scored = picker.choose(state, question, options)
    except Exception:  # noqa: BLE001 - a check that cannot run is not a word refused
        return True
    if not scored:
        return True
    against = float(scored.get(prompts.NONE_OF_THESE, 0.0))
    return not (max(scored, key=scored.get) == prompts.NONE_OF_THESE
                and against >= A_DIFFERENT_IDEA)
