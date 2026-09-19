"""Standardized known-answer scenarios for the code-writing agent.

One self-contained script: scenarios are declared below (task + a deterministic
`check(result)` predicate over the AgentResult — no LLM-as-judge) and run against
the live model. Task text is in Russian (that's the language tasks are posed in)
and deliberately phrased as an everyday request — it never names a class,
attribute, method, or enum value; mapping that onto the object model is the
agent's job, not something spelled out for it. identifiers/notes stay in English.

The world is shared; the agent under test is not. `--exp=<name>` picks which
experiment's agent answers the tasks, so runs stay comparable across architectures.

Usage: python run_scenarios.py [--exp=exp01_staged_agent] [--world=job_search] [--code] [name ...]
  Runs all scenarios whose name contains any given substring (or all, if none given).
"""
import re
import sys
from importlib import import_module
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from experiments.exp01_staged_agent.agent import AgentResult
from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.store import Store
from terraweaver.world import World
from worlds import DEFAULT_WORLD, load_world
from worlds.job_search import VACANCY_DATA

ONTOLOGY_DIR = Path(__file__).parent / "ontology" / "core"
DB_PATH = Path(__file__).parent / "terraweaver.db"


@dataclass
class Scenario:
    name: str
    task: str
    check: Callable[[AgentResult], bool]
    note: str = ""  # what a passing run demonstrates
    seed: dict = field(default_factory=dict)  # vars pre-loaded into the agent's namespace
    # Stands in for the human when a resolution skill asks a question.
    ask_user: Callable[[str, list], int | None] | None = None


def _picks(index: int):
    """A user who always answers with the given option."""
    return lambda question, options: index


def _picks_matching(fragment: str):
    """A user who picks the option mentioning something — steadier than a fixed index."""
    def choose(question, options):
        return next((i for i, o in enumerate(options) if fragment in o), None)
    return choose


def _declines(question, options):
    """A user who won't settle the question — the case must stay unresolved."""
    return None


def _resolution_of(result: AgentResult, kind: str) -> dict | None:
    for entry in result.resolutions:
        if entry["kind"] == kind:
            return entry
    return None


def _stored(store: Store, classes: dict, class_name: str) -> list:
    """Instances of a class as they exist in the world *after* the task ran."""
    return store.load_all(class_name, classes)


def _has_number_near(stdout: str | None, expected: float, tolerance: float) -> bool:
    if not stdout:
        return False
    for token in re.findall(r"-?\d+\.?\d*", stdout):
        try:
            if abs(float(token) - expected) <= tolerance:
                return True
        except ValueError:
            continue
    return False


def _counts_present(stdout: str | None, expected: Counter) -> bool:
    """Every group size shows up, as many times as it should.

    Deliberately blind to how the groups are labelled. An earlier version grepped for the
    raw enum values (`not_applied`), which quietly required the answer to leak internal
    identifiers at the user — the opposite of what a good answer does.
    """
    found = Counter(int(token) for token in re.findall(r"\b\d+\b", stdout or ""))
    return all(found[value] >= times for value, times in expected.items())


def _contains_email(stdout: str | None) -> bool:
    return bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", stdout or ""))


def _mentions_math(text: str | None) -> bool:
    text = (text or "").lower()
    return "mathemat" in text


def _mentions_ada(full_name: str | None) -> bool:
    text = (full_name or "").lower()
    return "ada love" in text


def make_basic_scenarios(classes: dict, store: Store) -> list[Scenario]:
    return [
        Scenario(
            name="create_person",
            task="Remember my new acquaintance: Katherine Johnson, email katherine@example.com.",
            check=lambda r: r.success and any(
                p.full_name == "Katherine Johnson" and p.email == "katherine@example.com"
                for p in _stored(store, classes, "Person")
            ),
            note="natural request -> new person present in the world state afterwards",
        ),
        Scenario(
            name="link_person_org",
            task="My friend Steve (email steve@acme.com) got a job at a company called Acme — put that in my records.",
            check=lambda r: r.success and any(
                p.full_name == "Steve" and p.organization is not None and p.organization.name == "Acme"
                for p in _stored(store, classes, "Person")
            ) and any(
                o.name == "Acme" and any(getattr(e, "full_name", None) == "Steve" for e in (o.employees or []))
                for o in _stored(store, classes, "Organization")
            ),
            note="natural request -> relationship persisted consistently on both sides",
        ),
        Scenario(
            name="distance_between_places",
            task=(
                "My office is in New York (coordinates 40.7128, -74.0060) and my home is in Los Angeles "
                "(coordinates 34.0522, -118.2437). How many kilometres apart are they?"
            ),
            check=lambda r: r.success and _has_number_near(r.stdout, 3935.75, tolerance=50),
            note="natural request -> numeric method result, known-answer haversine distance",
        ),
        Scenario(
            name="record_preference",
            task="My friend Ada Lovelace adores mathematics — remember that about her.",
            check=lambda r: r.success and any(
                _mentions_math(pref.value) and getattr(pref.subject, "full_name", None) == "Ada Lovelace"
                for pref in _stored(store, classes, "Preference")
            ),
            note="natural request -> fact persisted and linked to the right person",
        ),
        # --- read-only, against the prepared world ---
        Scenario(
            name="read_owner_name",
            task="What's my name?",
            check=lambda r: r.success and "Michael" in (r.stdout or ""),
            note="the assistant knows whose world this is (owner)",
        ),
        Scenario(
            name="read_self_name",
            task="And what's your name?",
            check=lambda r: r.success and "Tera" in (r.stdout or ""),
            note="the assistant knows who it is (me)",
        ),
        Scenario(
            name="read_colleagues_at_company",
            task="Which of my contacts work at TechCorp?",
            check=lambda r: r.success
            and "Ada Lovelace" in (r.stdout or "")
            and "Alan Turing" not in (r.stdout or "")
            and "Barbara Liskov" not in (r.stdout or ""),
            note="relationship traversal over the prepared world, and only the right person",
        ),
        Scenario(
            name="read_upcoming_interviews",
            task="What interviews do I have coming up?",
            # The DataWorks one is confirmed and ahead; the CloudNine one was cancelled and
            # is in the past — naming it would be answering from the calendar without reading it.
            check=lambda r: r.success
            and "DataWorks" in (r.stdout or "")
            and "CloudNine" not in (r.stdout or ""),
            note="reads scheduled events and respects their status",
        ),
        Scenario(
            name="read_owner_wants",
            task="Remind me, what did I want from a new job?",
            check=lambda r: r.success
            and "150000" in (r.stdout or "")
            and "remote" in (r.stdout or "").lower(),
            note="reads facts recorded about the owner themselves",
        ),
        Scenario(
            name="read_ambiguous_anna",
            task="Remind me, where does Annie work?",
            # Two contacts are called Annie and this conversation hasn't settled which. The
            # answer must not be picked by the agent — it has to ask first.
            check=lambda r: (_resolution_of(r, "uncertainty_resolution") or {}).get("status") == "resolved",
            note="two people share a name -> asks the user before answering",
            ask_user=_picks(0),
        ),
        # --- harder reading: several hops, the way a person actually asks ---
        Scenario(
            name="read_matching_vacancies",
            task="Have a look which of the openings actually fit what I'm looking for.",
            # Two hops: what the owner wants is recorded as facts about him, and only then
            # can the openings be filtered. Research Scientist fits on every count; Gameplay
            # Programmer fails all of them.
            check=lambda r: r.success
            and "Research Scientist" in (r.stdout or "")
            and "Gameplay Programmer" not in (r.stdout or ""),
            note="reads the owner's own criteria, then applies them to the openings",
        ),
        Scenario(
            name="read_contacts_at_applied_companies",
            task="Do I know anyone at the companies I've already applied to?",
            # Three classes deep: vacancies in play -> their companies -> people working there.
            check=lambda r: r.success
            and sum(name in (r.stdout or "") for name in ("Anna Peterson", "Alan Turing", "Ada Lovelace", "Anna Sullivan")) >= 3
            and "Barbara Liskov" not in (r.stdout or ""),
            note="join across vacancies, companies and contacts",
        ),
        Scenario(
            name="read_this_week",
            task="What have I got this week?",
            # The cancelled CloudNine interview is in the past and cancelled twice over.
            check=lambda r: r.success
            and "DataWorks" in (r.stdout or "")
            and "Alan" in (r.stdout or "")
            and "CloudNine" not in (r.stdout or ""),
            note="time window plus status, over the calendar",
        ),
        Scenario(
            name="read_best_paying_in_play",
            task="Of the openings I'm already pursuing, which one pays the most?",
            check=lambda r: r.success and "NLP Engineer" in (r.stdout or ""),
            note="filter by where things stand, then argmax on pay",
        ),
        Scenario(
            name="read_followup_with_anna",
            task="There was something I wanted to ask Annie — remind me what it was?",
            # Compound: two people answer to "Annie", so it has to be settled first, and only
            # then can the note attached to that person be found.
            check=lambda r: (_resolution_of(r, "uncertainty_resolution") or {}).get("status") == "resolved"
            and r.success
            and ("culture" in (r.stdout or "").lower() or "overtime" in (r.stdout or "").lower()),
            note="settle who is meant, then read what was noted about them",
            ask_user=_picks_matching("Peterson"),
        ),
        Scenario(
            name="dedup_misspelled_person",
            task="Note that Ada Lovelase is looking for a job right now.",
            # The world already holds "Ada Lovelace"; the misspelling is close but not exact, so
            # this must surface as an uncertainty for the user, not create a new person.
            check=lambda r: (
                r.success
                and (_resolution_of(r, "uncertainty_resolution") or {}).get("status") == "resolved"
                and len([p for p in _stored(store, classes, "Person") if _mentions_ada(p.full_name)]) == 1
            ),
            note="misspelled name -> uncertainty surfaced, settled with the user, no duplicate",
            ask_user=_picks(0),  # user confirms it's the existing Ada Lovelace
        ),
        Scenario(
            name="unresolved_ambiguity",
            task="Note that Ada Lovelase is looking for a job right now.",
            # Same case, but the user doesn't settle it: nothing may be guessed, and no
            # second Ada may appear in the world.
            check=lambda r: (
                (_resolution_of(r, "uncertainty_resolution") or {}).get("status") == "unresolved"
                and len([p for p in _stored(store, classes, "Person") if _mentions_ada(p.full_name)]) == 1
            ),
            note="user declines to disambiguate -> case stays unresolved, world untouched",
            ask_user=_declines,
        ),
        Scenario(
            name="contradiction_job_change",
            task="Ada Lovelace (ada@example.com) works at DataWorks now, not TechCorp.",
            # Email matches exactly, so identity is certain — but the stored employer disagrees.
            check=lambda r: (
                r.success
                and (_resolution_of(r, "contradiction_resolution") or {}).get("status") == "resolved"
                and any(
                    p.full_name == "Ada Lovelace"
                    and getattr(p.organization, "name", None) == "DataWorks"
                    for p in _stored(store, classes, "Person")
                )
            ),
            note="conflicting stored value -> contradiction surfaced and settled with the user",
            ask_user=_picks(0),  # user confirms the new employer
        ),
        Scenario(
            name="unsolvable_lookup",
            task="Find Grace Hopper in my contacts and remind me of her email.",
            # Nothing named Grace Hopper is seeded anywhere reachable. Declining (CANNOT_SOLVE)
            # or honestly reporting "not found" are both fine; fabricating a plausible-looking
            # email is the actual failure mode this scenario is trying to catch.
            check=lambda r: not _contains_email(r.stdout),
            note="no query/persistence capability exists yet — agent must not fabricate an answer",
        ),
    ]


def make_bulk_scenarios(classes: dict, companies: list, vacancies: list) -> list[Scenario]:
    seed = {"companies": companies, "vacancies": vacancies}
    vac_dicts = [
        {"title": t, "company": c, "stack": s, "salary_min": mn, "salary_max": mx, "remote": r, "status": st}
        for t, c, s, mn, mx, r, st in VACANCY_DATA
    ]

    top3_remote = [v["title"] for v in sorted((v for v in vac_dicts if v["remote"]), key=lambda v: -v["salary_max"])[:3]]
    python_vacs = [v for v in vac_dicts if any(s.lower() == "python" for s in v["stack"])]
    # "how much do they pay on average" is genuinely ambiguous between the low/high end of the
    # range and its midpoint — accept any of those readings rather than forcing one in the task.
    avg_salary_python_readings = [
        sum(v["salary_max"] for v in python_vacs) / len(python_vacs),
        sum(v["salary_min"] for v in python_vacs) / len(python_vacs),
        sum((v["salary_min"] + v["salary_max"]) / 2 for v in python_vacs) / len(python_vacs),
    ]
    status_counts = Counter(v["status"] for v in vac_dicts)
    company_counts = Counter(v["company"] for v in vac_dicts)
    top_company, top_company_count = max(company_counts.items(), key=lambda kv: kv[1])
    remote_not_applied = sum(1 for v in vac_dicts if v["remote"] and v["status"] == "not_applied")

    # Two of the three share a salary_max, so their order between themselves is arbitrary —
    # requiring one particular order marked correct answers wrong. Only the unique top one
    # has a defined position.
    top_salary = max(v["salary_max"] for v in vac_dicts if v["remote"])
    clear_leader = next(v["title"] for v in vac_dicts if v["remote"] and v["salary_max"] == top_salary)

    def check_top3_remote(r: AgentResult) -> bool:
        if not r.success or not r.stdout:
            return False
        positions = [r.stdout.find(title) for title in top3_remote]
        if any(p == -1 for p in positions):
            return False
        return r.stdout.find(clear_leader) == min(positions)

    return [
        Scenario(
            name="bulk_top3_remote_salary",
            task=(
                "I'm looking for remote work. Of the openings I've saved, show me the three "
                "best-paid ones that allow remote."
            ),
            check=check_top3_remote,
            note="natural request -> filter + sort over 26 seeded instances, order-sensitive",
            seed=seed,
        ),
        Scenario(
            name="bulk_avg_salary_python",
            task="I want a sense of the market: on average, what do the Python openings I saved pay?",
            check=lambda r: r.success and any(
                _has_number_near(r.stdout, reading, tolerance=1.5) for reading in avg_salary_python_readings
            ),
            note="natural request -> filter + aggregate (mean) over seeded instances",
            seed=seed,
        ),
        Scenario(
            name="bulk_count_by_status",
            task="How is my job search going overall — show me how many openings are at each stage.",
            check=lambda r: r.success and _counts_present(r.stdout, Counter(status_counts.values())),
            note="natural request -> group-by/count over seeded instances",
            seed=seed,
        ),
        Scenario(
            name="bulk_company_most_vacancies",
            task="Which of the companies I am considering has the most open positions right now?",
            # The question is which company; naming it is a complete answer, with or without
            # the count. Demanding the number too failed answers that were right.
            check=lambda r: r.success and top_company in (r.stdout or ""),
            note="natural request -> join across two seeded collections + argmax",
            seed=seed,
        ),
        Scenario(
            name="bulk_remote_not_applied_count",
            task="How many remote openings have piled up that I have not got round to applying for?",
            check=lambda r: r.success and _has_number_near(r.stdout, remote_not_applied, tolerance=0.4),
            note="natural request -> compound filter + count over seeded instances",
            seed=seed,
        ),
    ]


def _indent(text: str | None) -> str:
    if not text:
        return "    (none)"
    return "\n".join(f"      {line}" for line in text.splitlines())


build_world = load_world(DEFAULT_WORLD)


def build_suite(db_path: str | None = None, world_name: str = DEFAULT_WORLD) -> tuple[dict, dict, Store, list[Scenario]]:
    """Everything a run needs: specs, classes, a store holding the world, and the scenarios."""
    global build_world
    build_world = load_world(world_name)
    specs = load_specs(ONTOLOGY_DIR)
    classes = build_classes(specs, IMPLS)
    store = Store(db_path or str(DB_PATH))
    store.clear_all()
    build_world(classes, store)
    companies = store.load_all("Organization", classes)
    vacancies = store.load_all("Vacancy", classes)
    scenarios = make_basic_scenarios(classes, store) + make_bulk_scenarios(classes, companies, vacancies)
    return specs, classes, store, scenarios


DEFAULT_EXPERIMENT = "exp01_staged_agent"


def load_solver(experiment: str = DEFAULT_EXPERIMENT):
    """The agent under test. The world is shared; only how it's worked with varies."""
    module = import_module(f"experiments.{experiment}.agent")
    return module.solve


def run_scenario(scenario: Scenario, specs: dict, classes: dict, store: Store, solver=None) -> tuple[AgentResult, bool]:
    """Run one scenario from the same known world state and score it."""
    solver = solver or load_solver()
    # Reset first, so a state-based check can't be satisfied by an earlier scenario's leftovers.
    store.clear_all()
    build_world(classes, store)
    result = solver(
        scenario.task,
        specs,
        classes,
        seed=scenario.seed,
        store=store,
        world=World(store, classes),
        ask_user=scenario.ask_user,
        task_id=scenario.name,
    )
    try:
        correct = scenario.check(result)
    except Exception as exc:  # a broken check shouldn't crash the whole run
        correct = False
        result.message += f" [check raised {type(exc).__name__}: {exc}]"
    return result, correct


def main():
    args = sys.argv[1:]
    show_code = "--code" in args
    experiment = next((a.split("=", 1)[1] for a in args if a.startswith("--exp=")), DEFAULT_EXPERIMENT)
    world_name = next((a.split("=", 1)[1] for a in args if a.startswith("--world=")), DEFAULT_WORLD)
    filters = [a for a in args if not a.startswith("--")]
    solver = load_solver(experiment)

    specs, classes, store, scenarios = build_suite(world_name=world_name)
    if filters:
        scenarios = [s for s in scenarios if any(f in s.name for f in filters)]

    rows = []
    for scenario in scenarios:
        result, correct = run_scenario(scenario, specs, classes, store, solver)
        rows.append((scenario, result, correct))

    print(f"{'scenario':<28} {'result':<8} {'rounds':<7} message")
    print("-" * 80)
    for scenario, result, correct in rows:
        status = "PASS" if correct else "FAIL"
        print(f"{scenario.name:<28} {status:<8} {result.rounds:<7} {result.message}")
        if not correct or show_code:
            print(f"    code:\n{_indent(result.code)}")
            print(f"    stdout:\n{_indent(result.stdout)}")
            if result.error:
                print(f"    error: {result.error}")

    n_correct = sum(1 for *_, c in rows if c)
    avg_rounds = sum(r.rounds for _, r, _ in rows) / len(rows) if rows else 0
    print("-" * 80)
    print(f"{n_correct}/{len(rows)} scenarios correct, avg {avg_rounds:.1f} rounds/scenario  [{experiment} / {world_name}]")


if __name__ == "__main__":
    main()
