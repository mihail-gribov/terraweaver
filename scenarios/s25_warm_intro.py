DESCRIPTION = """Wanting to reach someone at a company and asking who could introduce you. The answer
is a chain — my former colleague's wife works there, my friend's brother used to — and it depends on
which chains are worth anything: a person seen last month is a different proposition from one who
stopped answering three years ago, and a link through someone's ex-employer is no link at all."""

SETUP = """
targets = Organization.new(name="Orbital Freight", industry="Logistics")
elsewhere = [Organization.new(name=n, industry="Data Analytics") for n in
             ["Cobalt Analytics", "Pike Systems", "Verso Labs"]]

# A crowd, so the chain has to be found rather than spotted.
firsts = ["Ana", "Ben", "Clara", "Dmitry", "Elena", "Farid", "Greta", "Hugo", "Iris", "Jonas",
          "Kira", "Lars", "Maya", "Nils", "Olga", "Pavel", "Rosa", "Sven", "Tara", "Vera"]
lasts = ["Adler", "Borg", "Cruz", "Dahl", "Ek", "Faber", "Holt", "Ibsen", "Jung", "Kahn"]
crowd = []
for i in range(36):
    person = Person.new(full_name=f"{firsts[i % 20]} {lasts[(i * 3 + i // 20) % 10]}",
                        email=f"c{i}@example.com")
    person.relate(elsewhere[i % 3], "membership", title="analyst", primary=True,
                  starts=date(2026, 1 + (i % 9), 1 + (i % 27)))
    crowd.append(person)
    if i % 4 == 0:
        person.relate(owner, "social", label="acquaintance")

# Three ways in, and only one of them is any good.
#
# 1. A former colleague I still see, whose wife works there.
tomas = Person.new(full_name="Tomas Reiner", email="tomas.reiner@example.com")
tomas.relate(owner, "social", label="former colleague")
tomas.relate(elsewhere[0], "membership", title="engineer", primary=True, starts=date(2025, 3, 1))
Event.new(title="beers with Tomas", kind="meeting", status="confirmed",
          start_time=now() - timedelta(days=21), participants=[tomas])
lena = Person.new(full_name="Lena Reiner", email="lena.reiner@orbital.example")
lena.relate(tomas, "partner", label="wife")
lena.relate(targets, "membership", title="operations manager", primary=True, starts=date(2024, 9, 2))

# 2. Someone I knew who *used to* work there and left two years ago — not a way in.
past = Person.new(full_name="Georg Malm", email="georg.malm@example.com")
past.relate(owner, "social", label="acquaintance")
old_job = past.relate(targets, "membership", title="dispatcher", primary=True,
                      starts=date(2021, 4, 1))
old_job.keep(until=date(2024, 6, 30))

# 3. A friend whose brother is there, but the friend and I haven't spoken in years.
distant = Person.new(full_name="Nadia Sorokin", email="nadia.sorokin@example.com")
distant.relate(owner, "social", label="friend")
Event.new(title="coffee with Nadia", kind="meeting", status="confirmed",
          start_time=now() - timedelta(days=1180), participants=[distant])
brother = Person.new(full_name="Artem Sorokin", email="artem.sorokin@orbital.example")
brother.relate(distant, "kin", label="brother")
brother.relate(targets, "membership", title="fleet planner", primary=True, starts=date(2023, 11, 5))
"""

TURNS = [
    "Using my world (terraweaver): I want to get in front of someone at Orbital Freight. Who do I "
    "know who could introduce me, how exactly, and who would you ask first?",
]

EXPECT = """
lena = Person.get(email="lena.reiner@orbital.example")
assert lena.organization is not None and lena.organization.name == "Orbital Freight", "Lena's job was damaged"
georg = Person.get(email="georg.malm@example.com")
assert not [o for o in georg.related("membership") if o.name == "Orbital Freight"], \
    "Georg left Orbital in 2024 — that job shouldn't read as current"
"""

PROBES = [
    ("Using my world (terraweaver): who can introduce me at Orbital Freight, through whom exactly, "
     "and who should I ask first?",
     ["Tomas", "Lena"], []),
    ("Using my world (terraweaver): is Georg Malm any use for getting into Orbital Freight?",
     ["left", "no longer", "until 2024", "2024", "former"], []),
]

LEVEL = "hard"
