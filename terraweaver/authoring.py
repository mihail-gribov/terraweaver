"""Letting the host write the ontology, and keeping what it writes uniform.

The world has always had classes we chose. This is the other arrangement: the host defines them
as it goes — a name of its choosing, a description of what kind of thing it is, attributes
declared when it first needs them, relation types with the few properties that decide how they
behave. The world does not judge the modelling. It does four things, and they are the reason
this is an ontology rather than a heap:

**It insists on a description.** For a class, an attribute, a relation type. Not decoration: the
description is what the next lookup searches, and a name without one cannot be found by anybody
who did not invent it. A definition without a description is refused.

**It answers "is there already something for this?"** before a host invents a second word for a
thing it already has. Spelling first, through the world's one suggester (`did_you_mean`), then
meaning, through the index that is already there. This is the whole difference between a
vocabulary that converges and one that branches forever.

**It insists that a changing thing is a value.** An attribute declared as free text can hold many
tellings and supersede none of them — which is exactly how a world loses track of who the current
CEO is (`benchmarks/README.md`: seven of eight losses). So an attribute the host says can change
is a value slot, and asking for a text slot for it is refused with the reason.

**It insists that a class says what identifies one.** Every class we wrote by hand appears in
`matching`'s tables; a class defined at runtime appears in none of them, so without a declared
identifying attribute the world cannot tell two of them apart and quietly breeds duplicates.

Everything after definition is the world as it already is: `ensure`, `relate`, periods, history,
comments, questions, tags, meaning. A class defined this way is a class — not a special kind.
"""
import json
import re
from pathlib import Path

VALUE_TYPES = ("str", "int", "float", "bool", "datetime", "date", "email", "phone", "url",
               "domain", "dict")
TEXT_TYPES = ("text", "list[text]")
# How alike two type descriptions must read before the world hands back the one it has
# rather than making a second. Above this they are the same idea said twice.
# The natures a link can have. The set is closed and small; what is particular — husband and
# wife, director and company — is a type of its own that names one of these. Two of the five
# already exist in this world below the level of links: `same_as` is a slot in the record, a
# derivation is a conclusion with its basis. Naming them here classifies those mechanisms; it
# does not give them a second one.
#
# Named as the link reads, not as the literature writes it. A host picking a nature has to see
# what it is from the word: "composition" and "derivation" are terms of art, `part_of` and
# `derived_from` are the sentence. The paper's words are taken as well, so the correspondence to
# EvoOntology (arXiv:2609.15779) is not lost.
NATURES = {
    "related_to": "two things stand in some relation — most of a person's world (association)",
    "kind_of": "the subject is a narrower kind of the object (hierarchy)",
    "part_of": "the subject is part of the object (composition)",
    "same_as": "they are one and the same (equivalence; recorded as same_as, not as a link)",
    "derived_from": "the subject was worked out from the object (derivation; recorded as a "
                    "conclusion with its basis)",
}
# What the paper calls them, so either word is understood.
AS_WRITTEN = {"association": "related_to", "hierarchy": "kind_of", "composition": "part_of",
              "equivalence": "same_as", "derivation": "derived_from"}

SAME_IDEA = 0.82

CARDINALITY = {
    # what the host says          one subject per object?   one object per subject?
    "one-to-one": (True, True),
    "one-to-many": (True, False),    # one manager, many reports
    "many-to-one": (False, True),
    "many-to-many": (False, False),
}


class Refused(Exception):
    """A definition the world will not take, with the reason said out loud."""


def _clean(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", (name or "").strip()).strip("_")


def _type_name(kind: str) -> str:
    """`keeps_bees_for` -> `KeepsBeesFor`: a class named the way the world's classes are named.

    The word a host says the link with is one thing, and the class it lands in is another. They
    were the same string, so a world grown at runtime ended up with `employment` sitting beside
    `Membership` — and a host reading the catalogue has to guess which of the two spellings the
    next one will use. The kind keeps the host's word; only the class is renamed.
    """
    cleaned = _clean(kind)
    return "".join(part[:1].upper() + part[1:] for part in cleaned.split("_") if part) or cleaned


def _described(what: str, description: str) -> str:
    text = (description or "").strip()
    if len(text) < 12:
        raise Refused(f"{what} needs a description of what it is — a sentence, not a word; "
                      "it is what anybody looking for it later will search")
    return text


class Authoring:
    """The definition calls a host sees, and the directory the definitions live in."""

    def __init__(self, world, specs_dir: Path | None = None):
        self.world = world
        self.dir = Path(specs_dir) if specs_dir else None
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    # --- defining ---

    def define(self, name: str, description: str, identified_by: str,
               attributes: list[dict] | None = None, parent: str | None = None,
               what_to_say: str | None = None, brief: str | None = None,
               source: str = "agent"):
        """A new class: what it is called, what kind of thing it is, what tells two apart.

        `parent` is what it is a kind of, and it is how the world finds this class again:
        placing a thing walks down from the widest class asking which child it is, so a class
        with no parent is a leaf nobody ever descends to. `brief` is the clause it appears as
        in the list every host reads before it writes. `what_to_say` is the line put to a host
        that records one of these and says nothing about it — per class, because describing a
        person and describing a place are not the same request; left out, it comes from the
        parent, which is what having a parent means.
        """
        from terraweaver import ontology

        class_name = _clean(name)
        if not class_name:
            raise Refused("a class needs a name")
        if class_name in self.world.classes:
            raise Refused(f"{class_name} is already a class here — "
                          f"{self.world.classes[class_name]._spec.get('description', '')}")
        near = self.classes_like(f"{name}. {description}", limit=1)
        spec = {
            "name": class_name,
            "description": _described(f"the class {class_name}", description),
            "identified_by": _clean(identified_by),
            "attributes": [self._attribute_spec(**a) for a in (attributes or [])],
            "methods": [],
        }
        for key, value in (("parent", parent if parent in self.world.classes else None),
                           ("brief", brief), ("what_to_say", what_to_say)):
            if value and str(value).strip():
                spec[key] = str(value).strip()
        # A class is described the way anything in this world is described: in prose, by
        # somebody, with room for somebody else to say it differently later. `brief` is the one
        # canonical line — what the class is called in the list every host reads — and the
        # account in sentences is a prose-fact among however many accumulate.
        spec["descriptions"] = [{"text": spec["description"], "source": source}]
        if not spec["identified_by"]:
            raise Refused("say what identifies one of these — the attribute that tells two "
                          "of them apart (a name, a title, a code)")
        if not any(a["name"] == spec["identified_by"] for a in spec["attributes"]):
            spec["attributes"].insert(0, self._attribute_spec(
                spec["identified_by"], f"what this {class_name} is called", type="str",
                required=True))
        built = ontology.define_class(self.world.classes, spec)
        self._register(spec)
        self._register_identity(spec)
        self._save(spec)
        if near:
            print(f"[note] {class_name} reads like {near[0][0]} ({near[0][1]}) — "
                  "merge them if they are the same idea")
        return built

    def describe_class(self, cls, text: str, source: str = "agent") -> list:
        """Another account of what this class is — prose, by somebody, alongside the others.

        One canonical sentence per class was a shape the world does not use anywhere else, and
        it lost what it replaced: the first account of a class is written when one thing of that
        kind has been seen, and the next reader's is written when there are twenty. Both are
        worth keeping and neither overrules the other, which is what `descriptions` means
        everywhere else here.

        `source` is the same word every statement in this world carries (`ontology.stating`):
        "agent" for what arrived through the assistant, "world" for the world's own reading,
        which stands lowest and comes off in one move. "given" is what a class opened with.
        """
        name = cls if isinstance(cls, str) else getattr(cls, "__name__", str(cls))
        spec = self.world.classes[name]._spec
        text = _described(f"the class {name}", text)
        kept = spec.setdefault("descriptions", [{"text": spec.get("description", ""),
                                                 "source": "given"}])
        if not any(d.get("text") == text for d in kept):
            kept.append({"text": text, "source": source})
        self._register(spec)
        self._save(spec)
        return kept

    def attribute(self, cls, name: str, description: str, type: str = "str",
                  changes: bool = True, required: bool = False):
        """Declare an attribute on a class defined here. `changes=True` means it supersedes.

        `required=True` says the class is not itself without it. The spec builder took this all
        along and this call did not pass it, so a host building its own vocabulary could not
        say that a thing must have something — the word was accepted and quietly dropped.

        Required here means the world says so when it is missing, not that it refuses: only the
        attribute that names a thing is worth losing a fact over, because an entity nothing can
        identify breeds duplicates that no later telling repairs. For the rest the gap is left
        open and named, since a host that must fill a field to get past a check fills it with
        its own knowledge, and the record cannot tell that from what the person said.
        """
        from terraweaver import ontology

        spec = self._spec_of(cls)
        attr = self._attribute_spec(name, description, type=type, changes=changes,
                                    required=required)
        standing = next((a for a in spec["attributes"] if a["name"] == attr["name"]), None)
        if standing is not None and standing.get("provisional"):
            # Saying what a word taken on the fly means is not redeclaring it — it is the
            # answer the world asked for. Whatever was written under the word stays where it is.
            spec["attributes"][spec["attributes"].index(standing)] = attr
            ontology.define_class(self.world.classes, spec)
            self._register(spec)
            self._save(spec)
            return attr
        if standing is not None:
            # Saying only "already declared" leaves a host that wanted a different type with
            # nowhere to go: it cannot redeclare, and nothing here removes or renames. So the
            # refusal says what the word already means in this world, which is the thing it
            # needs in order to either write the value in that form or pick another word.
            raise Refused(
                f"{spec['name']}.{attr['name']} is already declared, as "
                f"{standing.get('type', 'str')}: {standing.get('description', '')[:90]}\n"
                f"Write the value in that form, or if this is genuinely a different thing, give "
                f"it a name of its own — an attribute cannot be redeclared, removed or renamed, "
                f"because everything already recorded under the word was recorded meaning it."
            )
        spec["attributes"].append(attr)
        ontology.define_class(self.world.classes, spec)  # rebuild the class with the addition
        self._register(spec)
        self._save(spec)
        return attr

    # What a value looks like, when the word for it arrives before anybody says what it is.
    # A guess, and marked as one: the host confirms or corrects it before the task closes.
    def guess_type(self, value) -> str:
        from datetime import date as _date, datetime as _datetime

        from terraweaver.ontology import Entity

        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, _datetime) or isinstance(value, _date):
            return "datetime"
        if isinstance(value, Entity):
            return "ref:any"
        if isinstance(value, dict):
            return "dict"
        if isinstance(value, (list, tuple)):
            inner = next((v for v in value if v is not None), None)
            return f"list[{self.guess_type(inner) if inner is not None else 'str'}]"
        return "str"

    def provisional(self, cls, name: str, value) -> dict:
        """Take a word the host wrote before anybody said what it means.

        Refusing this is right about the ontology and wrong about the cost. A raise stops the
        block, and everything after it in that block is not recorded — one un-dated link took
        twenty-eight lines with it, and a host that keeps hitting a wall writes prose instead,
        which is where a fact stops being one. So the word is taken, the type is guessed from
        the value, and the two things nobody can read off a value — what it means and whether
        it supersedes — are asked for at the close, where the host is free to answer.
        """
        from terraweaver import ontology

        spec = self._spec_of(cls)
        attr_name = _clean(name)
        attr = {"name": attr_name, "type": self.guess_type(value), "required": False,
                "description": "", "changes": True, "provisional": True}
        spec["attributes"].append(attr)
        ontology.define_class(self.world.classes, spec)
        self._register(spec)
        self._save(spec)
        return attr

    def grown_names(self) -> set:
        """The classes this world wrote for itself, as the files beside it record them.

        Read from the directory rather than kept in memory, so a world reopened tomorrow still
        knows which of its types are its own. What came with the world is not the host's to fix.
        """
        if not self.dir or not self.dir.exists():
            return set()
        out = set()
        for path in self.dir.glob("*.json"):
            try:
                out.add(json.loads(path.read_text())["name"])
            except Exception:  # noqa: BLE001 - an unreadable file is not a class we can name
                continue
        return out

    def unsaid(self) -> list[tuple]:
        """Every word taken this way that nobody has said the meaning of yet."""
        out = []
        for name, cls in sorted(self.world.classes.items()):
            for attr in cls._spec.get("attributes", []):
                if attr.get("provisional"):
                    out.append((name, attr["name"], attr.get("type", "str")))
        return out

    def define_relation(self, name: str, description: str, subject=None, object=None,
                        nature: str | None = None,
                        cardinality: str | None = None, over_time: bool | None = None,
                        attributes: list[dict] | None = None, reads: str | None = None,
                        subject_is: str | None = None, object_is: str | None = None):
        """A new relation type: the sides, how many may stand on each, and whether one at a time.

        `subject_is` / `object_is` name what each end *is* in this link — "driver" and "vehicle",
        "owner" and "owned". That is what a class cannot say: a car is not barred from driving
        because it is a Car, but because nothing that drives is a vehicle. Every type in the core
        names its ends this way, and it is what makes a link written from the wrong end visible
        as a wrong fact rather than a type mismatch.

        A side may be a class, several classes, or left open. Open is the honest answer when the
        first example is all anybody has seen: a side named after it refuses the second one, and
        a host told "this type does not take these ends" defines a second type with the class
        names in it rather than concluding its own guess was narrow. Two of the thirty-one types
        a host built in one run were duplicates made that way. Name a side when the world will do
        something with it — the one thing a named side buys is noticing a link written backwards,
        and for that the two sides only have to differ.

        `over_time` has no default on purpose. It is what makes "who is it *now*" answerable — a
        new holder ends the previous one's period instead of standing beside it — and a run where
        it was quietly left off answered every changed citizenship with the first one it was told
        (`benchmarks/README.md`, experiment zero). Cardinality never decides this; saying so does.
        """
        from terraweaver import ontology

        kind = _clean(name).lower()
        if not kind:
            raise Refused("a relation type needs a name")
        # Everything missing, in one refusal, with the call written out. Refusing one argument
        # at a time costs a run each: a recorder that gave none of the three spent forty-one
        # runs collecting them, then reported ten facts recorded into a world that held eight
        # bare names and nothing else.
        if nature in ("part_of", "kind_of") and cardinality is None:
            cardinality = "many-to-one"   # a part has one whole, a kind has what it is a kind of
        wants = []
        if over_time is None:
            wants.append("over_time=False      # True when one holds at a time and a new one "
                         "ends the last (an employer, a spouse)")
        if nature not in NATURES:
            wants.append(f'nature="related_to"  # one of {", ".join(NATURES)}')
        if cardinality is None:
            wants.append(f'cardinality="many-to-one"  # one of {", ".join(CARDINALITY)}')
        if wants:
            written = ",\n        ".join(w.split("  #")[0].rstrip() for w in wants)
            raise Refused(
                f"{kind} needs {'this' if len(wants) == 1 else 'these'} said, and I will not "
                f"guess {'it' if len(wants) == 1 else 'them'}:\n    "
                + "\n    ".join(wants)
                + f"\n\nwrite:\n    world.define_relation(\"{kind}\", \"{description}\",\n"
                  f"        {written})"
            )
        if cardinality not in CARDINALITY:
            raise Refused(f"cardinality is one of {', '.join(CARDINALITY)}")
        one_subject, one_object = CARDINALITY[cardinality]
        # Two axes, named apart so they cannot be read as one. Cardinality says how many there
        # may be across all of time; `over_time` says whether one of them holds *now* and a new
        # one ends the last. They were once multiplied together in a line nobody could read, and
        # the default cardinality silently switched supersession off for most types defined here.
        holds_now_only = "at_any_time" if over_time else True
        one_object_ever = over_time or one_object
        one_subject_ever = over_time or one_subject
        already = self._relation_like(f"{kind.replace('_', ' ')}. {description}", word=kind)
        if already:
            # Said, not done. The world used to hand back the type it thought was meant, and
            # the reading was a guess dressed as a fact: "director of" came back as
            # ChairpersonOf and Tony Hall went into the world as the BBC's chairperson, with
            # nothing but a printed note to say a word had been swapped. Whether two words are
            # one idea is the agent's to judge — it has the sentence the user said and the
            # world has a number. The world says what it noticed and makes what was asked for.
            name_of, description_of, _ = already[0]
            from terraweaver import initiative, ontology as _ontology
            if initiative.MERGES_MEANING:
                print(f"[note] {kind} reads as {name_of} ({description_of}) — that type, not a "
                      f"second one. If they differ, say how and define it under a name that "
                      f"says so.")
                return self.world.classes[name_of]
            _ontology.note_hint(
                f"'{kind.replace('_', ' ')}' reads a lot like {name_of} ({description_of}). I "
                f"have made {kind} as you asked — if they are one idea, say so and move the "
                f"links over: world.take_in({name_of}, \"{kind}\"). If they are two, nothing "
                f"to do.")
        spec = {
            "name": _type_name(name),
            "description": _described(f"the relation {kind}", description),
            "relation": {
                "kind": kind,
                # The nature is the statement; what follows from it is read through
                # `relations.rule`, not copied here where the two could drift apart.
                "nature": nature,
                "from": self._sides(subject),
                "to": self._sides(object),
                # `over_time` and cardinality are different axes and must not cancel each
                # other. Many-to-many says "many over all time"; over_time says "one of them
                # holds now, and a new one ends the last". Reading cardinality first turned
                # supersession off for every type declared with the default many-to-many —
                # which was most of them — and the world then answered "which now" with the
                # first thing it had ever been told. Eight of ten wrong answers in one run.
                "functional": holds_now_only if one_object_ever else False,
                "inverse_functional": holds_now_only if one_subject_ever else False,
                "reverse": f"{kind}_of",
                "labels": [],
                "example": self._example(kind, subject, object),
                "reads": reads or self._reads(kind, subject, object, subject_is, object_is),
                "roles": ([{"name": _clean(subject_is).lower(),
                            "inverse": _clean(object_is).lower() if object_is else None}]
                          if subject_is else []),
            },
            "attributes": [self._attribute_spec(**a) for a in (attributes or [])],
            "methods": [],
        }
        built = ontology.define_class(self.world.classes, spec)
        self._register(spec)
        self._save(spec)
        # Looked at the moment it is made, while the host is still holding the pen. A type is
        # defined once and every link written under it inherits whatever was wrong with it —
        # a word that does not say which end starts, a second word for an idea already here.
        # Found a hundred facts later, the links are written and somebody has to go back over
        # them; found here, it is one more argument on the call being made.
        try:
            from terraweaver import inspector

            for said in inspector.on_new_type(self.world, name):
                ontology.note_hint(said)
        except Exception:  # noqa: BLE001 - looking at a type is never what stops one being made
            pass
        if not subject_is:
            # Asked for, never demanded. A type without named ends works perfectly well — it is
            # the *checking* of it that cannot be done: told what each end is, an outside reader
            # tells a link written backwards from one written right and abstains where it cannot
            # (12 of 14 against 7 of 12, and every miss an abstention rather than a wrong call).
            # Told only the type's name and description, it guesses, and guesses confidently.
            # None of the twenty-six types one recorder built named its ends, and a backwards
            # link was the commonest wrong fact left in that world.
            ontology.note_hint(
                f"{name} has no names for its ends, so nothing can later tell a link of this "
                f"type written backwards from one written right. Say what each end is — it is "
                f"one more argument, and it is what makes the type checkable:\n"
                f"    world.define_relation(\"{kind}\", \"…\", …, "
                f"subject_is=\"<what the first end is>\", "
                f"object_is=\"<what the second end is>\")\n"
                f"For {kind}: the subject is the end the sentence starts from."
            )
        return built

    def _relation_like(self, text: str, limit: int = 1,
                       word: str = "") -> list[tuple[str, str, float]]:
        """Relation types that read like this, closest first, with how close.

        Two readings have to agree: the whole text, and the word on its own. The second is
        there because a type the world invents gets a description built from a template — "one
        person director of one thing" — and the template is the same for every type, so the
        part that differs is a few characters in a sentence that is otherwise identical. It
        inflates everything: "director of" against "chairperson of" scores 0.708 as words and
        0.853 inside the frame, which is over the bar. Tony Hall went into the world as the
        BBC's chairperson because of those two numbers, and nothing said so.

        The word alone separates cleanly — real synonyms 0.83 to 0.95 ("born in"/"birthplace"
        0.840, "married to"/"spouse of" 0.834), different roles 0.66 to 0.77. Missing a synonym
        costs a second type, which `wanted()` and `take_in` exist to mend. A wrong merge
        changes what a fact says, and nothing mends that.
        """
        known, words = {}, {}
        for name, cls in self.world.classes.items():
            rel = cls._spec.get("relation")
            if rel and not rel.get("free"):
                known[name] = f"{rel['kind'].replace('_', ' ')}. {cls._spec.get('description', '')}"
                words[name] = rel["kind"].replace("_", " ")
        if not known:
            return []
        names = list(known)
        said = (word or text.split(".", 1)[0]).replace("_", " ").strip()
        vectors = self.world.meanings.model.embed(
            [text] + [known[n] for n in names] + [said] + [words[n] for n in names])
        half = 1 + len(names)
        near = lambda a, b: sum(x * y for x, y in zip(a, b))
        scored = sorted(((n, self.world.classes[n]._spec.get("description", ""),
                          near(vectors[0], vectors[1 + i]),
                          near(vectors[half], vectors[half + 1 + i]))
                         for i, n in enumerate(names)), key=lambda one: -one[2])
        # Only where it is plain, and only where both readings say so.
        return [(n, d, full) for n, d, full, alone in scored[:limit]
                if full >= SAME_IDEA and alone >= SAME_IDEA]

    # --- looking before inventing ---

    def classes_like(self, text: str, limit: int = 5) -> list[tuple[str, str]]:
        """(class name, its description) for what already exists and reads like this.

        The base is left out of the answer. A Thing is by construction like everything — saying
        so of every class anyone defines is not a warning, it is noise, and noise in a warning
        is how warnings stop being read.
        """
        from terraweaver import ontology

        return self._like(text, {name: cls._spec.get("description", "")
                                 for name, cls in self.world.classes.items()
                                 if name not in ontology.BASE_CLASSES}, limit)

    def attributes_like(self, text: str, limit: int = 8) -> list[tuple[str, str]]:
        """(Class.attribute, its description) for attributes that already mean roughly this."""
        known = {}
        for name, cls in self.world.classes.items():
            for attr in cls._spec.get("attributes", []):
                known[f"{name}.{attr['name']}"] = attr.get("description", "")
        return self._like(text, known, limit)

    def anything_like(self, name: str, limit: int = 5) -> list:
        """Is there already a thing called this, of any kind at all?

        Identity in this world is declared per class, so nothing stops the same word becoming
        four different things — in experiment zero "rugby" ended up a Place, an Organization, a
        Work and a SportsTeam at once, and no answer about it could be right. This is the look
        across classes that the world does not do by itself: ask before creating a fourth one.
        """
        wanted = (name or "").strip().lower()
        if not wanted:
            return []
        found = []
        for class_name, cls in self.world.classes.items():
            if cls._spec.get("relation"):
                continue
            for entity in self.world.all(class_name, limit=None):
                for slot in ("name", "full_name", "title", "label"):
                    said = getattr(entity, slot, None)
                    if isinstance(said, str) and wanted in said.lower():
                        found.append((class_name, entity))
                        break
            if len(found) >= limit:
                break
        return found[:limit]

    def _like(self, text: str, known: dict[str, str], limit: int) -> list[tuple[str, str]]:
        """Spelling first, through the world's one suggester; then meaning, over descriptions."""
        from terraweaver.ontology import did_you_mean

        wanted = (text or "").strip()
        if not wanted or not known:
            return []
        found: list[tuple[str, str]] = []
        guess = did_you_mean(wanted.split(".")[-1], list(known))
        if guess:
            found.append((guess, known[guess]))
        try:
            model = self.world.meanings.model
            names = [n for n in known if n != (guess or "")]
            vectors = model.embed([f"{n}: {known[n]}" for n in names] + [wanted])
            asked = vectors[-1]
            scored = sorted(((sum(a * b for a, b in zip(asked, vector)), name)
                             for vector, name in zip(vectors, names)), reverse=True)
            for score, name in scored[:limit]:
                if score >= 0.5 and all(name != had for had, _ in found):
                    found.append((name, known[name]))
        except Exception:  # no model, no meaning: spelling still answered
            pass
        return found[:limit]

    # --- the plumbing ---

    def _attribute_spec(self, name: str, description: str, type: str = "str",
                        changes: bool = True, required: bool = False) -> dict:
        attr_name = _clean(name)
        if not attr_name:
            raise Refused("an attribute needs a name")
        described = _described(f"the attribute {attr_name}", description)
        if changes and type in TEXT_TYPES:
            raise Refused(
                f"{attr_name} is meant to change, so it cannot be free text: several tellings "
                "would sit side by side and none would supersede the others. Give it a value "
                f"type ({', '.join(VALUE_TYPES[:6])}, …), or say changes=False if it is prose.")
        return {"name": attr_name, "type": type, "required": required,
                "description": described, "changes": changes}

    def _register(self, spec: dict) -> None:
        """Put the grown spec everywhere a spec is read from, not only on the class.

        `world.specs` is the dictionary the world opened with, and two readers prefer it to the
        class: `find`/`get` checks an attribute name against it, and the assembler asks it
        whether a slot holds one value or many. Left behind, an attribute a host had just
        declared was writable and not findable in the same run — `Person.find(salary=...)` came
        back "no attribute 'salary'" while `person.salary` held it — and a grown `list[...]`
        slot was read back on a rebuild as a single value, the last one said.
        """
        specs = getattr(self.world, "specs", None)
        if isinstance(specs, dict):
            specs[spec["name"]] = spec

    def _register_identity(self, spec: dict) -> None:
        from terraweaver import matching

        register = getattr(matching, "register_identity", None)
        if register is None:  # the hook is not in yet; say so rather than breed duplicates
            raise Refused("this world cannot yet tell two of a host-defined class apart "
                          "(matching.register_identity is missing)")
        register(spec["name"], name_keys=[spec["identified_by"]])

    def _name_of(self, cls) -> str:
        return cls if isinstance(cls, str) else getattr(cls, "__name__", str(cls))

    def _reads(self, kind: str, subject, object, subject_is=None, object_is=None) -> str:
        """Which end is the subject, in a sentence.

        Every type in the core says this — "the owner is the subject", "the member is the
        subject" — and it is what stops a link being written from the wrong end. Types the host
        defines used to get "a <kind> b", which says nothing, and links came in backwards. Said
        with the classes in it, the sentence at least names the ends; said by the host in its own
        words (`reads=`), it names the roles, which is better.
        """
        if subject_is:
            said = f"the {subject_is} is the subject"
            return (f"{said}: {subject_is} {kind.replace('_', ' ')} "
                    f"{object_is or 'the other end'}") if object_is else said
        starts = " or ".join(self._sides(subject))
        ends = " or ".join(self._sides(object))
        if starts == "any" and ends == "any":
            return (f"a {kind.replace('_', ' ')} b — whichever end you start from is the "
                    f"subject, so start from the one the sentence starts from")
        return (f"the {starts} is the subject: "
                f"{starts} {kind.replace('_', ' ')} {ends}")

    def _example(self, kind: str, subject, object) -> str:
        a, b = self._sides(subject)[0], self._sides(object)[0]
        a = "a" if a == "any" else a.lower()
        b = "b" if b == "any" else b.lower()
        return f"{a}.relate({b}, {kind!r})"

    def _sides(self, given) -> list[str]:
        """One side of a relation: a class, several, or open."""
        if given is None:
            return ["any"]
        if isinstance(given, (list, tuple, set)):
            named = [self._name_of(one) for one in given if one is not None]
            return named or ["any"]
        return [self._name_of(given)]

    def _spec_of(self, cls) -> dict:
        name = self._name_of(cls)
        if name not in self.world.classes:
            raise Refused(f"{name} is not a class here")
        return json.loads(json.dumps(self.world.classes[name]._spec))  # a copy to add to

    def _save(self, spec: dict) -> None:
        if self.dir:
            (self.dir / f"{spec['name']}.json").write_text(json.dumps(spec, indent=2))


def install(world, specs_dir=None, one_door: bool = False) -> Authoring:
    """Put the definition calls where a host can reach them, and nowhere else.

    The core world does not know these exist; a mode adds them. `world.extras` is the one door
    (`runtime.WorldView` looks there for a name it does not have of its own), so a world that was
    not started this way is exactly the world it always was.
    """
    authoring = Authoring(world, specs_dir)
    world.grown_dir = Path(specs_dir) if specs_dir else None   # where a type made on the fly goes
    extras = getattr(world, "extras", None)
    if extras is None:
        raise Refused("this world has no `extras` — the facade cannot reach the definition calls")
    extras.update({
        "define": authoring.define,
        "attribute": authoring.attribute,
        "define_relation": authoring.define_relation,
        "classes_like": authoring.classes_like,
        "attributes_like": authoring.attributes_like,
        "anything_like": authoring.anything_like,
    })
    if one_door:
        # An experiment, and the reason it has to be one: offered both doors, a host takes the
        # one it already knows — measured, ten facts out of ten through the type-first door and
        # not one call to the other, which appeared in the dialogue only where the world itself
        # had printed it. Two doors measure the habit, not the mechanism. With the type-first
        # one closed, what is left is `world.link(a, b, "...")`, which defines the types itself
        # from what was said. Nothing is lost: the calls are still here and still used, by the
        # sentence door among others — they are simply not on the host's surface.
        for shut in ("define_relation",):
            extras.pop(shut, None)
    return authoring
