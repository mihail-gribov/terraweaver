"""Statements, the code an ideal host writes for each, and what that statement must change.

The benchmark's own facts, in its own order, with nothing selected. Each step says what the
statement *changed* — what the world gained and what stopped holding — not what the whole world
looks like afterwards. A step then reads as one fact and one consequence, stays true however many
steps come before it, and a failure points at the statement that caused it.

    gained   links that were not there and now hold
    ended    links that were holding and now do not — superseded, not erased

The code is what an ideal host writes **through the type-first door, as this world stands now**:
one word for the type, declared before it is used. It was written when a two-word kind was
ordinary and an unknown one made its own type; neither is true any more — a word with a space in
it is a sentence about the fact (`sentences.py`), and `initiative.MAKES_TYPES` is off. Said the
other way, through the door that takes words, the same six are
`experiments/story/new_doors.py`, checked against this same table.
"""

STEPS = [
    {
        "said": "Thomas Kyd was born in the city of London.",
        "code": 'world.define_relation("born_in", "the place somebody was born", nature="related_to", '
                'cardinality="many-to-one", over_time=False)\n'
                'Person.ensure(full_name="Thomas Kyd")'
                '.relate(Thing.ensure(name="London"), "born_in")',
        "gained": [("born_in", "Thomas Kyd", "London")],
    },
    {
        "said": "The chairperson of Fatah is Mahmoud Abbas.",
        "code": 'world.define_relation("chairperson_of", "the body somebody chairs", nature="related_to", '
                'cardinality="many-to-one", over_time=True)\n'
                'Person.ensure(full_name="Mahmoud Abbas")'
                '.relate(Thing.ensure(name="Fatah"), "chairperson_of")',
        "gained": [("chairperson_of", "Mahmoud Abbas", "Fatah")],
    },
    {
        "said": "Amy Winehouse died in the city of Camden Town.",
        "code": 'world.define_relation("died_in", "the place somebody died", nature="related_to", '
                'cardinality="many-to-one", over_time=False)\n'
                'Person.ensure(full_name="Amy Winehouse")'
                '.relate(Thing.ensure(name="Camden Town"), "died_in")',
        "gained": [("died_in", "Amy Winehouse", "Camden Town")],
    },
    {
        "said": "Hines Ward plays the position of wide receiver.",
        "code": 'world.define_relation("plays_position", "the position somebody plays in their sport", nature="related_to", '
                'cardinality="many-to-one", over_time=True)\n'
                'Person.ensure(full_name="Hines Ward")'
                '.relate(Thing.ensure(name="wide receiver"), "plays_position")',
        "gained": [("plays_position", "Hines Ward", "wide receiver")],
    },
    {
        "said": "Thomas Kyd was born in the city of Leeds.",
        "why": "a birthplace has one value: the later telling corrects the earlier",
        "code": 'Person.get(full_name="Thomas Kyd")'
                '.relate(Thing.ensure(name="Leeds"), "born_in")',
        "gained": [("born_in", "Thomas Kyd", "Leeds")],
        "ended": [("born_in", "Thomas Kyd", "London")],
    },
    {
        "said": "Hines Ward plays the position of cornerback.",
        "why": "a position is held one at a time: the new one takes over",
        "code": 'Person.get(full_name="Hines Ward")'
                '.relate(Thing.ensure(name="cornerback"), "plays_position")',
        "gained": [("plays_position", "Hines Ward", "cornerback")],
        "ended": [("plays_position", "Hines Ward", "wide receiver")],
    },
]
