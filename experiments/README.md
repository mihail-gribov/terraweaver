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
      01_relation_formalisation/   <- a numbered experiment: one question, its own directory
      exp01_staged_agent/          <- an agent variant, driven through class -> objects -> code
      exp02_literate_dialogue/     <- another agent variant
      README.md

Two kinds of thing live here, and they are told apart by the name.

`expNN_<name>/` is an **agent variant**: a package exposing a `solve(...)` with the signature
`run_scenarios.py` calls. Add one by copying the closest existing variant and changing what you
want to test.

`NN_<name>/` is an **experiment**: one question, its own directory, and everything that question
needs inside it. The number is the order they were started in and never changes.

## A numbered experiment

**The user starts them.** Not a thing to be helpful with: an experiment is a question somebody
has decided is worth the money, and one nobody asked for produces a number nobody reads.

What is in one:

    README.md    the question, what it runs against, how to run it, what would count as an
                 answer, and what the runs found. Written before the first run, not after
    the code     the piece under test, written here rather than in `terraweaver/`
    results/     one file per run, with the whole trace and the commit it ran at
    earlier/     iterations that came before, kept as they were rather than summarised

**The world is the real one.** `terraweaver/` is not forked, stubbed or bypassed: an experiment
opens a world and drives it through the doors a host goes through, so a refusal it hits is a
refusal a host would hit. What is written in the experiment is the piece being tried, and when it
earns its place it moves into the world and the experiment keeps the measurement that paid for it.

**The world starts from the base** unless the question is about a fixture — `Thing`, `Related`,
`Person`, `AIAgent`, `Event`. A fixture already holds a vocabulary somebody wrote by hand, and a
run against one cannot tell what the world arrived at from what it was handed.

## Reading results

A single run measures almost nothing. The same suite, against unchanged code, has returned
14/14, then 11/13, then passed again — the spread between runs is comparable to the
differences we'd want to detect. Any claim about one agent being better than another needs
repeated runs, not one.
