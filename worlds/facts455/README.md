# facts455

A world one recording run built, frozen so questions can be asked of it without building it again.

- facts given: 460
- entities: 519
- links: 468
- statements in the record: 2762
- relation types the recorder defined: 32
- frozen: 2026-09-24 01:20
- size: 16 MB, most of it the meaning index — the vectors a question searches by, which are derived and could be rebuilt, at the cost of a model run.

Open it the way a run does — the base classes plus what this world grew:

```python
from terraweaver import growth, ontology as ont
from terraweaver.runtime import WorldRuntime
specs = growth.apply_growth(ont.base_specs(Path('ontology/core')),
                            growth.load_grown(Path('worlds/facts455/grown')))
rt = WorldRuntime('worlds/facts455/world.db', fixture=None, specs=specs, selves=True)
```

What it holds is what the recorder put there, right and wrong: `experiments/check_expected.py worlds/facts455` reads it against what the facts owe.
