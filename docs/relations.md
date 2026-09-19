# Relations

Design agreed and implemented 2026-09-19 (`terraweaver/relations.py`, relation types in `ontology/core/`, tests in `tests/test_relations.py`). Participation is defined but `Event.participants` / `Project.participants` still exist.

## Why

Today a link between two entities is just a ref attribute (`Person.organization`,
`Event.participants`). The link itself has no type and no data of its own: a job can't carry a
role and dates, "Darren's older brother Kevin" or "the manager of Kevin's department" can't be
said at all, and `Person.relationship` is a free string about the owner.

What hosts do without relations — seen in the MemOps B04 scenario (s17) with Haiku: the
department became an unattached `Organization`; "Linda manages B04" was written three ways at once
(her `job_title`, a sentence in the department's `notes`, a `Preference` fact "manages B04"); the
transfer date lived only inside a comment's text. A later conversation couldn't find who runs
Kevin's department.

## A relation is an instance

A relation is an entity that links two others: it has a `subject` and an `object`, and
everything else an entity has — its own attributes, a validity period, value history, comments.
Each relation type is a class in the ontology, like `Person`, with an extra `relation` section
describing how the link behaves:

    {
      "name": "Membership",
      "description": "A person belonging to an organization: a job, studies, a club.",
      "relation": {
        "from": "Person", "to": "Organization",
        "symmetric": false, "asymmetric": true, "irreflexive": true,
        "transitive_via": "PartOf",
        "reverse": "members"
      },
      "attributes": [
        {"name": "role",    "type": "str", "description": "Position or title in it."},
        {"name": "kind",    "type": "enum[employment, study, club, volunteer, other]"},
        {"name": "primary", "type": "bool", "description": "The main one — what Person.organization shows."},
        {"name": "team",    "type": "str"}
      ]
    }

The world checks the characteristics in code; the specific name of a relation ("older
brother", "dentist", "landlord") is a label inside its type, written the way the user said it.

## Types

A type says what kind of relation it is — how it behaves — not what it is called.

| Type | From → to | Cardinality | Characteristics | Labels inside the type |
|---|---|---|---|---|
| **Kin** | Person ↔ Person | many-to-many | symmetric (a label per side), irreflexive, doesn't end | brother, mother, grandmother, cousin, in-laws |
| **Partner** | Person ↔ Person | one-to-one at any point in time | symmetric, irreflexive | wife, husband, girlfriend, partner, fiancée |
| **Social** | Person ↔ Person | many-to-many | symmetric, irreflexive | best friend, friend, acquaintance, neighbour, former colleague |
| **Membership** | Person → Organization | many-to-many; the primary one many-to-one at any point in time | asymmetric, transitive via PartOf | job, studies, club, volunteering |
| **Authority** | Person → Person / Organization | many-to-one at any point in time | asymmetric, acyclic, irreflexive | manager, head of department, supervisor |
| **Service** | Person / Organization → Person | many-to-many | asymmetric | doctor, lawyer, landlord, recruiter, tutor, coach, mentor |
| **PartOf** | Organization → Organization, Place → Place | many-to-one at any point in time | transitive, asymmetric, acyclic | department, branch, team; district of a city |
| **Located** | Person / Organization / thing → Place | many-to-one at any point in time for home and office; many-to-many otherwise | transitive along place nesting | lives in, office at, kept at |
| **Ownership** | Person / Organization → thing / Place | one-to-many; many-to-many when joint | asymmetric | owns, rents, borrowed |
| **Participation** | Person / Organization → Event / Project | many-to-many | asymmetric | attendee, organizer, speaker |
| **Related** | anything → anything | many-to-many | none — the world infers nothing | godfather, loan guarantor, "my sister's former roommate" |

**Related** is the free type, for a link none of the others fits. Direction is as written, and
the world assumes no symmetry, transitivity or limits. A label and a description are required
(checked in code), so it doesn't become a dump. If the label is one another type knows
("brother", "manager", "dentist"), the world points to that type in the result — the write still
goes through. A label that keeps recurring in Related is a missing type: counted like attribute
and procedure usage, later for Nemotron to propose mapping it to an existing type or a new one.

Terms, as used in the spec fields:

- **cardinality** — one-to-one, one-to-many / many-to-one, many-to-many;
- **functional** — at most one object per subject; **inverse functional** — at most one subject
  per object (OWL property characteristics);
- **functional at any point in time** — at most one *current* at each moment, many over a
  lifetime (temporal cardinality); checked by overlapping validity periods, not by "now":
  divorced in 2020 and married in 2022 is no conflict;
- **symmetric / asymmetric**, **transitive**, **reflexive / irreflexive**;
- **acyclic** — asymmetric with no cycles through the transitive closure (graph term, not OWL);
- **participation constraint** — whether an entity must have such a relation (total / partial);
  all of ours are optional.

Spec fields: `"symmetric"`, `"asymmetric"`, `"transitive"`, `"transitive_via"`, `"acyclic"`,
`"irreflexive"`, `"functional": "at_any_time"`, `"inverse_functional"`, `"reverse"` (the name read
from the object's side).

## Relations in a class's description

A class is described not only by its attributes but by the relations characteristic of it — what
it is typically linked to, and how. Two sources, no duplication:

- **which** relations a class takes part in comes from the relation types themselves: Membership
  goes Person → Organization, so Person lists "membership → Organization" and Organization lists
  "members ← Person". One source of truth, nothing to keep in sync;
- **what they mean for this class** — typical labels and notes — lives in the class spec, in a
  `relations` section: for Organization, PartOf is "a department or branch of another
  organization"; for Place, "a district or building within a larger place".

`describe_world` shows them under each class, after the attributes:

    class Person:
        full_name: str ...
        relations:
          kin ↔ Person                       brother, mother, cousin, in-laws
          partner ↔ Person                   wife, girlfriend — one at a time
          social ↔ Person                    best friend, acquaintance, neighbour
          membership → Organization          role, kind, primary, team — job, studies, club
          authority → Person / Organization  manager — one at a time, no cycles
          service ← Person / Organization    their doctor, landlord, recruiter
          ...

`relate` accepts only relations the type allows for that pair of classes; Related is always
allowed.

## Time

Relations have the same lifetime as instances: `starts` / `until` / `ttl`; ordinary reads show
current relations, `history=True` shows all. A relation that ends isn't deleted — it becomes
history ("former manager" is an Authority with `until`; a job change closes the old Membership
and opens a new one); `forget` is a separate operation. Attributes of a relation keep their
history like any entity's (`membership.history("role")`). Transitivity is evaluated at a moment:
a department moved to another company links its people to the new one only from that date.

## Host API

    m = kevin.relate(b04, "membership", role="vendor logistics lead", starts=date(2026, 1, 15))
    m.role = "team lead"                   # assignment; the old role stays in history
    m.comment("moved from Procurement")    # remarks on the relation itself
    linda.relate(b04, "authority", label="manager")
    b04.relate(company, "part_of")
    kevin.relate(darren, "kin", label="older brother")

    kevin.relations("membership")          # the relations, with their attributes
    kevin.related("membership")            # the entities at the other end: B04, and via PartOf the company
    b04.related("members")                 # read from the object's side by the reverse name
    darren.related("kin")                  # symmetric: seen from both ends

An unknown attribute on a relation is an error, as on entities. A violated characteristic — a
second current partner, a second current manager, a cycle of authority — is reported by the
world, not silently accepted.

## What changes around it

- `Person.organization` and `Person.job_title` become derived from the primary Membership;
  assigning `person.organization = x` closes the old primary membership with a date and opens a
  new one, so a job history comes for free.
- `Person.relationship` ("friend", "former manager") becomes relations between the owner and the
  person.
- Matching: refs in `find` conditions compare by id, not by name (today two different people
  with the same name would count as one).

## Open questions (defaults proposed)

1. Mentor, coach, teacher: **Service** (they help, they don't rule) — not Authority.
2. Participation replacing `Event.participants` / `Project.participants`, so a participant can
   have a role: **later**, a separate change.
3. In-laws: **Kin** with a label, no separate type.

## Plan

1. `Relation(Entity)` base: subject/object, characteristics from the spec checked in code;
   `relate` / `relations` / `related` on every entity; reverse names and transitivity.
2. The ten types plus Related as JSON classes with their attributes; a `relations` section in
   entity class specs for class-specific labels; `describe_world` lists each class's relations.
3. `Person.organization` / `job_title` derived from Membership, `relationship` as owner
   relations; fixture migrated.
4. Re-run the MemOps relational scenarios (s16, s17) and compare with the run before the change:
   world 3/4 (Haiku failed s17), baseline 4/4.
