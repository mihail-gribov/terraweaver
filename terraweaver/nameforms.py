"""Which names are forms of one name.

"Mike" and "Michael" are the same name said two ways, and so are "Миша" and "Михаил" — and so
is "Gribov" written "Грибов". A name in another alphabet is not another name; it is the same one
written the way that language writes it. All of this is knowledge about language, not about a
person: it holds for everyone called Michael, it can be
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


# One alphabet is not another name. Enough to compare a name written either way; this is not a
# transliteration standard and doesn't try to be — it is here so "Миша Грибов" and "Mike Gribov"
# meet, which they plainly should.
CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def latin(text: str) -> str:
    """The same name in one alphabet, so two spellings of it can be compared."""
    return "".join(CYRILLIC.get(letter, letter) for letter in text.lower())


def _pairs() -> set:
    """Every pair the table and what has been learned make — in one alphabet, and with spelling
    choices taken out, so the table doesn't have to list "Mikhail" and "Mihail" separately."""
    out = {(skeleton(a), skeleton(b)) for a, b in KNOWN}
    for canonical, forms in FORMS.items():
        everything = [skeleton(canonical)] + [skeleton(f) for f in forms]
        out |= {(one, other) for one in everything for other in everything if one != other}
    return out


def by_table(first: str, second: str) -> bool:
    """The standard forms: a table of what people called X are also called."""
    return (skeleton(first), skeleton(second)) in _pairs()


# Two ways of writing one sound. People pick between them by habit — "Mikhail" on the passport,
# "Mihail" because it is easier to say back — and neither is a different name.
SPELLINGS = (("kh", "h"), ("ck", "k"), ("ph", "f"), ("c", "k"), ("yi", "i"), ("iy", "i"),
             ("yy", "y"))


def skeleton(name: str) -> str:
    """A name with its spelling choices taken out, so two spellings of it can be compared."""
    text = _norm(name)
    for written, plainer in SPELLINGS:
        text = text.replace(written, plainer)
    out = []
    for letter in text:  # "Anna" and "Ana" are one name written twice
        if not out or out[-1] != letter:
            out.append(letter)
    return "".join(out)


def by_spelling(first: str, second: str) -> bool:
    """The same name, spelled the way whoever wrote it preferred."""
    return skeleton(first) == skeleton(second)


def by_initial(first: str, second: str) -> bool:
    """A name written as an initial: "M. Gribov" is Michael Gribov, unless two Ms are about."""
    short, long = sorted((first, second), key=len)
    return len(short.rstrip(".")) == 1 and long.startswith(short.rstrip("."))


# How one given name is recognised as another. The standard ways are here; the world can add its
# own for what it meets — a house spelling, a name from a language this table doesn't cover —
# and those are procedures like any other (procedures.py), kept because they earned their place.
MATCHERS = [by_table, by_spelling, by_initial]


def one_name(first: str, second: str) -> bool:
    """Whether these two are forms of one given name, by any rule the world knows."""
    left, right = _norm(first), _norm(second)
    return left == right or any(match(left, right) for match in MATCHERS)


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
        return left[-1] == right[-1] or skeleton(left[-1]) == skeleton(right[-1])
    return True


def _norm(text: str) -> str:
    return " ".join(latin(str(text)).split())
