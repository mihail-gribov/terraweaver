"""World fixture: a job search in progress.

Rich enough to ask real questions of — not just companies and vacancies, but the people
around the search, what the owner wants from it, what is already scheduled, and what they
meant to follow up on. Deterministic (no randomness) so scenario ground truth stays stable.

Two contacts are deliberately both called Anna, and both answer to "Annie": a personal world
genuinely contains name collisions, and an agent that only ever meets unambiguous names is
never tested on the case that matters.

TechCorp deliberately has more vacancies than any other company, so "which company has
the most openings" has a single right answer.
"""
from datetime import datetime, timedelta, timezone

from terraweaver.world import World

COMPANY_DATA = [
    # (name, industry, city, aliases) — companies get called by short and spelled-out names
    ("TechCorp", "Software", "San Francisco", ["TC", "Tech Corp"]),
    ("DataWorks", "Data Analytics", "New York", ["DW", "Data Works"]),
    ("CloudNine", "Cloud Infrastructure", "Seattle", ["Cloud 9"]),
    ("PixelForge", "Game Development", "Austin", []),
    ("QuantumLeap", "AI Research", "Boston", ["QL"]),
    ("GreenGrid", "CleanTech", "Berlin", []),
    ("FinEdge", "FinTech", "London", []),
    ("HealthSync", "HealthTech", "Toronto", []),
]

VACANCY_DATA = [
    # (title, company, stack, salary_min, salary_max, remote, status)
    ("Senior Backend Engineer", "TechCorp", ["Python", "Django", "PostgreSQL"], 140000, 180000, True, "not_applied"),
    ("Frontend Engineer", "TechCorp", ["React", "TypeScript", "CSS"], 120000, 150000, False, "not_applied"),
    ("DevOps Engineer", "TechCorp", ["AWS", "Terraform", "Kubernetes"], 130000, 160000, True, "applied"),
    ("QA Engineer", "TechCorp", ["Python", "Selenium", "CI/CD"], 100000, 125000, False, "not_applied"),
    ("Engineering Manager", "TechCorp", ["Leadership", "Python", "System Design"], 160000, 200000, False, "not_applied"),
    ("Data Engineer", "DataWorks", ["Python", "Spark", "Airflow"], 135000, 170000, True, "not_applied"),
    ("ML Engineer", "DataWorks", ["Python", "PyTorch", "SQL"], 150000, 190000, True, "interviewing"),
    ("Analytics Manager", "DataWorks", ["SQL", "Tableau", "Python"], 145000, 175000, False, "not_applied"),
    ("Cloud Architect", "CloudNine", ["AWS", "GCP", "Terraform"], 160000, 200000, True, "not_applied"),
    ("Site Reliability Engineer", "CloudNine", ["Kubernetes", "Go", "Prometheus"], 140000, 175000, True, "not_applied"),
    ("Support Engineer", "CloudNine", ["Linux", "Bash", "AWS"], 90000, 110000, False, "rejected"),
    ("Gameplay Programmer", "PixelForge", ["C++", "Unreal Engine"], 110000, 140000, False, "not_applied"),
    ("Graphics Engineer", "PixelForge", ["C++", "OpenGL", "Vulkan"], 120000, 155000, False, "not_applied"),
    ("Technical Artist", "PixelForge", ["Python", "Maya", "Unity"], 95000, 120000, False, "not_applied"),
    ("Research Scientist", "QuantumLeap", ["Python", "PyTorch", "Research"], 170000, 220000, True, "not_applied"),
    ("NLP Engineer", "QuantumLeap", ["Python", "NLP", "Transformers"], 155000, 195000, True, "applied"),
    ("Research Engineer", "QuantumLeap", ["Python", "JAX", "Research"], 160000, 200000, True, "not_applied"),
    ("Embedded Engineer", "GreenGrid", ["C", "Embedded", "IoT"], 100000, 130000, False, "not_applied"),
    ("Sustainability Analyst", "GreenGrid", ["Python", "Data Analysis"], 85000, 105000, False, "not_applied"),
    ("Firmware Engineer", "GreenGrid", ["C++", "Embedded"], 105000, 135000, False, "offer"),
    ("Quant Developer", "FinEdge", ["Python", "C++", "Quantitative Finance"], 165000, 210000, False, "not_applied"),
    ("Backend Engineer", "FinEdge", ["Java", "Spring", "PostgreSQL"], 130000, 165000, True, "not_applied"),
    ("Risk Analyst", "FinEdge", ["Python", "SQL", "Risk Modeling"], 110000, 140000, False, "not_applied"),
    ("Health Data Engineer", "HealthSync", ["Python", "SQL", "HL7"], 125000, 155000, True, "not_applied"),
    ("Mobile Engineer", "HealthSync", ["Swift", "iOS"], 115000, 145000, False, "not_applied"),
    ("Product Manager", "HealthSync", ["Roadmapping", "Agile"], 130000, 160000, True, "not_applied"),
]


# The two personas every conversation has: whose world this is, and who is minding it.
OWNER = {"full_name": "Michael", "email": "michael@example.com"}
AGENT = {
    "name": "Tera",
    "character": "Attentive and calm. Doesn't fuss or ask about trifles, but never makes "
                 "things up — if it doesn't know for sure, it asks.",
    "speaking_style": "Short and human. No officialese, no bullet lists where one sentence does.",
}

PEOPLE_DATA = [
    # (full_name, email, company or None, relationship, job_title, aliases)
    # A misspelling such as "Ada Lovelase" is deliberately not recorded, so it stays a
    # resemblance for the user to confirm rather than a settled name.
    ("Ada Lovelace", "ada@example.com", "TechCorp", "friend", "Staff Engineer", ["Ada"]),
    ("Alan Turing", "alan@example.com", "QuantumLeap", "friend", "Research Scientist", ["Alan"]),
    ("Barbara Liskov", "barbara@example.com", None, "former colleague", None, ["Barb"]),
    # Both answer to "Annie" — the collision is the point. Only Sullivan goes by "Ann".
    ("Anna Peterson", "anna.peterson@example.com", "DataWorks", "recruiter", "Technical Recruiter", ["Annie"]),
    ("Anna Sullivan", "anna.sullivan@example.com", "CloudNine", "acquaintance", "SRE", ["Annie", "Ann"]),
    ("Robert Wolfe", "robert@example.com", "FinEdge", "former manager", "Head of Engineering", ["Bob"]),
]

# What the owner wants out of this search — the part that makes an answer personal.
OWNER_FACTS = [
    ("wants", "remote work", 1.0),
    ("wants", "a salary of 150000 or more", 1.0),
    ("likes", "Python", 1.0),
    ("dislikes", "night on-call shifts", 0.8),
]

# (title, kind, in_days, participants, company, status, notes)
# `kind` is recorded rather than left to be guessed from the title: "DataWorks interview"
# and "chat with DW" can be the same kind of thing, and no keyword heuristic survives that.
EVENTS_DATA = [
    ("DataWorks interview", "interview", 3, ["Anna Peterson"], "DataWorks", "confirmed",
     "Technical round; they said it would be about Spark and Airflow."),
    ("Call with Alan about QuantumLeap", "call", 1, ["Alan Turing"], "QuantumLeap", "planned",
     "Ask how research work and overtime go there."),
    ("CloudNine interview", "interview", -4, ["Anna Sullivan"], "CloudNine", "cancelled",
     "Cancelled on their side; they promised to get back later."),
]

# (title, content, related person)
NOTES_DATA = [
    ("Ask Annie about the culture", "Find out from Annie how overtime really is at DataWorks.",
     "Anna Peterson"),
    ("Referral from Bob", "Bob offered to refer me to FinEdge — don't forget to write to him.",
     "Robert Wolfe"),
]


def build(classes: dict[str, type], store) -> None:
    """(Re-)populate the store with the fixture world under stable ids."""
    for class_name in ("Vacancy", "Organization", "Place", "Person", "Event", "Idea", "Project", "Preference"):
        store.clear(class_name)


    Place = classes["Place"]
    Organization = classes["Organization"]
    Vacancy = classes["Vacancy"]

    companies = {}
    for name, industry, city, aliases in COMPANY_DATA:
        slug = name.lower()
        place = Place(id=f"place:{slug}", name=f"{name} HQ", city=city, category="work")
        org = Organization(id=f"org:{slug}", name=name, aliases=list(aliases), industry=industry, location=place)
        store.save(place)
        store.save(org)
        companies[name] = org

    store.clear("Agent")
    Person = classes["Person"]
    # Every world already holds the two parties under fixed ids (world.ensure_selves); a fixture
    # fills them in rather than inventing a second pair.
    owner = Person(id=World.USER_ID, **OWNER)
    store.save(owner)
    store.save_graph(classes["Agent"](id=World.AGENT_ID, owner=owner, **AGENT))

    # Where people work and what they are to the owner are relations, not fields: a job carries
    # a role and dates, and "former manager" is an Authority that ended.
    Membership, Social, Service, Authority = (classes[n] for n in ("Membership", "Social", "Service", "Authority"))
    now_ = datetime.now(timezone.utc)
    people = {}
    for index, (full_name, email, company, relationship, job_title, aliases) in enumerate(PEOPLE_DATA):
        person = Person(id=f"person:{index:02d}", full_name=full_name, aliases=list(aliases), email=email)
        store.save(person)
        people[full_name] = person
        if company:
            store.save(Membership(id=f"membership:{index:02d}", subject=person, object=companies[company],
                                  title=job_title, kind="employment", primary=True))
        tie = f"tie:{index:02d}"
        if relationship == "recruiter":
            store.save(Service(id=tie, subject=person, object=owner, label="recruiter"))
        elif relationship == "former manager":
            store.save(Authority(id=tie, subject=person, object=owner, label="manager",
                                 valid_until=now_ - timedelta(days=365)))
        else:
            store.save(Social(id=tie, subject=owner, object=person, label=relationship))

    for predicate, value, confidence in OWNER_FACTS:
        store.save_graph(owner.add_fact(predicate=predicate, value=value, confidence=confidence))

    # Whoever we know at a company is our way in to its openings.
    contacts = {company: people[name] for name, _, company, *_ in PEOPLE_DATA if company}

    now = datetime.now(timezone.utc)
    vacancies = []
    for i, (title, company, stack, salary_min, salary_max, remote, status) in enumerate(VACANCY_DATA):
        org = companies[company]
        vacancy = Vacancy(
            id=f"vac:{i:03d}",
            title=title,
            organization=org,
            contact=contacts.get(company),
            # Status says where things stand; this says when they got there.
            applied_at=(now - timedelta(days=5 + i % 11)) if status != "not_applied" else None,
            location=org.location,
            remote=remote,
            salary_min=float(salary_min),
            salary_max=float(salary_max),
            stack=list(stack),
            status=status,
        )
        store.save_graph(vacancy)
        vacancies.append(vacancy)

    Event, Idea, Project = classes["Event"], classes["Idea"], classes["Project"]
    events = []
    for index, (title, kind, in_days, participants, company, status, notes) in enumerate(EVENTS_DATA):
        org = companies[company]
        # An interview is about the opening it's for; a call about the company being sounded out.
        subject = next((v for v in vacancies if v.organization is org and v.status == "interviewing"), org)
        event = Event(
            id=f"event:{index:02d}",
            title=title,
            kind=kind,
            about=subject if kind == "interview" else org,
            # Whole hours: a fixture time of "now + 3 days" carried minutes and microseconds
            # that hosts dutifully turned into appointments at 8:48 PM.
            start_time=(now + timedelta(days=in_days)).replace(hour=15, minute=0, second=0, microsecond=0),
            location=org.location,
            participants=[owner] + [people[name] for name in participants],
            status=status,
            notes=notes,
        )
        store.save_graph(event)
        events.append(event)

    for index, (title, content, about) in enumerate(NOTES_DATA):
        store.save_graph(Idea(id=f"idea:{index:02d}", title=title, content=content, related_to=[people[about]]))

    # The search is the frame the case hangs on, so it points at what it actually covers.
    in_play = [v for v in vacancies if v.status != "not_applied"]
    store.save_graph(Project(
        id="project:search",
        name="Job search",
        description="Looking for a remote Python role, aiming at 150000 and up.",
        status="active",
        owner=owner,
        start_date=now - timedelta(days=21),
        related_to=in_play + events,
    ))
