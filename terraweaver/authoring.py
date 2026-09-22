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
               attributes: list[dict] | None = None):
        """A new class: what it is called, what kind of thing it is, what tells two apart."""
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
        if not spec["identified_by"]:
            raise Refused("say what identifies one of these — the attribute that tells two "
                          "of them apart (a name, a title, a code)")
        if not any(a["name"] == spec["identified_by"] for a in spec["attributes"]):
            spec["attributes"].insert(0, self._attribute_spec(
                spec["identified_by"], f"what this {class_name} is called", type="str",
                required=True))
        built = ontology.define_class(self.world.classes, spec)
        self._register_identity(spec)
        self._save(spec)
        if near:
            print(f"[note] {class_name} reads like {near[0][0]} ({near[0][1]}) — "
                  "merge them if they are the same idea")
        return built

    def attribute(self, cls, name: str, description: str, type: str = "str",
                  changes: bool = True):
        """Declare an attribute on a class defined here. `changes=True` means it supersedes."""
        from terraweaver import ontology

        spec = self._spec_of(cls)
        attr = self._attribute_spec(name, description, type=type, changes=changes)
        if any(a["name"] == attr["name"] for a in spec["attributes"]):
            raise Refused(f"{spec['name']}.{attr['name']} is already declared")
        spec["attributes"].append(attr)
        ontology.define_class(self.world.classes, spec)  # rebuild the class with the addition
        self._save(spec)
        return attr

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
        if over_time is None:
            raise Refused(
                f"say whether {kind} holds one at a time: over_time=True when a thing has one "
                "current holder and a new one ends the last (an employer, a spouse, a "
                "citizenship somebody changes), over_time=False when they simply accumulate "
                "(everything a person has ever written). Without it, asking later gives you the "
                "first answer you were ever told.")
        nature = AS_WRITTEN.get(str(nature or "").strip().lower(), nature)
        if nature not in NATURES:
            raise Refused(
                "say what kind of link this is — its nature, one of: "
                + "; ".join(f"{k} ({v})" for k, v in NATURES.items())
                + ". Everything particular — husband and wife, director and company — is a "
                  "type of its own with a nature behind it; the nature is what the world knows "
                  "how to behave about, the name is what you and the user call it.")
        if nature in ("part_of", "kind_of") and cardinality is None:
            cardinality = "many-to-one"      # a part has one whole, a kind has what it is a kind of
        if cardinality is None:
            raise Refused(
                f"say how many of these there may be: cardinality is one of "
                f"{', '.join(CARDINALITY)}. It used to default to many-to-many, and a default "
                f"nobody chose is a guess the world then treats as an answer — that one switched "
                f"supersession off for most types defined here and had the world answering "
                f"'which one now' with the first thing it was ever told.")
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
        already = self._relation_like(f"{kind.replace('_', ' ')}. {description}")
        if already:
            # The world looks, because the host does not. Forty-six relation types were defined
            # in one run and `classes_like` was never called once — an instruction to look before
            # inventing is an instruction, and instructions are what this world stopped relying
            # on. Where the match is plain the existing type is handed back and the reading is
            # announced, the same bargain `take_as` makes for a misspelt word.
            name_of, description_of, _ = already[0]
            print(f"[note] {kind} reads as {name_of} ({description_of}) — that type, not a "
                  f"second one. If they differ, say how and define it under a name that says so.")
            return self.world.classes[name_of]
        spec = {
            "name": _clean(name),
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
        self._save(spec)
        return built

    def _relation_like(self, text: str, limit: int = 1) -> list[tuple[str, str, float]]:
        """Relation types that read like this, closest first, with how close."""
        known = {}
        for name, cls in self.world.classes.items():
            rel = cls._spec.get("relation")
            if rel and not rel.get("free"):
                known[name] = f"{rel['kind'].replace('_', ' ')}. {cls._spec.get('description', '')}"
        if not known:
            return []
        names = list(known)
        vectors = self.world.meanings.model.embed([text] + [known[n] for n in names])
        scored = sorted(((n, self.world.classes[n]._spec.get("description", ""),
                          sum(a * b for a, b in zip(vectors[0], v)))
                         for n, v in zip(names, vectors[1:])), key=lambda one: -one[2])
        # Only where it is plain. A looser bar names an unrelated type as a near miss — "married
        # to" against "associated with sport" — and a warning that cries wolf stops being read,
        # which costs more than the duplicate it was meant to prevent.
        return [one for one in scored[:limit] if one[2] >= SAME_IDEA]

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


def install(world, specs_dir=None) -> Authoring:
    """Put the definition calls where a host can reach them, and nowhere else.

    The core world does not know these exist; a mode adds them. `world.extras` is the one door
    (`runtime.WorldView` looks there for a name it does not have of its own), so a world that was
    not started this way is exactly the world it always was.
    """
    authoring = Authoring(world, specs_dir)
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
    return authoring
