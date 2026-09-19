# Schema growth: new attributes

In v1 the set of classes is fixed, but attributes can grow. The rule that keeps this
consistent: **what isn't settled can't be read.**

## Reading

A read returns exactly what the schema has. An attribute that isn't in the schema doesn't
exist; a value that isn't stored means the information isn't there. Nothing pending is ever
visible to a read or to a procedure.

## Writing

A host knows the structure (`describe_world()`), so an attribute it doesn't find there must be
proposed explicitly, with a description:

```python
Person.ensure(full_name="Аня", favorite_cuisine=New("итальянская", "which cuisine the person prefers"))
```

Enforced in code, not asked for in a prompt:

- an unknown attribute passed without `New(...)` is an error that says how to propose it;
- a known attribute wrapped in `New(...)` is an error too — the host is expected to know the
  structure, and this is how a near-duplicate gets caught at the door;
- assigning an undeclared attribute directly (`person.x = ...`) is an error. Today it is
  silently accepted and then lost on save.

The write succeeds for everything known; the proposed attribute is accepted into a pending
area, and the host gets an honest receipt: "accepted, `favorite_cuisine` is under review".

## Pending area

A separate table, `pending_attrs`: instance, proposed name, description, raw value, who sent
it, when. Not `values_` — that is what guarantees reads can't see it. The raw value and its
source are kept even after a decision, so a decision can be revisited.

## Nemotron decides, asynchronously

The world integrates proposals when convenient, not in the host's request. Waiting is an
advantage: by then there are several example values, sometimes from several agents, and the
decision is made on data rather than on a single case. Proposals of the same thing are decided
together.

Before any model call, deterministic checks: name normalization (case, snake_case, plural,
`is_`/`has_`, transliteration, a small synonym list), a known alias, a value already reachable
through a link, a value that coincides with an existing attribute on the same instances.

Possible outcomes:

- **Synonym of an existing attribute** — values move there; the host's name becomes an alias,
  so next time it maps deterministically, without Nemotron.
- **Duplicate through a link** (`company_name` → `organization.name`) — the value becomes a
  reference, via `Organization.ensure`.
- **New attribute** — Nemotron picks the canonical name (from the ontology library when it has
  one) and the type, converts the values (`"150k"` → `150000.0`) and adds it to the class spec.
- **A one-off fact** — stays a fact (`Preference`) until it recurs across instances.
- **Noise** — rejected, with the reason logged.

Integration is one transaction: spec change, value migration, pending rows cleared. The
world's schema has a version number; `describe_world()` returns it, so a host can see the
structure changed.

## Delayed contradictions

A decision can reveal a conflict after the user has left — `company` turns out to be the
existing `organization`, and the stored value differs. It goes into a queue of pending
resolutions that the world presents at the next interaction. Until the user decides, the world
is not touched.

## Why consistency holds

- Pending values are invisible to reads and procedures, so nothing is built on them.
- Only Nemotron moves a proposal into the schema, and it knows what is provisional and what is
  settled.
- Integration is atomic.
- Changes are additive; a rename or merge that removes a name keeps it as an alias, so host
  code and procedures using it don't break. Destructive changes need the user's confirmation.

## Forgetting attributes

Attributes follow the same lifecycle as procedures: kept while used, forgotten when not.
Usage is measured on the world itself:

- **fill rate** — share of a class's instances with a non-empty value, straight from `values_`;
- **writes** — how often values change; needs a timestamp per value, which `values_` doesn't
  have yet;
- **reads** — how often host code and procedures read the attribute; `Entity.__getattribute__`
  already counts entity reads, it just needs to count per attribute.

Reads weigh more than fill: `birth_date` may be set for few people and still be asked about.
An attribute rarely filled *and* rarely read is a candidate for forgetting.

Rules:

- Only learned attributes are forgotten automatically; those from the core ontology stay.
- An attribute a procedure depends on isn't forgotten while the procedure is active.
- Forgetting hides the attribute from the schema and from `describe_world()`; the values are
  archived, not deleted. Deleting data is destructive and needs the user's confirmation.
- A new proposal matching an archived attribute revives it, values included.

## Open questions

- Should the host that proposed an attribute see its own pending value in the same session,
  or strictly nothing until integration?
- When does integration run: on a timer, on N accumulated proposals, or at session end?
