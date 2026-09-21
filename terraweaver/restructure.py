"""Taking the notes apart: what the world already had a place for, and what it never did.

A host writes prose when it cannot see anywhere better to put something. That happens for two
quite different reasons, and telling them apart is the whole point of this pass:

**It had a home and the host did not find it.** `ceo_of` exists and the fact went into a
description anyway. Nothing is missing from the world — the guide is too long, the name is not
the one that was looked for, the lookup was not made. Adding an attribute here makes it worse:
then there are two ways to say one thing.

**It had no home.** "Ferdowsi is famous for Shahnameh" fits nothing, so it was dropped or written
out as a sentence. That is a real gap, and the class wants another attribute, or the world wants
another relation type.

So the order is fixed: **fit to what exists first, propose only the residue.** The two counts that
come out are worth as much as the repair — how much moved into existing slots measures our guide,
how much needed something new measures our schema.

**The evidence is counted, never read.** Which classes accumulate text against values, which notes
repeat word for word, and — the useful one — which notes are the same sentence with different
things in it:

    "Ferdowsi is famous for Shahnameh"
    "Nobuhiro Watsuki is famous for Rurouni Kenshin"

Strip the names the world already knows and those are one shape seen twice, with the values
already collected. No sentence is interpreted to find that; it is arithmetic over strings, the
same kind `did_you_mean` does. A shape that turns up under several classes is not several
attributes — it is one predicate wanting several ends, which is what a relation type is for.

**The judgement is the world's own model.** Naming the attribute, seeing that "is known for" and
"is famous for" are one idea, deciding that a shape belongs on a parent rather than on each class
— that is meaning, and arithmetic cannot do it. It runs off the hot path, through `llm.py`
(Nemotron by default), and what comes back is a proposal, not a change.

**What is applied is a conclusion with a basis.** A value read out of a note is written with
`facts.conclude` and the note as its basis: the world's own weakest kind of statement, retractable
one at a time, and the note stays exactly where it was. Being wrong here costs a retraction, not
a repair.
"""
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

NOTE_SLOTS = ("descriptions", "notes", "description")
NAME_SLOTS = ("full_name", "name", "title", "label")
WORTH_LOOKING = 3       # a shape seen fewer times than this is a note, not a pattern


def _rows(conn, sql, args=()):
    try:
        return list(conn.execute(sql, args))
    except sqlite3.Error:
        return []


def _class_tables(conn) -> list[str]:
    return [r[0] for r in _rows(conn, "select name from sqlite_master where type='table' "
                                      "and name like 'facts_%'")]


def known_names(conn) -> dict[str, str]:
    """Every name the world knows, longest first — what gets taken out of a sentence."""
    names = {}
    for table in _class_tables(conn):
        class_name = table[len("facts_"):]
        for subject, slot, value in _rows(
                conn, f'select subject, slot, value from "{table}" where slot in '
                      f'({",".join("?" * len(NAME_SLOTS))})', NAME_SLOTS):
            try:
                said = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                said = value
            if isinstance(said, str) and len(said.strip()) > 2:
                names[said.strip()] = class_name
    return dict(sorted(names.items(), key=lambda kv: -len(kv[0])))


def prose_share(conn) -> dict[str, dict]:
    """Per class: how much of what was said went into text rather than into values."""
    out = {}
    for table in _class_tables(conn):
        class_name = table[len("facts_"):]
        total = _rows(conn, f'select count(*) from "{table}"')
        if not total or not total[0][0]:
            continue
        text = _rows(conn, f'select count(*) from "{table}" where slot in '
                           f'({",".join("?" * len(NOTE_SLOTS))})', NOTE_SLOTS)
        said, whole = (text[0][0] if text else 0), total[0][0]
        out[class_name] = {"statements": whole, "in_text": said,
                           "share": round(said / whole, 2) if whole else 0.0}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["share"]))


def notes(conn) -> list[tuple[str, str, str]]:
    """(class, subject, text) for everything that went into a text slot."""
    found = []
    for table in _class_tables(conn):
        class_name = table[len("facts_"):]
        for subject, value in _rows(
                conn, f'select subject, value from "{table}" where slot in '
                      f'({",".join("?" * len(NOTE_SLOTS))})', NOTE_SLOTS):
            try:
                said = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                said = value
            for one in (said if isinstance(said, list) else [said]):
                if isinstance(one, str) and one.strip():
                    found.append((class_name, subject, one.strip()))
    return found


def repeated(conn) -> list[tuple[str, int, list[str]]]:
    """Notes written word for word more than once — nobody repeats what has a field."""
    counts, classes = Counter(), defaultdict(set)
    for class_name, _, text in notes(conn):
        counts[text] += 1
        classes[text].add(class_name)
    return [(text, count, sorted(classes[text]))
            for text, count in counts.most_common() if count > 1]


def shapes(conn, least: int = WORTH_LOOKING) -> list[dict]:
    """The same sentence with different things in it, counted, with the things collected.

    A shape is what is left of a note once the names the world knows are taken out of it. It is
    the evidence for a missing attribute, and the values that were substituted are the evidence
    for filling it in.
    """
    names = known_names(conn)
    pattern = re.compile("|".join(re.escape(name) for name in names) or r"(?!x)x")
    seen: dict[str, dict] = {}
    for class_name, subject, text in notes(conn):
        filled = pattern.findall(text)
        skeleton = pattern.sub("…", text).strip()
        skeleton = re.sub(r"\s+", " ", skeleton)
        if skeleton.count("…") == 0 or len(skeleton) < 6:
            continue
        entry = seen.setdefault(skeleton, {"shape": skeleton, "seen": 0, "classes": Counter(),
                                           "examples": [], "values": Counter(),
                                           "value_classes": Counter()})
        entry["seen"] += 1
        entry["classes"][class_name] += 1
        entry["values"].update(filled)
        # What kind of thing stood in the gap is the far end of a relation, and the world already
        # knows it — so the model is told rather than left to guess.
        entry["value_classes"].update(names[value] for value in filled if value in names)
        if len(entry["examples"]) < 3:
            entry["examples"].append(text)
    out = []
    for entry in seen.values():
        if entry["seen"] >= least:
            entry["classes"] = dict(entry["classes"])
            entry["value_classes"] = dict(entry["value_classes"])
            entry["values"] = [v for v, _ in entry["values"].most_common(8)]
            out.append(entry)
    return sorted(out, key=lambda e: -e["seen"])


def schema_from_specs(directory) -> dict:
    """The same picture of what can be said, read from the spec files a blank world wrote."""
    out = {}
    for path in sorted(Path(directory).glob("*.json")):
        spec = json.loads(path.read_text())
        relation = spec.get("relation")
        out[spec["name"]] = {
            "description": spec.get("description", ""),
            "attributes": {a["name"]: a.get("description", "") for a in spec.get("attributes", [])},
            "relation": {"kind": relation.get("kind"), "from": relation.get("from"),
                         "to": relation.get("to")} if relation else None,
        }
    return out


def schema(world) -> dict:
    """What the world can already say, as the model needs to see it to try fitting first."""
    out = {}
    for class_name, cls in world.classes.items():
        spec = cls._spec
        relation = spec.get("relation")
        out[class_name] = {
            "description": spec.get("description", ""),
            "attributes": {a["name"]: a.get("description", "") for a in spec.get("attributes", [])},
            "relation": {"kind": relation.get("kind"), "from": relation.get("from"),
                         "to": relation.get("to")} if relation else None,
        }
    return out


def evidence(conn, world=None, least: int = WORTH_LOOKING) -> dict:
    """Everything the restructuring pass reasons from, all of it counted rather than read."""
    counts = {}
    for table in _class_tables(conn):
        rows = _rows(conn, f'select count(distinct subject) from "{table}"')
        if rows and rows[0][0]:
            counts[table[len("facts_"):]] = rows[0][0]
    return {"things_per_class": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
            "prose_share": prose_share(conn),
            "repeated_notes": [{"text": t, "seen": n, "classes": c} for t, n, c in repeated(conn)[:20]],
            "shapes": shapes(conn, least)[:20],
            "schema": schema(world) if world is not None else None}


ASK = """\
You are the model inside a personal world model, looking at notes that piled up in free-text \
fields and deciding what the world's structure should do about them.

Here is the whole structure of this world — every class with its description and attributes, and
every relation type with the ends it may join:
{schema}

How many things of each kind there are:
{counts}

Here are shapes found in the notes — the same sentence with different things in it, with how \
often each was seen, under which classes the notes sit ("classes"), what stood in the gap
("values"), and what kind of thing those were ("value_classes") — a shape whose values are all of
one kind is a relation to that kind, one whose values are plain words is an attribute:
{shapes}

Notes repeated word for word:
{repeated}

Answer in JSON, and in this order of preference.

1. "fits": shapes that can already be said with something in the schema above. For each: the \
shape, the class and attribute or relation kind it belongs in, and nothing else. Prefer this \
always — a second way to say one thing is worse than prose.
2. "propose": only what genuinely has no home. For each: "kind" ("attribute" or "relation"), \
"name", "description" (one sentence, what it holds), "on" (the class, for an attribute) or \
"from"/"to" (lists of classes, for a relation), "changes" (true if a thing has one current value \
and a new one replaces it), and "shape" (which shape it came from). A shape found under several \
classes is one relation with several ends, not several attributes.
3. "leave": shapes that are genuinely prose — somebody's remark, not a fact with a field.

Answer with ONE JSON object holding the keys "fits", "propose" and "leave". Here is an answer
for a *different* world, to show the form — do not copy its contents:

{{"fits": [{{"shape": "works at …", "class": "Person", "slot": "employer"}}],
 "propose": [{{"kind": "attribute", "name": "allergic_to", "description": "what this person \
reacts badly to", "on": "Person", "changes": true, "shape": "allergic to …"}},
             {{"kind": "relation", "name": "supplies", "description": "who supplies a part to \
whom", "from": ["Organization"], "to": ["Organization", "Project"], "changes": true, \
"shape": "supplies … to …"}}],
 "leave": ["had a rough week"]}}

Now answer for the world above, with its own shapes in it."""


def read_notes(evidence: dict, model: str | None = None) -> dict:
    """The judgement: what fits, what is missing, what is simply a remark.

    Arithmetic gathered the evidence; naming an attribute and seeing that two wordings are one
    idea is meaning, and that is the world's own model — not the host's (this is the world
    working on its own structure) and not a heuristic.
    """
    from terraweaver import llm

    prompt = ASK.format(
        schema=json.dumps(evidence.get("schema") or {}, indent=1)[:20000],
        counts=json.dumps(evidence.get("things_per_class") or {})[:1500],
        shapes=json.dumps(evidence.get("shapes") or [], indent=1)[:9000],
        repeated=json.dumps(evidence.get("repeated_notes") or [], indent=1)[:1500])
    answer = llm.client().chat.completions.create(
        model=model or llm.DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        # A reasoning model thinks in its own field and then answers; too small a budget and it
        # spends the whole of it thinking, which comes back as an empty answer.
        max_tokens=16000)
    message = answer.choices[0].message
    said = message.content or getattr(message, "reasoning_content", "") or ""
    objects = _json_objects(said)
    for one in objects:
        if {"fits", "propose", "leave"} & set(one):
            return {"fits": one.get("fits", []), "propose": one.get("propose", []),
                    "leave": one.get("leave", [])}
    # A model that answered one object per shape instead of one object: gather them.
    fits = [o for o in objects if {"shape", "class"} <= set(o) and "kind" not in o or
            ("slot" in o or "kind" in o) and "name" not in o]
    propose = [o for o in objects if "name" in o and "description" in o]
    if fits or propose:
        return {"fits": fits, "propose": propose, "leave": []}
    raise ValueError(f"the model did not answer with JSON: {said[:300]}")


def _json_objects(said: str) -> list[dict]:
    """Every whole JSON object in what came back, in order.

    A model that thinks out loud puts its answer in the middle of a paragraph, and a greedy match
    swallows whatever follows it. So: find a brace, count braces, stop at the matching one.
    """
    found, at = [], 0
    for start, char in enumerate(said):
        if char != "{" or start < at:
            continue
        depth, inside = 0, False
        for end in range(start, len(said)):
            here = said[end]
            if here == '"' and said[end - 1] != "\\":
                inside = not inside
            elif not inside and here == "{":
                depth += 1
            elif not inside and here == "}":
                depth -= 1
                if depth == 0:
                    try:
                        found.append(json.loads(said[start:end + 1]))
                        at = end + 1
                    except json.JSONDecodeError:
                        pass
                    break
    return found


def main() -> int:
    """Look at a world and say what its structure should learn from its own notes."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="the world to look at")
    parser.add_argument("--least", type=int, default=WORTH_LOOKING,
                        help="how often a shape must occur to count as a pattern")
    parser.add_argument("--specs", default=None,
                        help="the directory of spec files (a blank world writes one per class)")
    parser.add_argument("--read", action="store_true",
                        help="ask the world's model what fits and what is missing")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    conn = sqlite3.connect(Path(args.db))
    found = evidence(conn, None, args.least)
    if args.specs:
        found["schema"] = schema_from_specs(args.specs)
    print(json.dumps({"prose_share": found["prose_share"],
                      "repeated_notes": found["repeated_notes"][:8],
                      "shapes": found["shapes"][:12]}, indent=2, ensure_ascii=False))
    if args.read:
        print(json.dumps(read_notes(found, args.model), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --- putting the answer into effect -------------------------------------------------------

def _merge_proposals(proposals: list[dict]) -> list[dict]:
    """One proposal per name: the same predicate seen under several shapes is still one thing."""
    merged: dict[str, dict] = {}
    for one in proposals:
        name = (one.get("name") or "").strip()
        if not name:
            continue
        have = merged.setdefault(name, {**one, "from": list(one.get("from") or []),
                                        "to": list(one.get("to") or []), "shapes": []})
        for side in ("from", "to"):
            for end in one.get(side) or []:
                if end not in have[side]:
                    have[side].append(end)
        if one.get("shape") and one["shape"] not in have["shapes"]:
            have["shapes"].append(one["shape"])
    return list(merged.values())


def _values_in(shape: str, text: str, names: dict[str, str]) -> list[str]:
    """What stood where the dots are, for this one note."""
    pattern = re.compile("|".join(re.escape(name) for name in names) or r"(?!x)x")
    filled = pattern.findall(text)
    skeleton = re.sub(r"\s+", " ", pattern.sub("…", text).strip())
    return filled if skeleton == shape else []


def apply(world, answer: dict, *, specs_dir=None, dry_run: bool = False) -> dict:
    """Define what was missing, and read the notes into it.

    Two kinds of write, and the difference matters. A value read out of a note is a **conclusion**
    with that note as its basis — the world's own weakest statement, retractable one at a time,
    and the note stays where it is. A link between two things is an ordinary relation, because a
    relation is not one slot on one subject; that is a gap worth closing later, and until then a
    wrong link is undone by ending it rather than by retracting it.

    Nothing is invented: if a note names something the world has never heard of, the link is
    skipped rather than the thing conjured. A restructuring pass is for what was already said.
    """
    from terraweaver import authoring

    conn = world.store.conn
    names = known_names(conn)
    by_name = {}
    for class_name in list(world.classes):
        try:
            for entity in world.all(class_name, limit=None):
                for slot in NAME_SLOTS:
                    said = getattr(entity, slot, None)
                    if isinstance(said, str) and said.strip():
                        by_name.setdefault(said.strip(), entity)
                        break
        except Exception:  # a relation class has no instances to name
            continue

    author = authoring.Authoring(world, specs_dir)
    done = {"defined": [], "concluded": 0, "linked": 0, "skipped": 0, "refused": []}

    for proposal in _merge_proposals(answer.get("propose", [])):
        if dry_run:
            done["defined"].append(proposal.get("name"))
            continue
        try:
            if proposal.get("kind") == "relation":
                author.define_relation(proposal["name"], proposal["description"],
                                       subject=(proposal.get("from") or ["Thing"])[0],
                                       object=(proposal.get("to") or ["Thing"])[0],
                                       cardinality="many-to-many",
                                       over_time=bool(proposal.get("changes", True)))
            else:
                author.attribute(proposal.get("on"), proposal["name"], proposal["description"],
                                 changes=bool(proposal.get("changes", True)))
            done["defined"].append(proposal.get("name"))
        except Exception as refused:
            done["refused"].append(f"{proposal.get('name')}: {refused}")

    targets = [(f.get("shape"), f.get("class"), f.get("slot")) for f in answer.get("fits", [])]
    targets += [(p.get("shape"), (p.get("from") or [p.get("on")])[0], p.get("name"))
                for p in answer.get("propose", []) if p.get("shape")]

    for shape, class_name, slot in targets:
        if not (shape and slot):
            continue
        for note_class, subject, text in notes(conn):
            if class_name and note_class != class_name:
                continue
            values = _values_in(shape, text, names)
            if not values:
                continue
            value = values[-1]
            if dry_run:
                done["concluded"] += 1
                continue
            other = by_name.get(value)
            kind = slot if slot in {c._spec.get("relation", {}).get("kind")
                                    for c in world.classes.values()
                                    if c._spec.get("relation")} else None
            try:
                if kind and other is not None:
                    world.relate(world.store.load(subject, world.classes), other, kind)
                    done["linked"] += 1
                elif kind:
                    done["skipped"] += 1
                else:
                    basis = [s.id for s in world.facts.about(subject, "descriptions")
                             if isinstance(s.value, (str, list))][:1]
                    world.facts.conclude(subject, slot, value, basis=basis, class_name=note_class)
                    done["concluded"] += 1
            except Exception:
                done["skipped"] += 1
    return done
