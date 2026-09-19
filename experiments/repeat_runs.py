"""Run the suite several times and report what's stable and what isn't.

A single run measures almost nothing here: the same suite, against unchanged code, has
returned 14/14, 11/13 and 10/13. That spread is as large as the differences we'd want to
detect, so one run can't tell a fix from a lucky sample. Repeats can.

The per-scenario pass rate is the useful number. A scenario that passes 5/5 or fails 0/5 is
telling you something; one at 3/5 is telling you it's unstable, which is itself a finding —
and the ones to look at first, since an unstable scenario is where the agent's behaviour
actually varies.

Run: python3 experiments/repeat_runs.py [N] [--exp=...] [--world=...] [name-substring ...]
"""
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from run_scenarios import DEFAULT_EXPERIMENT, build_suite, load_solver, run_scenario
from worlds import DEFAULT_WORLD

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def main() -> int:
    args = sys.argv[1:]
    repeats = next((int(a) for a in args if a.isdigit()), 3)
    experiment = next((a.split("=", 1)[1] for a in args if a.startswith("--exp=")), DEFAULT_EXPERIMENT)
    world_name = next((a.split("=", 1)[1] for a in args if a.startswith("--world=")), DEFAULT_WORLD)
    filters = [a for a in args if not a.startswith("--") and not a.isdigit()]

    specs, classes, store, scenarios = build_suite(world_name=world_name)
    if filters:
        scenarios = [s for s in scenarios if any(f in s.name for f in filters)]
    solver = load_solver(experiment)

    passes: dict[str, int] = defaultdict(int)
    rounds: dict[str, list] = defaultdict(list)
    messages: dict[str, list] = defaultdict(list)

    started = time.time()
    for attempt in range(1, repeats + 1):
        print(f"--- run {attempt}/{repeats} ---", flush=True)
        for scenario in scenarios:
            result, correct = run_scenario(scenario, specs, classes, store, solver)
            passes[scenario.name] += int(correct)
            rounds[scenario.name].append(result.rounds)
            if not correct:
                # The message alone ("script raised an error") doesn't say what went wrong,
                # and by the next run the evidence is gone.
                messages[scenario.name].append({
                    "message": result.message,
                    "error": result.error,
                    "stdout": (result.stdout or "")[:400],
                    "code": (result.code or "")[-800:],
                })
            print(f"  {'PASS' if correct else 'FAIL'}  {scenario.name}", flush=True)

    print()
    print(f"{'scenario':<30} {'passed':<9} {'avg rounds':<11} note")
    print("-" * 84)
    unstable = []
    for scenario in scenarios:
        name = scenario.name
        hits = passes[name]
        mean = sum(rounds[name]) / len(rounds[name])
        if 0 < hits < repeats:
            note = "UNSTABLE — same code, different outcome"
            unstable.append(name)
        elif hits == 0:
            note = (messages[name][0]["message"][:44] if messages[name] else "fails consistently")
        else:
            note = ""
        print(f"{name:<30} {hits}/{repeats:<7} {mean:<11.1f} {note}")

    total = sum(passes.values())
    possible = len(scenarios) * repeats
    print("-" * 84)
    print(f"{total}/{possible} across {repeats} runs, {len(unstable)} unstable, "
          f"{time.time() - started:.0f}s  [{experiment} / {world_name}]")
    if unstable:
        print(f"unstable: {', '.join(unstable)}")

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"{stamp}-{experiment}-{world_name}.json"
    path.write_text(json.dumps({
        "experiment": experiment,
        "world": world_name,
        "repeats": repeats,
        "scenarios": {
            s.name: {"passed": passes[s.name], "rounds": rounds[s.name], "failures": messages[s.name]}
            for s in scenarios
        },
    }, ensure_ascii=False, indent=2))
    print(f"saved: {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
