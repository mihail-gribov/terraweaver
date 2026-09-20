"""Which names are forms of one name.

"Mike" and "Michael" are the same name said two ways, and so are "Миша" and "Михаил". That is
knowledge about language, not about a person: it holds for everyone called Michael, it can be
checked, and nobody needs to confirm it. "Sota" for Sasha is the opposite — a fact about one
person, true only because someone in their life decided it was.

The world treats the two differently, and the difference matters because names decide who is
who. A known form is accepted as another way of saying the same name. An unknown nickname waits
for someone to vouch for it, because accepting it would quietly merge two people and be very
hard to unpick afterwards (assembly.py).

The host is a language model and knows all this better than any table: it is asked to look
people up by the fullest form of the name it knows, and canonicalising "Миша" into "Михаил
Грибов" is its job, not the world's. This table is the net under that — for the forms that slip
through, and for judging what the world itself proposes.

The table below is small on purpose: the common cases, in the languages this world is used in.
When the model inside the world knows a pair this table doesn't, that is a judgement about
language rather than about the person — recorded once, with its own source, and reusable for
everyone. `KNOWN` is where such an answer lands.
"""

# Canonical form -> what people are also called. Both directions are matched.
FORMS = {
    "michael": ["mike", "mikey", "mick", "миша", "михаил", "мишa"],
    "mikhail": ["misha", "миша", "михаил"],
    "robert": ["bob", "bobby", "rob", "robbie"],
    "william": ["will", "bill", "billy", "liam"],
    "elizabeth": ["liz", "beth", "betty", "eliza", "lisa"],
    "katherine": ["kate", "katie", "kathy", "kat", "catherine"],
    "alexander": ["alex", "sasha", "саша", "александр", "шура"],
    "alexandra": ["alex", "sasha", "саша", "александра"],
    "anna": ["anne", "annie", "ann", "аня", "анна"],
    "maria": ["mary", "masha", "маша", "мария"],
    "richard": ["rick", "dick", "richie"],
    "james": ["jim", "jimmy", "jamie"],
    "joseph": ["joe", "joey"],
    "daniel": ["dan", "danny"],
    "thomas": ["tom", "tommy"],
    "barbara": ["barb", "barbie"],
    "margaret": ["maggie", "meg", "peggy"],
    "nikolai": ["kolya", "коля", "николай"],
    "dmitry": ["dima", "дима", "дмитрий"],
    "ekaterina": ["katya", "катя", "екатерина"],
}

# Pairs the model worked out that the table didn't have. Knowledge about language, so it is kept
# once and used for everyone — not a fact about whoever prompted the question.
KNOWN: set = set()


def _pairs() -> set:
    out = set(KNOWN)
    for canonical, forms in FORMS.items():
        everything = [canonical] + list(forms)
        for one in everything:
            for other in everything:
                if one != other:
                    out.add((one, other))
    return out


def one_name(first: str, second: str) -> bool:
    """Whether these two are known forms of one given name."""
    return (_norm(first), _norm(second)) in _pairs()


def learn(first: str, second: str) -> None:
    """Record a pair the table didn't have — what the world worked out about the language."""
    KNOWN.add((_norm(first), _norm(second)))
    KNOWN.add((_norm(second), _norm(first)))


def same_name(full: str, other: str) -> bool:
    """Whether two full names are the same name said differently.

    Compared part by part: the given names must be one name (the same word, or known forms of
    it), and any surnames present must agree. "Mike Gribov" is "Michael Gribov"; "Mike Orlov"
    is not.
    """
    left, right = _norm(full).split(), _norm(other).split()
    if not left or not right:
        return False
    if not (left[0] == right[0] or one_name(left[0], right[0])):
        return False
    if len(left) > 1 and len(right) > 1:
        return left[-1] == right[-1]
    return True


def _norm(text: str) -> str:
    return " ".join(str(text).lower().replace("ё", "е").split())
