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

    def define_relation(self, name: str, description: str, subject, object,
                        cardinality: str = "many-to-many", over_time: bool = True,
                        attributes: list[dict] | None = None):
        """A new relation type: the sides, how many may stand on each, and whether one at a time.

        `over_time=True` is what makes "who is it *now*" answerable: a new holder ends the old
        one's period instead of standing beside it. Cardinality alone never decides that.
        """
        from terraweaver import ontology

        kind = _clean(name).lower()
        if not kind:
            raise Refused("a relation type needs a name")
        if cardinality not in CARDINALITY:
            raise Refused(f"cardinality is one of {', '.join(CARDINALITY)}")
        one_subject, one_object = CARDINALITY[cardinality]
        when = "at_any_time" if over_time else True
        spec = {
            "name": _clean(name),
            "description": _described(f"the relation {kind}", description),
            "relation": {
                "kind": kind,
                "from": [self._name_of(subject)],
                "to": [self._name_of(object)],
                "functional": when if one_object else False,
                "inverse_functional": when if one_subject else False,
                "reverse": f"{kind}_of",
                "labels": [],
                "example": f"a.relate(b, {kind!r})",
                "reads": f"a {kind} b",
            },
            "attributes": [self._attribute_spec(**a) for a in (attributes or [])],
            "methods": [],
        }
        built = ontology.define_class(self.world.classes, spec)
        self._save(spec)
        return built

    # --- looking before inventing ---

    def classes_like(self, text: str, limit: int = 5) -> list[tuple[str, str]]:
        """(class name, its description) for what already exists and reads like this."""
        return self._like(text, {name: cls._spec.get("description", "")
                                 for name, cls in self.world.classes.items()}, limit)

    def attributes_like(self, text: str, limit: int = 8) -> list[tuple[str, str]]:
        """(Class.attribute, its description) for attributes that already mean roughly this."""
        known = {}
        for name, cls in self.world.classes.items():
            for attr in cls._spec.get("attributes", []):
                known[f"{name}.{attr['name']}"] = attr.get("description", "")
        return self._like(text, known, limit)

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
    })
    return authoring
