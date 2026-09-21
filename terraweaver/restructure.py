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
                                           "examples": [], "values": Counter()})
        entry["seen"] += 1
        entry["classes"][class_name] += 1
        entry["values"].update(filled)
        if len(entry["examples"]) < 3:
            entry["examples"].append(text)
    out = []
    for entry in seen.values():
        if entry["seen"] >= least:
            entry["classes"] = dict(entry["classes"])
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
    return {"prose_share": prose_share(conn),
            "repeated_notes": [{"text": t, "seen": n, "classes": c} for t, n, c in repeated(conn)[:20]],
            "shapes": shapes(conn, least)[:20],
            "schema": schema(world) if world is not None else None}


ASK = """\
You are the model inside a personal world model, looking at notes that piled up in free-text \
fields and deciding what the world's structure should do about them.

Here is what the world can already say:
{schema}

Here are shapes found in the notes — the same sentence with different things in it, with how \
often each was seen, under which classes, and which values were substituted:
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
        schema=json.dumps(evidence.get("schema") or {}, indent=1)[:6000],
        shapes=json.dumps(evidence.get("shapes") or [], indent=1)[:6000],
        repeated=json.dumps(evidence.get("repeated_notes") or [], indent=1)[:2000])
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
