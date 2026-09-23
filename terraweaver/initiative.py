"""What the world is allowed to do on its own.

Every switch here is the world acting without being asked — not checking, not asking, not
refusing, but changing something and carrying on. Each one was added for a good reason and each
one, on the material we have measured, has at some point changed a fact into a different fact
while every count said the run was clean.

They are gathered in one file and off by default so that adding facts can be watched without
them: what the agent says is what the world holds, and anything that is wrong is the agent's
doing or the world's refusal, never a third party. Automation goes back on one switch at a
time, against a world we can already read.

Turning one on is one line, here. Nothing reads these except the site it names.
"""

# An unknown relation word makes a type of its own, with the world guessing its nature.
# Off: `relate(a, b, "born_in")` raises and names the types there are; the agent defines it.
MAKES_TYPES = False

# A label moves a link to the type that label belongs to — "husband" written as kin becomes a
# partner. Off: the link is recorded under the type that was asked for.
REROUTES_BY_LABEL = False

# A name settled once is remembered, so the same name later means the same entity without
# asking. Off: every name is resolved as it comes, and an ambiguity is a question.
LEARNS_NAMES = False

# Two words read as one idea by embedding similarity, so the second is recorded as the first.
# Off: the world says what it noticed and makes the type that was asked for.
#
# Turning this on needs more than the switch. The text it compares is a description the world
# wrote itself from a template, so the score is mostly about the template: "director of" against
# "chairperson of" is 0.708 as words and 0.853 inside the frame, and the bar is 0.82. That is
# how Tony Hall became the BBC's chairperson. See docs/decisions.md, "The world's own
# description was the evidence it judged by".
MERGES_MEANING = False

# An unknown relation word is read as the nearest word this world already has, by spelling
# distance. Off: it raises, and the near one is named where the type is defined.
#
# Same warning, worse arithmetic: "worked_in_city" scores 0.769 against "born_in_city" and
# "died_in_city" 0.667, on a shared "_in_city" that says nothing about meaning. A recorder wrote
# both correctly four times each and the world rewrote both, four times each.
TAKES_NEAR_WORD = False

# Not structure, and not here: correcting a misspelt attribute name (`ontology.take_as`) names
# the same attribute by its right spelling and changes nothing about what the world holds.
