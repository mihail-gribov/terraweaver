"""Statements, the code an ideal host writes for each, and what that statement must change.

The benchmark's own facts, in its own order, with nothing selected. Each step says what the
statement *changed* — what the world gained and what stopped holding — not what the whole world
looks like afterwards. A step then reads as one fact and one consequence, stays true however many
steps come before it, and a failure points at the statement that caused it.

    gained   links that were not there and now hold
    ended    links that were holding and now do not — superseded, not erased
"""

STEPS = [
    {
        "said": "Thomas Kyd was born in the city of London.",
        "code": 'Person.ensure(full_name="Thomas Kyd")'
                '.relate(Thing.ensure(name="London"), "born in")',
        "gained": [("born_in", "Thomas Kyd", "London")],
    },
    {
        "said": "The chairperson of Fatah is Mahmoud Abbas.",
        "code": 'Person.ensure(full_name="Mahmoud Abbas")'
                '.relate(Thing.ensure(name="Fatah"), "chairperson of")',
        "gained": [("chairperson_of", "Mahmoud Abbas", "Fatah")],
    },
    {
        "said": "Amy Winehouse died in the city of Camden Town.",
        "code": 'Person.ensure(full_name="Amy Winehouse")'
                '.relate(Thing.ensure(name="Camden Town"), "died in")',
        "gained": [("died_in", "Amy Winehouse", "Camden Town")],
    },
    {
        "said": "Hines Ward plays the position of wide receiver.",
        "code": 'Person.ensure(full_name="Hines Ward")'
                '.relate(Thing.ensure(name="wide receiver"), "plays position")',
        "gained": [("plays_position", "Hines Ward", "wide receiver")],
    },
    {
        "said": "Thomas Kyd was born in the city of Leeds.",
        "why": "a birthplace has one value: the later telling corrects the earlier",
        "code": 'Person.get(full_name="Thomas Kyd")'
                '.relate(Thing.ensure(name="Leeds"), "born in")',
        "gained": [("born_in", "Thomas Kyd", "Leeds")],
        "ended": [("born_in", "Thomas Kyd", "London")],
    },
    {
        "said": "Hines Ward plays the position of cornerback.",
        "why": "a position is held one at a time: the new one takes over",
        "code": 'Person.get(full_name="Hines Ward")'
                '.relate(Thing.ensure(name="cornerback"), "plays position")',
        "gained": [("plays_position", "Hines Ward", "cornerback")],
        "ended": [("plays_position", "Hines Ward", "wide receiver")],
    },
]
