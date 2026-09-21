"""What the host reads: the world described in its own words.

Kept apart from the object model on purpose. `ontology.py` decides how an entity behaves; this
decides how it is explained — and the explanation is the interface a model actually works
against, so it is edited as carefully as code and belongs where it can be read in one sitting.

    HOST_GUIDE          how the world works: runs, sessions, what it refuses and why
    COMMON_MEMBERS      what every class shares: the verbs, time, remarks, relations, questions
    describe_for_prompt the classes themselves, from their specs
"""
from typing import Any

from terraweaver import sandbox


HOST_GUIDE = """\
This is the user's personal world: a Python object model backed by storage. You work with it
by sending Python code to the `run` tool. Print what you need to see — stdout is what you get
back. Variables persist between `run` calls in this session, so build on earlier results.

In the namespace: every class below, `world`, `NeedsResolution`, and the two this world is
between — `user`, the person it belongs to, and `agent`, you. Those two are always there, in
every session, and can't be rebound; `owner` and `me` are older names for the same two.

World variables (listed below, if any) are the few named things every session shares: use
them as they are instead of looking them up again. Set or change one with
`world.pin(anna, value, "description")`, remove with `world.unpin(anna, stats)` — name them as
variables, no quotes needed. Pin only what will
matter beyond this task, and describe what it is.

Variables are working memory for one task. Starting a new task, call `reset_session` first, so
nothing from an earlier task — an entity settled for another conversation, a stale query
result — carries over. After a long pause the session is reset for you. Anything that must
outlive the task belongs in the world, not in a variable.

Rules the world enforces:
- Each `run` is atomic: if your code raises, nothing it *wrote* is kept — including the lines
  that printed before it failed. Your variables are not rolled back, though: the result says
  which are [still bound], so send again only what the failure stopped, not the lookups you
  already have. One thing to watch: an entity created in the failed run is [not in the world]
  — the variable still holds it, its record was taken back, and it must be recorded again
  before anything is linked to it.
- What isn't in the world isn't known. An empty result means the information isn't there — say
  so rather than filling the gap.
- Before recording what the user tells you, decide from the conversation whether it is about
  something already in the world or something new, and say so by the call: `Class.get(...)`
  for an existing one (never creates; NotInWorld if absent), `Class.new(...)` for a new one
  (asks the user if its twin exists), `Class.ensure(...)` only when you genuinely can't tell.
  Three levels of detail, so a task carries only what it uses. The prompt lists class names.
  describe_classes(["Person", "Event"]) gives their attributes with types, their methods and
  their relations, one line each. describe_methods(["tag", "repeat", "Event.reschedule"]) says
  what a particular one does, in full and with examples. Guessing an attribute name costs a turn
  to undo; asking costs a few hundred tokens.

  Never construct `Class(...)` directly. Check the [created] / [updated] / [found] lines of
  each result against what you meant. What has no attribute to go into is attached as a dated
  remark: `anna.describe("allergic to nuts", when=date(...))`.
- Which entity the user means is never yours to guess. Look it up with everything the user
  already told you — `Person.find(full_name="Annie", organization=cloudnine)`, not just the name.
  If it is still open, you get a NeedsResolution; printing it shows the question and the
  candidates (`needs.candidates`). Ask the user, then `entity = world.settle(needs, <the entity
  they meant>)`, or `world.settle(needs, new=True)` if it's someone new. Never answer it
  yourself — not even with new=True. If the user won't choose, leave it unresolved.
- Assigning an attribute is your statement and goes through: `anna.email = "..."` when the user
  says it changed, or when you concluded it. The old value is kept — `anna.history("email")`.
  A disagreement shows up as a question only when identifying: `Person.ensure(full_name="Ada",
  organization=dataworks)` with Ada recorded at TechCorp asks whether it changed, the record is
  right, or it's a different person — `world.settle(needs, <the value that is right>)`, or
  `new=True` for a different one.
- Your code can reach the world and plain computation only. """ + sandbox.AVAILABLE + "\n"


COMMON_MEMBERS = """\
Every class below shares these, so they aren't repeated for each one:

    id           — how this entity is known in the world
    created_at   — when it entered the world
    accessed_at  — when it was last worked with

    Class.all(limit=50)
        Entities of that class, the ones you dealt with most recently first. Limited by
        default, because a personal world keeps growing; pass limit=None for everything.

    Class.find(**attrs)
        Entities matching every attribute you pass, best match first (ties go to whoever
        you dealt with most recently). Ordinary attributes match exactly, so this is how
        you ask real questions of the world:
            Person.find(organization=acme)      — who works there
            Vacancy.find(remote=True, status="not_applied")
            Person.find(email="ada@example.com")
        Times and numbers take ranges — after(x), before(x), between(a, b) — which compare dates
        and datetimes safely whatever their time zone (use now() and today() for "now"):
            Event.find(start_time=after(now()))                               — upcoming
            Event.find(start_time=between(date(2026, 9, 21), date(2026, 9, 27)))  — that week
            Vacancy.find(salary_max=after(150000))
        Emails, phones and URLs compare in their canonical form, whatever way they're written:
        "+1 (555) 010-2030" finds "+15550102030", "Ada@Example.com" finds "ada@example.com",
        a company website matches on its domain (https://careers.acme.com/jobs ~ acme.com).

        The result comes back in two parts, and the difference matters:
            result.main     — the one it found, when the search found exactly one
            result.matches  — the ones that match (a list: none, one or several)
            result.similar  — the ones that merely resemble what you asked for
            result.matched  — False when nothing actually matched
        `result.main` is the usual way in and it is right whenever the search settled. Where it
        didn't, it says which: several match (look at result.matches and narrow what you asked —
        one more attribute usually settles it), or none did and some merely resemble.
        Iterating the result gives everything, best first, so it still works as a list —
        but `result[0]` may well be a resemblance. When `result.matched` is False, nothing
        in the world matches: say so, rather than serving the closest thing as the answer.
        A person's recorded nicknames count as their names, so "Bob" finds Robert.

        Look someone up by the fullest form of the name you know — "Michael Gribov", not "Миша".
        You are the one who knows that those are one name; the world only knows what it was
        told, and it keeps every form it was given, so either will usually find him. The full
        form is what identifies without context, and it is what the world will show back.

        A name this entity answers to, with no rival and nothing that disagrees, is them:
        "Darren" where the world holds one Darren Liu gives you Darren Liu, with an [assumed]
        line saying so. A question comes back when the world genuinely doesn't know — two people
        answer to that name, a value you gave disagrees with what's recorded, or the name merely
        resembles theirs ("Wilma Chen" is not "William Chen"). Then you get a NeedsResolution:
        it reads like a result that didn't settle (.matched is False, .similar holds the
        candidates), printing it shows the question, and which one was meant is not yours to
        decide — ask the user, then world.settle(...).

    Person.where(...) is the same call from the class's side, as Person.all and Person.find are.
    world.where(...) is the one way of asking, and the plain searches are it with a single
    condition — world.where(tagged="move") is the tag search, world.where(like="cell chemistry")
    is the meaning search. Everything given narrows; nothing widens:
        world.where(Person, organization=acme,          — attributes, as in find()
                    related=("membership", acme),        — a link, named from either end
                    tagged="berlin",                     — a tag, as it held at `at`
                    like="cell chemistry",               — what is said about them reads like this
                    at=date(2026, 6, 1), limit=20)
    The class is optional, and that is the point of it: leave it out and the answer is of any
    kind. Most real things in a life are not one kind of thing — everything to do with a move is
    a flat, a landlord, a moving firm and four dates — so ask for the thing, not for each kind:
        world.where(tagged="move")                       — the move, all of it
        world.where(related=("participation", project))  — everything hanging off one thing
    A relation name is read in its own direction: related="service" is who provides one,
    related="served_by" is who receives one. `like` also sets the order, since closeness is the
    only thing here with a degree.

    Recording what the user tells you starts with a decision only you can make from the
    conversation: is it about someone/something already in the world, or new? Say so by the
    call you pick — the world checks the claim instead of deciding silently.

    Class.get(**attrs)
        "The one we already know." Use everything the user said to pick it out:
        Person.get(full_name="Annie", organization=cloudnine). Returns that entity, or a
        NeedsResolution if several fit. Never creates: if nothing matches, it raises NotInWorld
        — then either the user means someone new (use new) or you misidentified them.
    Class.new(**attrs)
        "Someone/something new." Creates it — unless one just like it already exists (same
        email, same name at the same company, the same event on the same day); then you get
        a NeedsResolution asking the user whether it's really new.
    Class.ensure(**attrs)
        "I can't tell." Finds it or creates it; the attributes are new information, so a value
        contradicting what's stored comes back as a question. Prefer get or new whenever the
        conversation tells you which it is.

    After each run the result lists what happened: [created], [updated] with the attributes
    that changed, [found]. Check it matches what you meant.

    entity.save()
        Persist that entity and everything it references.

    Relations link two entities and carry their own data (docs: "Relation types" below).
    Direction is one rule: the subject is the one the label describes, so a.relate(b, kind,
    label=X) reads "a is b's X". maria.relate(michael, "kin", label="mother") says Maria is
    Michael's mother; nina.relate(michael, "service", label="dentist") says Nina is Michael's
    dentist. Read the sentence before you write the call — "my dentist is Nina" puts Nina first,
    not the owner. From the other end, use the reverse name: michael.relate(greg, "served_by",
    label="landlord") says Greg is Michael's landlord. Results show each relation as that
    sentence — check it reads the way you meant. A relation's period
    reads back under the same names it's written with: rel.starts, rel.until. The label is matched to the type's roles ("mom" -> mother,
    "older brother" -> sibling), and the world checks each role's limits — a second mother is
    refused with the alternatives (stepmother). relation.role_of(entity) says what an end is to
    the other ("child" for Michael). a.how_related(b) walks the relations and names the chain
    ("sister's husband" -> sibling in law).
        kevin.relate(b04, "membership", title="vendor logistics lead", starts=date(2026, 1, 15))
        kevin.relate(darren, "kin", label="older brother")
        linda.relate(b04, "authority", label="manager")
        b04.relate(company, "part_of")
    entity.relations(kind)[i].counterpart is the end that isn't the entity you asked from.
    descriptions — every class has them, relations included, and the type is list[text]: not one
    paragraph but many texts, each said on its own and each able to hold for a time. This is
    where anything said in words about a thing goes; none of them replaces another, because
    people describe the same thing differently and each telling is worth keeping.
        anna.describe("quiet, precise, hates being rushed")
        anna.describe("hiring freeze since March", when=date(2026, 3, 1))  — when it happened
        anna.describe("might move in spring", tentative=True, ttl=timedelta(days=60))
        anna.descriptions                 — the texts that hold for her now, as plain strings
        anna.described(contains="move")   — the same with when, how long, and whether tentative
        anna.drop("descriptions", "...")  — this one stops holding; the record keeps that it did
        anna.spells("descriptions")       — every stretch each text has held, in order
        world.described(contains="lease") — across everything, newest first
        anna.descriptions = [...]         — "these are the ones now": what is new is said, what
                                            is no longer named stops holding
    `describe` is `add("descriptions", ...)` plus three things only a remark needs: when it
    happened (as distinct from when the text starts to hold), that it may be tentative, and an
    end by default (180 days, 30 for a tentative one) so notes go stale on their own.
    Descriptions are what both searches run on — the words themselves (world.where(mentions=...))
    and the meaning (world.where(like=...)) — so a description written down is how you find
    someone later by something no attribute can hold. It may be the user's words or something
    publicly known — a company's own account of itself, what a place is — and the record keeps
    whose telling each one was, so the two never blur.

    tags — every class has them. A tie too vague to formalise — everything about the move, everyone from that
    conference, what matters this month. A relation type has to say what the tie *is*; a tag only
    says there is one. anna.tags = ["job-search", "berlin"]. They are kept in one form, so
    "job search" and "Job-Search" are the same tag however they were typed (what you typed stays
    in the record):
        anna.tag("berlin", "apartment-hunt", until=date(2027, 3, 1))  — several at once, one period
        anna.untag("apartment-hunt")  — it stops holding now; the record keeps that it once did
        anna.tags                     — what holds for her now
        anna.spells("tags")           — every stretch each tag has held, in order
        anna.suggest_tags()           — tags worth considering, from whatever reads like her
        world.tagged("berlin")        — everything carrying it now, whatever the spelling
        world.tagged("berlin", any_time=True)     — and everything that ever did
        world.tagged_all("berlin", "conference")  — carrying both: one gathers, two pick out
        world.tags()                  — every tag, how often used, how it has been written
        world.merge_tags("job-search", "jobsearch")   — two words for one idea, when you know it
        world.untag("q3-push")        — take one off everything, when it has stopped meaning anything
    A tag holds for a time, like everything else here: `starts=`, `until=`, `ttl=`,
    `permanent=True`, and reads that take `any_time=True`. A set of tags put on in one breath
    usually shares one period, which is why tag() takes several at once. The same tag can hold
    over more than one stretch — on in spring, off in summer, on again — and each stretch is kept,
    so "what was this tagged in June" has an answer. Assigning the list (anna.tags = [...]) says
    "these are the tags now", which ends the ones no longer named.
    Suggesting applies nothing and merging is yours to decide: what a tag means is what the user
    means by the word, and the world only counts and points.

    Finding by meaning, for what is written as prose rather than filled in:
        world.like("works on batteries")   — remarks and notes that read like that, closest first
        person.similar()                   — whoever else reads like what is said about them
    It searches, it doesn't decide: what comes back are candidates with how close they read, and
    nothing about who someone is follows from it.

    Walking the graph, for when the answer is a chain rather than a field. The world does the
    walking; what a chain means is yours to say:
        a.path_to(b)          how these two are connected, step by step — None if nothing does
        a.near(hops=2)        everyone within a few links, nearest first, with the way there
        a.shared_with(b)      what both are connected to: people, companies, places in common
        a.reaches("part_of")  everything along one kind of link, as far as it goes
    relate returns the relation — assign its attributes like any entity's (m.title = "team lead"),
    describe it, end it (m.expire()). entity.relations(kind) gives the relations themselves;
    entity.related(kind) the entities at the other end — also by the reverse name (b04.related(
    "members")) and along chains (kevin.related("membership") includes the company B04 is part
    of). What no type fits: a.relate(b, "related", label="godfather", description="…").
    Person.organization / job_title / relationship read from these relations and can be assigned.

    What the world holds to. It doesn't mind how you write your code — import what you like of
    what's already here, name things as you please. What it does hold is the data: an attribute
    with a vocabulary takes one of its words (however you type it — "Meeting" is "meeting"), and
    anything else is refused with the list; a value declared an email, phone or web address that
    can't be one is kept and asked about; a relation must satisfy the rules of its type; and a
    run is all or nothing, so a subgraph is never half-written.

    Assigning an attribute (anna.email = "...") is your statement — the user said so or you
    concluded it — and it goes through as it is. The old value isn't lost:
    entity.history("email") lists what it held before and until when.

    Time is one axis for the whole world, and the same words mean the same thing everywhere.
    Three times are easy to confuse, so keep them apart:
      when it's true   — the validity period, starts / until. Every entity and every relation
                         has one. A job that ran March to September, a lease to next June.
      when it happened — the thing's own time, an ordinary attribute: Event.start_time, a
                         a description's when. A past meeting and next week's one are both valid
                         records; find them by that attribute (Event.find(start_time=after(now()))).
      when we learned  — created_at / recorded_at, the world's bookkeeping. A marriage recorded
                         today may have started in 2019; you never set this.
    What can be given a period — the same four keywords everywhere, and this is the whole list:
      an entity      Class.ensure(..., starts=..., until=...) — a listing open for a month, a
                     project that ran last year; entity.keep(...), entity.expire(), .current()
      a relation     a.relate(b, kind, starts=..., until=...) — a job, a marriage, a landlord;
                     rel.keep(...), rel.expire()
      a tag          anna.tag("apartment-hunt", until=...) — several at once share one period;
                     anna.untag(...) ends it, and each stretch is kept (anna.spells("tags"))
      one text       anna.add("descriptions", "on parental leave", starts=..., until=...) —
                     any list[text] slot: several free texts, each its own dated item.
                     anna.drop("descriptions", "...") ends one; anna.spells("descriptions")
                     lists the stretches. `anna.descriptions = [...]` means "these are the
                     ones now" and goes through the same door.
      a remark       anna.describe(text, when=..., until=..., ttl=..., permanent=True)
    Searching words, two ways, and they are not the same question:
        world.where(mentions="lisbon flat")   — literally: every word appears, case ignored,
                                                nothing stemmed, same answer every time
        world.where(like="a shop selling bread")  — by meaning, which is a judgement; an entity
                                                is scored on all its texts, the closest first
        world.texts("lisbon", slot="descriptions")  — the texts themselves, not their entities
    Everything said in words lives in one derived table (texts.py), so both of these are one
    query, and each text carries its own meaning rather than the entity carrying an average.

    A slot typed list[text] holds several free texts, each stated on its own and each able to
    hold for a time — that is what descriptions are, and what any "several things said about
    this" attribute should be. A slot typed list[enum[a, b, c]] is the same, drawn from a fixed
    vocabulary. What the vocabulary has no word for goes in a free text, never a new word.

    Not an attribute value: `anna.email = ...` holds from when you write it, and there is no way
    yet to say a value held from March to June. Say it in a remark and note the dates there.

    A period can be cyclic instead of one-off — a standup every weekday, rent on the first, a
    rota every third week. Say it once as a rule; nothing is written out occurrence by occurrence:
        standup.repeat(every="day", lasting=timedelta(minutes=30))
        one_to_one.repeat(every="2 weeks")          — anchored on its own date (start_time)
        michael.tag("on-call", every="3 weeks", lasting=timedelta(days=7), starts=date(...))
      every=   "day", "week", "2 weeks", "month", "quarter", "year", or a timedelta
      lasting= how long each one runs; left out, it is a moment rather than a stretch
      starts=  the first one (anchor); until= when the series stops
    "What repeats?" is world.repeats() — every cyclic thing in the world, whatever kind it is.
    Do not answer it from the events alone: a rota, a season, anything that holds for a while
    again and again is a tag with a period, and it will not be in Event.all().

    world.happening(since, until) answers "what is on between these two dates" for the whole
    world, counting repeats out into that window. Use it rather than a date query on an
    attribute: a weekly standup has one start_time — the day it started — so
    Event.find(start_time=after(new_year)) finds nothing, however many times it will happen.

    Read it back: entity.next_occurrence(), entity.occurrences(since=..., until=...) — a rule has
    no end, so a question about it needs a window; entity.repeats() and world.repeats() say what
    is cyclic in words. A cyclic tag answers as of a moment like any other: whether someone is
    on call on the 30th is world.where(tagged="on-call", at=date(2026, 9, 30)).

    Writing a period, the same four keywords for entities, relations and descriptions:
        Class.ensure(..., starts=date(2026, 10, 1))   — begins later
        Class.ensure(..., until=date(...) | ttl=timedelta(days=30))
        kevin.relate(b04, "membership", title="lead", starts=date(2026, 1, 15))
        entity.keep(starts=..., until=... | ttl=... | permanent=True); entity.expire() ends it
        now; entity.current() asks whether it holds. Nothing is deleted when a period ends — it
        becomes history.
    Reading, the default is now — that's why "who is her partner" doesn't return an ex. One
    keyword widens any read: any_time=True in Class.all, Class.find, entity.relations,
    entity.related, entity.described, world.described. It adds both ended and not-yet-started
    ones — the future is not history. When a read hides something, you get a [hint] saying so.
    entity.timeline(since=None, until=None)
        Everything dated about one entity or relation, oldest first — when it was recorded, when
        its period starts and ends, what its attributes were changed to and when, its dated
        remarks, its relations starting and ending. Each moment has .when and .what. This is the
        one call for "what happened with this, and when", instead of assembling history(),
        described() and relations(any_time=True) by hand.
    Conflicts are judged by overlapping periods, not by "now": one employer at a time, one
    mother, one CEO — but divorced in 2020 and married in 2022 contradict nothing.

    Open questions. The world takes what you tell it even when it doesn't add up — the user
    said it, and their life is not the world's to correct. What doesn't add up is kept as a
    question about the entity: two current dentists, someone recorded as new next to someone who
    answers to the same name, anything you noticed yourself.

    An open question never leaves you without an answer. Each one comes with what the world
    reads meanwhile, and that reading is a rule, the same for every host at every hour: the
    later statement counts. Lists come in that order, so the first one is the one that counts;
    identity is the exception — two records are never merged without an answer, you get the one
    you looked up. So you can always answer: by the standing reading, saying which it is.

    Three moments to put one to the user, and only these — a doubt that doesn't bear on what
    you're doing stays quiet until one of them:
      [ask first]     — this run's read depends on it. Ask before answering, or answer by the
                        standing reading and say so ("as recorded, Nina from October 1").
      end of a task   — world.questions(here=True) is what this task touched; reset_session
                        hands you the same list. The user is there and nothing is in flight:
                        "two things I'd like to check with you".
      the user offers — world.questions() is everything open, the entities that come up most
                        often first. Never interrupt a task with these.
        for q in owner.questions(): print(q.line())
        q.answer("Nina replaces Rao")    — closes it; recording what follows from it is yours
        q.drop("asked — it's a different Olga")
        anna.question("two numbers, which is current?", options=["the mobile", "the old one"],
                      about="phone")     — about= makes a later read of that attribute say so
    A question closes itself once its reason is gone: end the old dentist's relation and the
    question about two dentists goes away without anyone answering it.

    entity.describe(text, when=None, tentative=False, until=None, ttl=None, permanent=False)
        One word, one place: it goes into entity.descriptions, which holds as many texts as
        anyone cares to say, and is found by its words (world.where(mentions=...)) and by its
        meaning like anything else said here. What `describe` adds over
        entity.add("descriptions", ...) is when the thing happened (`when=`, as distinct from
        when the text starts to hold), that it may be only tentative, and an end by default so
        notes go stale on their own.
        Say whatever matters about it but has no attribute —
        a friend's allergy, "hiring frozen since March", "might move in spring". `when` is the
        date it happened or holds (a date or datetime), if known; tentative=True for what isn't
        certain yet. Say how long it holds: until=date(...), ttl=timedelta(days=7) ("on vacation
        until Friday", a pickup code), or permanent=True (an allergy). Unsaid, it holds 180 days,
        a tentative one 30. Prefer a real attribute when one exists; never invent attributes.
    entity.described(since=None, until=None, contains=None, any_time=False)
        That entity's current remarks, newest first; expired ones are history, shown only with
        any_time=True. Each has .text, .when, .until, .expired, .recorded_at,
        .tentative, .about, and .forget() (delete for good), .confirm(),
        .keep(until=... | ttl=... | permanent=True) to change how long it holds.
    world.described(since=None, until=None, contains=None, any_time=False)
        Remarks across the whole world.
"""


def short(text: str, width: int = 88) -> str:
    """The first sentence, and not too much of it — enough to choose by, not to work from."""
    said = " ".join(str(text or "").split())
    stop = said.find(". ")
    if stop > 20:
        said = said[:stop + 1]
    return said if len(said) <= width else said[:width - 1].rsplit(" ", 1)[0] + "…"


def describe_methods(specs: dict[str, dict[str, Any]], names: list[str]) -> str:
    """Everything about a few methods: the full description, and an example where there is one.

    Three levels, because a task needs all of one and none of the others: the prompt says what
    classes there are, describe_classes says what a class is made of in one line per member, and
    this says what a member actually does. Class methods come from the ontology; everything every
    entity can do comes from the code itself, so there is no second copy of it to go stale.
    """
    from terraweaver import ontology, world as world_module

    out, missing = [], []
    for asked in names:
        name = str(asked).strip()
        written = _spec_method(specs, name) or _code_method(ontology.Entity, name) or \
            _code_method(world_module.World, name)
        (out.append(written) if written else missing.append(name))
    if not out:
        return ("No such method: " + ", ".join(missing) + ".\n\n" + _members_index())
    text = "\n\n".join(out)
    if missing:
        text += "\n\nNot found: " + ", ".join(missing) + ".\n" + _members_index()
    return text


def _spec_method(specs: dict, name: str) -> str | None:
    """A method a class declares in the ontology — asked for as "Event.reschedule"."""
    if "." not in name:
        return None
    class_name, method_name = name.split(".", 1)
    spec = next((s for n, s in specs.items() if n.lower() == class_name.lower()), None)
    for method in (spec or {}).get("methods", []):
        if method["signature"].split("(")[0] == method_name or method.get("name") == method_name:
            lines = [f"{class_name}.{method['signature']}", "    " + " ".join(
                str(method.get("description", "")).split())]
            if method.get("example"):
                lines.append("    e.g. " + method["example"])
            return "\n".join(lines)
    return None


def _code_method(holder, name: str) -> str | None:
    """One of the things every entity or the world itself can do. Its docstring is the source —
    written once, next to what it does, so this cannot drift from the truth."""
    import inspect

    bare = name.split(".")[-1]
    member = getattr(holder, bare, None)
    if member is None or not callable(member) or bare.startswith("_"):
        return None
    try:
        signature = str(inspect.signature(member)).replace("self, ", "").replace("(self)", "()")
    except (TypeError, ValueError):
        signature = "(...)"
    where = "entity" if holder.__name__ == "Entity" else "world"
    body = inspect.getdoc(member) or ""
    return f"{where}.{bare}{signature}\n" + "\n".join("    " + line for line in body.splitlines())


def _members_index() -> str:
    """What can be asked about, by name — one line, not a listing of every signature."""
    from terraweaver import ontology, world as world_module

    def named(holder):
        return sorted(n for n in vars(holder) if not n.startswith("_")
                      and callable(getattr(holder, n, None)))

    return ("Ask by name — describe_methods([\"tag\", \"Event.reschedule\"]).\n"
            "  every entity: " + ", ".join(named(ontology.Entity)) + "\n"
            "  the world:    " + ", ".join(named(world_module.World)))


def catalogue(specs: dict[str, dict[str, Any]]) -> str:
    """The classes by name, one line each — what the prompt carries.

    Spelling out every attribute, method and relation of every class cost six thousand tokens in
    front of every task, most of them about classes the task never touches. So the prompt says
    what there is, and `describe_classes([...])` says what any of them is made of. The one line
    per class is there to choose by, not to work from.
    """
    entities = [f"{n} — {s.get('description', '').strip()}" for n, s in specs.items()
                if "relation" not in s]
    links = []
    for name, spec in specs.items():
        rel = spec.get("relation")
        if not rel:
            continue
        reverse = f" / '{rel['reverse']}'" if rel.get("reverse") else ""
        links.append(f"{name} ('{rel['kind']}'{reverse}): "
                     f"{' / '.join(rel['from'])} → {' / '.join(rel['to'])}")
    return "\n".join(
        ["Classes in this world — names only. Before writing code that touches one, call",
         "describe_classes([\"Person\", \"Event\"]) for its attributes, methods and relations.",
         ""]
        + [f"  {line}" for line in entities]
        + ["", "Relation types — a.relate(b, kind, label=X) reads as the sentence \"a is b's X\", so the",
           "dentist, the manager, the mother stands first. The reverse name reads it from the other end.",
           ""]
        + [f"  {line}" for line in links]
        + [""])


def describe_for_prompt(specs: dict[str, dict[str, Any]], only: list[str] | None = None) -> str:
    """Render class specs as compact text: everything, or only the classes asked for.

    Entity classes come first, each with its attributes, methods and the relations it takes part
    in; then the relation types, each with how it behaves and its own attributes.
    """
    from terraweaver.relations import describe_relations

    lines = []
    wanted = {n.lower() for n in only} if only else None
    if wanted is not None:
        specs = {n: s for n, s in specs.items() if n.lower() in wanted}
    entities = {n: s for n, s in specs.items() if "relation" not in s}
    relation_types = {n: s for n, s in specs.items() if "relation" in s}
    for name, spec in entities.items():
        lines.append(f"class {name}:  # {spec.get('description', '')}")
        lines += _attribute_lines(spec)
        for method in spec.get("methods", []):
            lines.append(f"    def {method['signature']}:  # {short(method.get('description', ''))}")
        if relation_types:
            lines.append("    relations:  # entity.relate(other, kind, ...), entity.related(kind)")
            lines += describe_relations(specs, name)
        lines.append("")
    if relation_types and only is None:
        lines.append("Relation types — instances linking a subject and an object, with their own attributes and")
        lines.append("validity period (starts / until), history and descriptions.")
        lines.append("")
        lines.append("Direction, one rule for every type: the subject is the one the label describes.")
        lines.append("a.relate(b, kind, label=X) reads as the sentence \"a is b's X\" — so the dentist, the")
        lines.append("manager, the mother stands first. Say it out loud before writing it; each type below")
        lines.append("shows the sentence its example makes, and results print every relation as that sentence.")
        lines.append("To say it from the other end, use the reverse name: michael.relate(nina, \"served_by\",")
        lines.append("label=\"dentist\") records the same relation, read from the client's side.")
        lines.append("")
    if relation_types:
        for name, spec in relation_types.items():
            rel = spec["relation"]
            traits = [t for t in ("symmetric", "transitive", "acyclic") if rel.get(t)]
            if rel.get("functional") == "at_any_time":
                traits.append("one at a time per subject")
            if rel.get("inverse_functional") == "at_any_time":
                traits.append("one at a time per object")
            if rel.get("transitive_via"):
                traits.append(f"extends through {rel['transitive_via']}")
            if rel.get("reverse"):
                traits.append(f"read from the object's end as '{rel['reverse']}'")
            arrow = "↔" if rel.get("symmetric") else "→"
            lines.append(f"relation {name} ('{rel['kind']}'): {' / '.join(rel['from'])} {arrow} "
                         f"{' / '.join(rel['to'])}  # {spec.get('description', '')}")
            if traits:
                lines.append(f"    # {'; '.join(traits)}")
            if rel.get("example"):
                lines.append(f"    {rel['example']}   # {rel.get('reads', '')}")
            if rel.get("notes"):
                # What the shape of the data implies but the world won't infer for you.
                for line in _wrapped(rel["notes"], 92):
                    lines.append(f"    # {line}")
            if rel.get("roles"):
                shown = []
                for r in rel["roles"]:
                    limit = f" (at most {r['max']})" if r.get("max") else ""
                    names = ", ".join(r.get("synonyms", [])[:3])
                    shown.append(f"{r['name']}{limit}" + (f" [{names}]" if names and names != r["name"] else ""))
                lines.append(f"    # roles — a.relate(b, '{rel['kind']}', label=...) reads 'a is b's label': {'; '.join(shown)}")
            elif rel.get("labels"):
                lines.append(f"    # typical labels: {', '.join(rel['labels'][:8])}")
            lines += [line for line in _attribute_lines(spec) if not line.lstrip().startswith(("subject:", "object:"))]
            lines.append("")
    return "\n".join(lines)


def _wrapped(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return out + ([line] if line else [])


def _attribute_lines(spec: dict[str, Any]) -> list[str]:
    """One line per attribute: what it is called, what it holds, and a short word on why.

    Short on purpose. A class is read to write one piece of code, and the whole description of
    every attribute is more than that needs — describe_methods() has the rest."""
    lines = []
    for attr in spec["attributes"]:
        req = "required" if attr.get("required") else "optional"
        default = f", default={attr['default']!r}" if "default" in attr else ""
        said = short(attr.get("description", ""))
        if attr.get("derived") == "relation":
            access = "settable, " if attr.get("settable") else "read-only, "
            lines.append(f"    {attr['name']}: {attr['type']}  # {access}from relations — {said}")
        elif "derived" in attr:
            lines.append(f"    {attr['name']}: {attr['type']}  # read-only, from {attr['derived']} — {said}")
        else:
            lines.append(f"    {attr['name']}: {attr['type']}  # {req}{default} — {said}")
    return lines
