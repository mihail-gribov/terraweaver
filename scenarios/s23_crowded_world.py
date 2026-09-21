DESCRIPTION = """A world with a year of life in it: 90 people across 18 companies, jobs that changed,
120 meetings, and remarks scattered over all of it. The questions need a cross-section — who at a
company I met recently, who moved where, who is the only one left — the kind of thing that is a
query against a model and a reading exercise against a file. Volume is the point: the data no
longer fits comfortably in a turn, and what the host does with it is what differs."""

SETUP = """
industries = ["Data Analytics", "FinTech", "Health", "Logistics", "Game Development", "Energy"]
cities = ["Berlin", "Austin", "Lisbon", "Toronto", "Singapore"]
firsts = ["Ana", "Ben", "Clara", "Dmitry", "Elena", "Farid", "Greta", "Hugo", "Iris", "Jonas",
          "Kira", "Lars", "Maya", "Nils", "Olga", "Pavel", "Quinn", "Rosa", "Sven", "Tara",
          "Ugo", "Vera", "Wei", "Xenia", "Yuri", "Zoe", "Aiko", "Bruno", "Cato", "Dara"]
lasts = ["Adler", "Borg", "Cruz", "Dahl", "Ek", "Faber", "Grant", "Holt", "Ibsen", "Jung",
         "Kahn", "Lind", "Moss", "Nord", "Ovchinnikov", "Peres", "Quint", "Roth", "Stern", "Tate"]

companies = []
for i in range(18):
    name = f"{lasts[i]} {['Labs','Works','Systems','Group','Partners','Dynamics'][i % 6]}"
    place = Place.new(name=f"{name} office", city=cities[i % len(cities)], category="work")
    companies.append(Organization.new(name=name, industry=industries[i % len(industries)],
                                      location=place))

people = []
for i in range(90):
    first = firsts[i % len(firsts)]
    last = lasts[(i * 7 + (i // len(firsts)) * 3) % len(lasts)]
    person = Person.new(full_name=f"{first} {last}",
                        email=f"{first.lower()}.{last.lower()}{i}@example.com")
    here = companies[i % len(companies)]
    person.relate(here, "membership", title=["engineer", "analyst", "manager", "designer"][i % 4],
                  primary=True, starts=date(2026, 1 + (i % 9), 1 + (i % 27)))
    people.append(person)

# A year of movement: every seventh person changed employer in the spring.
for i in range(0, 90, 7):
    people[i].organization = companies[(i + 5) % len(companies)]

# Meetings, thinning out towards the present so "recently" means something.
for i in range(120):
    when = now() - timedelta(days=(i * 3) % 330)
    guests = [people[(i * 5) % 90], people[(i * 11 + 3) % 90]]
    Event.new(title=f"{['coffee','review','interview','call','workshop'][i % 5]} with {guests[0].full_name}",
              kind=["meeting", "call", "interview", "meeting", "meeting"][i % 5],
              start_time=when, status="confirmed", participants=guests,
              about=companies[(i * 3) % len(companies)])

# One person the questions are about, so the task is answerable rather than a lottery: she works
# at Grant Labs, two of her colleagues were met recently, and one of them is looking.
maya = Person.new(full_name="Maya Grant", email="maya.grant@grantlabs.example")
maya.relate(companies[6], "membership", title="analyst", primary=True, starts=date(2026, 2, 3))
seen_lately = [maya, people[6], people[24]]
for i, guest in enumerate(seen_lately):
    if guest is not maya:
        guest.organization = companies[6]
    Event.new(title=f"coffee with {guest.full_name}", kind="meeting",
              start_time=now() - timedelta(days=3 + i * 9), status="confirmed", participants=[guest],
              about=companies[6])
people[24].describe("mentioned they are looking", when=now() - timedelta(days=11))

# Remarks worth finding later, spread thinly: a third of the people have one.
for i in range(0, 90, 3):
    people[i].describe(["mentioned they are looking", "allergic to peanuts", "has two kids",
                       "prefers mornings", "speaks Portuguese", "runs marathons"][i % 6],
                      when=now() - timedelta(days=(i * 4) % 200))
"""

TURNS = [
    "Using my world (terraweaver): I had coffee with Maya Grant yesterday and she mentioned her "
    "team is hiring two analysts. Note that down.",
]

EXPECT = """
maya = [p for p in Person.all(limit=None) if p.full_name == "Maya Grant"]
assert len(maya) == 1, f"Maya duplicated or lost: {len(maya)}"
assert [c for c in maya[0].described() if "hiring" in c.text.lower() or "analyst" in c.text.lower()], \
    "the hiring remark wasn't attached to Maya"
"""

PROBES = [
    ("Using my world (terraweaver): which people at Grant Labs have I met in the last 60 days, and "
     "what do I know about each of them beyond their job?",
     ["Maya Grant"], ["no one", "nobody", "no data", "not found"]),
    ("Using my world (terraweaver): who changed employer this year, and how many of them did I meet "
     "after they moved? Give me the number.",
     ["moved", "changed"], []),
    ("Using my world (terraweaver): who at Grant Labs is looking for work right now?",
     ["looking"], ["nobody", "no one"]),
]

LEVEL = "hard"
