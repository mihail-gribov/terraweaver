# Experiments

One world, many agents.

`terraweaver/` is the world and stays shared across every experiment: the ontology, the
SQLite store, identity matching, uncertainty/contradiction resolution, the session. An
experiment never forks it — otherwise results stop being comparable, and a difference in
outcome could just as well be a difference in the world.

What varies is **how the agent works with that world**: how the model is driven, what it's
shown, how many stages it goes through, where decisions are taken away from it. That is the
subject of an experiment.

`run_scenarios.py` is the shared measuring stick — the same tasks, the same known answers,
the same world state before each one. Whichever agent is under test answers them.

## Layout

    experiments/
      exp01_staged_agent/   <- agent driven through class -> objects -> code stages
      README.md

Each experiment is a package exposing a `solve(...)` with the signature `run_scenarios.py`
calls. Add a new one by copying the closest existing experiment and changing what you want
to test.

## Reading results

A single run measures almost nothing. The same suite, against unchanged code, has returned
14/14, then 11/13, then passed again — the spread between runs is comparable to the
differences we'd want to detect. Any claim about one agent being better than another needs
repeated runs, not one.
