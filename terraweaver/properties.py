"""What the links in this world actually do, measured rather than declared.

Every relation type carries formal properties — one at a time, reads the same from both ends,
never a cycle — and those properties are what let the world check anything. We wrote them by
hand: a person has one mother, a company one chief executive. That works until the world meets a
kind of link nobody wrote rules for, and then it can check nothing at all.

So the world measures. For each type and each role it looks at what the data has ever shown:

    chances to break  how often the data even had the opportunity — a rule only means
                      something where it could have been broken and wasn't
    most at once      has any subject ever had two of these at overlapping times?
    both directions   has the same pair ever been recorded each way round?
    self-links        has anything ever pointed at itself?
    cycles            does following the link ever come back where it started?

From that come two lists, and the second is the more valuable:

- **supported**: the type doesn't declare it, and the data has never contradicted it. A candidate
  property, with the number of cases behind it — evidence, not proof. Nobody's world has two
  mothers in it, but nor does it have many mothers at all, and "never seen twice in eleven cases"
  is a proposal, not a law. What settles it is knowledge about the world in general, which is the
  model's to bring (docs/architecture.md: a judgement about language or the world, kept once and
  used for everyone) — and it lands as a proposal that is applied only after a rebuild shows
  nothing broke.
- **contradicted**: the type declares it and the data breaks it. That is a rule this world would
  now refuse to obey, and either the rule is wrong or something was recorded that shouldn't have
  been. Either way somebody should look.

Nothing here changes a type. Measuring is deterministic and cheap, so it happens on a tick;
deciding is not, and belongs to the agenda.
"""
from dataclasses import dataclass, field

from terraweaver import relations, timeutil


@dataclass
class Observed:
    """What one relation type was seen doing."""

    name: str
    kind: str
    count: int
    most_per_subject: int = 0
    most_per_object: int = 0
    both_directions: int = 0
    self_links: int = 0
    cycles: int = 0
    # How many subjects/objects ever held more than one of these at all. Where nobody ever had
    # two, "never two at once" says nothing: there was no chance to break the rule.
    subjects_with_several: int = 0
    objects_with_several: int = 0
    chains: int = 0
    per_role: dict = field(default_factory=dict)    # role -> most ever held at once by one subject
    role_chances: dict = field(default_factory=dict)  # role -> subjects who had several of this
                                                      # type at all, and so could have had two

    ENOUGH = 3  # chances to break a rule before "it never happened" is worth saying out loud

    def supports(self, spec: dict) -> list[str]:
        """Properties the data had the chance to break and never did, and the type doesn't say.

        Rarity is not evidence. A world with three mothers in it shows nothing about how many
        mothers a person has; a world where eleven people each have several relatives and not one
        has two mothers at once shows something. So every line here counts the chances, and says
        how many there were — it is a proposal to be weighed, not a finding."""
        out = []
        if self.subjects_with_several >= self.ENOUGH and self.most_per_subject == 1 \
                and spec.get("functional") != "at_any_time":
            out.append(f"functional — {self.subjects_with_several} had several and never two at once")
        if self.objects_with_several >= self.ENOUGH and self.most_per_object == 1 \
                and spec.get("inverse_functional") != "at_any_time":
            out.append(f"inverse_functional — {self.objects_with_several} chances, never two at once")
        if self.chains >= self.ENOUGH and not self.cycles and not spec.get("acyclic"):
            out.append(f"acyclic — {self.chains} chains, none came back")
        if self.both_directions >= self.ENOUGH and not spec.get("symmetric"):
            out.append(f"symmetric — {self.both_directions} pairs recorded both ways")
        for role, most in sorted(self.per_role.items()):
            declared = next((r.get("max") for r in spec.get("roles", []) if r["name"] == role), None)
            chances = self.role_chances.get(role, 0)
            if most == 1 and declared is None and chances >= self.ENOUGH:
                out.append(f"role {role}: at most one — {chances} had several relatives, "
                           f"never two {role}s")
        return out

    def contradicts(self, spec: dict) -> list[str]:
        """Rules the type declares that this world's own data breaks."""
        out = []
        if spec.get("functional") == "at_any_time" and self.most_per_subject > 1:
            out.append(f"declared one at a time per subject, but {self.most_per_subject} were held at once")
        if spec.get("inverse_functional") == "at_any_time" and self.most_per_object > 1:
            out.append(f"declared one at a time per object, but {self.most_per_object} were held at once")
        if spec.get("irreflexive", True) and self.self_links:
            out.append(f"declared irreflexive, but {self.self_links} point at themselves")
        if spec.get("acyclic") and self.cycles:
            out.append(f"declared acyclic, but {self.cycles} cycle(s) exist")
        for role, most in sorted(self.per_role.items()):
            limit = next((r.get("max") for r in spec.get("roles", []) if r["name"] == role), None)
            if limit is not None and most > limit:
                out.append(f"role {role}: at most {limit} declared, {most} seen at once")
        return out

    def __repr__(self):
        return (f"<{self.name}: {self.count} links, most per subject {self.most_per_subject}, "
                f"per object {self.most_per_object}>")


def observe(world, name: str) -> Observed:
    """Measure one relation type against everything recorded of it."""
    cls = world.classes[name]
    spec = relations.spec(cls)
    links = world.all(name, limit=None, history=True)
    seen = Observed(name, spec.get("kind", name.lower()), len(links))
    by_subject: dict = {}
    by_object: dict = {}
    by_role: dict = {}
    role_counts: dict = {}
    pairs = set()
    for link in links:
        subject, obj = getattr(link, "subject", None), getattr(link, "object", None)
        if subject is None or obj is None:
            continue
        if relations.same(subject, obj):
            seen.self_links += 1
        by_subject.setdefault(subject.id, []).append(link)
        by_object.setdefault(obj.id, []).append(link)
        role = getattr(link, "role", None)
        if role:
            by_role.setdefault((subject.id, role), []).append(link)
            role_counts[role] = role_counts.get(role, 0) + 1
        if (obj.id, subject.id) in pairs:
            seen.both_directions += 1
        pairs.add((subject.id, obj.id))
    seen.most_per_subject = max((_at_once(group) for group in by_subject.values()), default=0)
    seen.most_per_object = max((_at_once(group) for group in by_object.values()), default=0)
    seen.subjects_with_several = sum(1 for group in by_subject.values() if len(group) > 1)
    seen.objects_with_several = sum(1 for group in by_object.values() if len(group) > 1)
    for (subject_id, role), group in by_role.items():
        seen.per_role[role] = max(seen.per_role.get(role, 0), _at_once(group))
        if len(by_subject.get(subject_id, [])) > 1:  # they had several of this type at all
            seen.role_chances[role] = seen.role_chances.get(role, 0) + 1
    seen.cycles, seen.chains = _cycles(links)
    return seen


def observe_all(world) -> list[Observed]:
    return [observe(world, name) for name in relations.relation_classes(world.classes)]


def findings(world) -> tuple[list[str], list[str]]:
    """(what the data supports and the type doesn't say, what the type says and the data breaks)."""
    supported, broken = [], []
    for seen in observe_all(world):
        spec = relations.spec(world.classes[seen.name])
        supported += [f"{seen.name}: {line} — {seen.count} recorded" for line in seen.supports(spec)]
        broken += [f"{seen.name}: {line}" for line in seen.contradicts(spec)]
    return supported, broken


def _at_once(links: list) -> int:
    """The most of these that ever held at the same time — periods, not a plain count: two jobs
    one after the other are not two jobs at once."""
    moments = []
    for link in links:
        start = timeutil.as_datetime(getattr(link, "valid_from", None) or link.created_at)
        end = getattr(link, "valid_until", None)
        moments.append((start, 1))
        if end is not None:
            moments.append((timeutil.as_datetime(end), -1))
    most = held = 0
    for _, change in sorted(moments, key=lambda pair: (pair[0], -pair[1])):
        held += change
        most = max(most, held)
    return most


def _cycles(links: list) -> tuple[int, int]:
    """(loops found, chains of two steps or more) — the second says whether a loop was even
    possible. A link that never joins to another cannot come back on itself."""
    edges: dict = {}
    for link in links:
        subject, obj = getattr(link, "subject", None), getattr(link, "object", None)
        if subject is not None and obj is not None:
            edges.setdefault(subject.id, set()).add(obj.id)
    found = chains = 0
    for start in edges:
        seen, frontier = {start}, list(edges.get(start, ()))
        depth = 0
        while frontier:
            node = frontier.pop()
            if node == start:
                found += 1
                break
            if node in seen:
                continue
            seen.add(node)
            onward = list(edges.get(node, ()))
            depth = max(depth, 1 if onward else 0)
            frontier += onward
        chains += depth
    return found, chains
