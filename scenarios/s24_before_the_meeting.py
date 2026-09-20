DESCRIPTION = """The commonest hard task there is: someone is about to see a person they last saw
months ago, in a world with a year of other people in it. What do they need to remember — what was
said last time, what changed since, what was promised, what not to bring up. Every piece is in the
world, none of it is in one place, and the answer is wrong if it is stale."""

SETUP = """
# A year of other people, so the answer has to be found rather than read.
firsts = ["Ana", "Ben", "Clara", "Dmitry", "Elena", "Farid", "Greta", "Hugo", "Iris", "Jonas",
          "Kira", "Lars", "Maya", "Nils", "Olga", "Pavel", "Rosa", "Sven", "Tara", "Vera"]
lasts = ["Adler", "Borg", "Cruz", "Dahl", "Ek", "Faber", "Holt", "Ibsen", "Jung", "Kahn"]
firms = [Organization.new(name=n, industry=i) for n, i in
         [("Northwind Health", "Health"), ("Cobalt Analytics", "Data Analytics"),
          ("Pike Logistics", "Logistics"), ("Verso Energy", "Energy"), ("Halden Labs", "Research")]]
crowd = []
for i in range(40):
    person = Person.new(full_name=f"{firsts[i % 20]} {lasts[(i * 3 + i // 20) % 10]}",
                        email=f"p{i}@example.com")
    person.relate(firms[i % 5], "membership", title="analyst", primary=True,
                  starts=date(2026, 1 + (i % 9), 1 + (i % 27)))
    crowd.append(person)
for i in range(60):
    Event.new(title=f"catch-up {i}", kind="meeting", status="confirmed",
              start_time=now() - timedelta(days=(i * 5) % 300), participants=[crowd[(i * 7) % 40]])

# The person this is about, and the trail they left.
sofia = Person.new(full_name="Sofia Bergmann", email="sofia.bergmann@northwind.example",
                   phone="+15550114455")
sofia.relate(firms[0], "membership", title="research lead", primary=True, starts=date(2024, 5, 6))
sofia.relate(owner, "social", label="former colleague")
last_time = Event.new(title="lunch with Sofia", kind="meeting", status="confirmed",
                      start_time=now() - timedelta(days=142), participants=[sofia],
                      notes="talked about her move into research management")
sofia.comment("asked me to send the Kaplan paper — still haven't", when=now() - timedelta(days=142))
sofia.comment("her son started school this autumn", when=now() - timedelta(days=30))
sofia.comment("don't bring up the Pike Logistics job — she was turned down", when=now() - timedelta(days=100),
              permanent=True)
sofia.comment("was on parental leave until March", when=now() - timedelta(days=320),
              until=now() - timedelta(days=180))

# What changed since that lunch, recorded later and from elsewhere.
sofia.organization = firms[4]
job = [r for r in sofia.relations("membership", any_time=True) if r.object == firms[4]][0]
job.title = "head of research"
job.keep(starts=now() - timedelta(days=54))
partner = Person.new(full_name="Ilya Bergmann", email="ilya.b@example.com")
partner.relate(sofia, "partner", label="husband")
"""

TURNS = [
    "Using my world (terraweaver): I'm seeing Sofia Bergmann tomorrow for the first time in ages. "
    "Remind me what I need to know before that — where she is now, what we left unfinished, what's "
    "new with her, and anything I should keep off the table.",
]

EXPECT = """
sofia = Person.get(email="sofia.bergmann@northwind.example")
assert sofia.organization is not None and sofia.organization.name == "Halden Labs", \
    f"her current employer should be Halden Labs, got {sofia.organization}"
"""

PROBES = [
    ("Using my world (terraweaver): before I see Sofia tomorrow — where does she work now and what "
     "is she doing there, what did I promise her last time, what's new in her life, and what should "
     "I avoid?",
     # Saying the leave is over is right; presenting it as where she is now is not.
     ["Halden", "Kaplan", "son", "Pike"], ["currently on leave", "is on parental leave"]),
    ("Using my world (terraweaver): when did I last see Sofia, and what did we talk about?",
     ["research"], []),
]

LEVEL = "hard"
