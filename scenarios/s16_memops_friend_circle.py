DESCRIPTION = """MemOps B01 (forget, bridge entities): the owner's best friend Darren Liu, his birthday, his older
brother Kevin (VP at a finance firm in Chicago) and his girlfriend Naomi — relationships between
people the owner knows, not only with the owner. Then one detail (helping Darren move furniture
into a storage unit) is to be forgotten while everything else stays."""

SETUP = ""

CONVERSATIONS = [
    [
        "Using my world (terraweaver): Hey, I want to tell you about my closest friend so you can keep some things in mind for me. My best friend is Darren Liu. We've been close since college, like over eight years now. He's genuinely the one person I'd call at 3 a.m. if something went wrong. We both live in Portland and we grab ramen together at least twice a month at this spot on Hawthorne.\n\nYeah, one important thing — Darren's birthday is October 17th. I always want to make sure I remember that. I blanked on it one year and felt terrible about it. So please keep that noted down for me. I want to plan something nice this year, maybe get a reservation at a good restaurant or find a thoughtful gift. Just having the date saved would help a lot.\n\nThat would be great, thanks. Oh, also — Darren's older brother Kevin just got promoted to VP at some finance firm in Chicago. Darren mentioned it when we were hanging out recently. He seemed proud of Kevin but also a little competitive about it, which is very on-brand for Darren. Kevin's apparently doing really well for himself out there. I think Darren sometimes measures himself against his brother's career trajectory.\n\nThat's a really good point, actually. I hadn't thought about it that way, but it makes sense. Darren has always been driven but he gets in his own head sometimes. Anyway, I really appreciate you keeping track of all this. These details matter to me because Darren is basically family at this point. Having someone remember the little things about my friendships is helpful."
    ],
    [
        "Using my world (terraweaver): So picking up where we left off about Darren — Darren's girlfriend Naomi has been with him for about two years now. She's apparently against the Seattle move. Darren told me about it and he seemed really torn up. I think the relationship tension is weighing on him heavily. I felt kind of down for days after that conversation because it made the whole Seattle thing feel more real and complicated.\n\nThanks, I might take you up on that. On a different note, I helped Darren move some furniture into a storage unit in mid-April because he was downsizing his apartment. It was a pretty physical day — we loaded up a bunch of stuff, drove it over, and got everything squared away. Afterwards we grabbed beers at this great little dive bar nearby. I always prefer those hole-in-the-wall spots over trendy cocktail bars.\n\nYeah, those low-key hangouts are really my thing. I much prefer a quiet corner booth or a no-frills bar over anything flashy. It's just easier to actually talk and connect when the environment isn't trying to compete for attention. Anyway, Darren told me last week that he's leaning toward taking the Seattle job. He hasn't officially accepted yet but said he'd probably decide by end of May.\n\nHonestly, the thought of losing those weeknight hangouts really gets to me. But I told Darren I'd support whatever he chooses. That's what matters most. I've been trying not to dwell on it too much. We've got a strong enough friendship that distance won't break it, but it'll definitely change the rhythm of things. I just want to be a good friend through this whole process.\n\nActually, you can forget the storage unit thing. That's completely done and over with — no need to keep track of it. The furniture is all moved, the storage is sorted, and there's nothing left to follow up on. Just drop that from what you're remembering for me. Everything else about Darren — the birthday, Kevin, Naomi, the Seattle decision — all of that is still relevant and important."
    ],
    [
        "Using my world (terraweaver): So I've been thinking more about what to do for Darren's birthday this year. October 17th is on a Friday, which is perfect for a dinner out. I want to find a really good spot — nothing too loud or trendy, just great food and a comfortable atmosphere. Maybe somewhere with a private dining area or at least a quieter section. Any ideas on how to start looking?\n\nDarren loves Japanese food, so maybe a nice izakaya or omakase spot. Something a step up from our usual ramen place on Hawthorne but still with that cozy vibe. I'd probably want to keep it to just the two of us, or maybe invite Naomi since they've been together a couple years. I'd want Darren to feel celebrated without it being an overwhelming production.\n\nYeah, that would be helpful. I also want to think about a gift. Darren's been stressed about the Seattle decision and the whole thing with Kevin making VP — I think he's been feeling the pressure of comparison. Maybe something that acknowledges his own accomplishments or just shows I appreciate him. Not career-related though, something more personal and thoughtful.\n\nA photo book is a great idea actually. We have tons of pictures from college and all the Portland years. Oh, by the way, I was looking at a group chat earlier and someone mentioned that Darren's brother Kevin's birthday is October 12th. I don't need to track that though — Kevin's not really in my circle, that's Darren's family stuff. Just Darren's birthday matters to me.\n\nLet's start with the restaurant search first since reservations at good omakase places fill up fast. I want to lock that down well in advance. For the photo book I have more time. Also, just to confirm — you've still got all the key Darren details noted, right? His birthday, Naomi, Kevin's VP thing, the Seattle decision timeline? Those are all still important to me."
    ]
]

EXPECT = """
darrens = [p for p in Person.all(limit=None) if "darren" in p.full_name.lower()]
assert len(darrens) == 1, f"expected one Darren, got {len(darrens)}"
assert not world.comments(contains="storage"), "the storage-unit detail is still current"
"""

# Asked afterwards, each in a fresh conversation: (question, must mention, must not mention).
PROBES = [
    ('Using my world (terraweaver): summarize everything you know about Darren Liu — how we know each other, his birthday and the people in his life.',
     ['October 17', 'Kevin', 'Naomi'], []),
    ('Using my world (terraweaver): what have I helped Darren with lately?',
     [], ['storage']),
]

LEVEL = "hard"
