"""The whole mechanism on examples: look, find or describe, emit a class, register, use."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from relation_class import Relations, Relation, as_class

failures = []
def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if not ok else ""))
    if not ok: failures.append(name)


def take(book, described):
    """What a host does with one description: run the class, register it."""
    source = as_class(described)
    where = {"Relation": Relation}
    exec(source, where)
    made = next(v for k, v in where.items() if isinstance(v, type) and issubclass(v, Relation)
                and v is not Relation)
    return book.add(made), source


book = Relations()
check("a world with nothing in it offers nothing", "no relations yet" in book.offer())
check("and a look finds nothing", book.look("husband") is None)

made, source = take(book, {"subject_is": "husband", "object_is": "wife",
                           "one_object": True, "one_subject": True,
                           "relation_is": "A married couple, one at a time on each side."})
check("the description becomes a class that is a Relation", issubclass(made, Relation))
check("and it carries the six things", made.roles() == ("husband", "wife") and made.one_object)
check("and its word is read off the roles, not asked for", made.word() == "husband_of", made.word())

# --- the look, which is the point ---
again = book.look("husband")
check("saying the same thing again finds it", again is not None and again.relation is made)
check("and knows which end the word names", again.role_is == "subject", str(again))
far = book.look("wife")
check("the far role finds the same relation", far is not None and far.relation is made)
check("and knows it is the far end", far.role_is == "object", str(far))

# --- a second host, other words, same idea ---
near = book.look("spouse")
check("a word that shares nothing finds nothing, and that is honest", near is None)

take(book, {"subject_is": "chair", "object_is": "organization", "one_object": True,
            "relation_is": "The person who chairs a body."})
clash = book.look("chair")
check("a second relation is found by its own role", clash.relation.__name__ == "ChairOf")
overlap = book.look("chairperson")
check("and a word inside a word is offered rather than missed",
      overlap is not None and overlap.relation.__name__ == "ChairOf", str(overlap))

# --- what the host is shown before it invents anything ---
shown = book.offer()
check("the world shows what it holds, so the host need not remember",
      "husband ↔ wife" in shown and "chair ↔ organization" in shown, shown)
check("with how many hold at a moment, which is what decides a reading",
      "(one per husband, one per wife)" in shown, shown)

# --- symmetry is not declared anywhere ---
sib, _ = take(book, {"subject_is": "sibling", "object_is": "sibling",
                     "relation_is": "Two people with a parent in common."})
check("symmetry is the roles being one word", sib.symmetric() and not made.symmetric())

# --- transitivity survives the round trip through source ---
part, src = take(book, {"subject_is": "part", "object_is": "whole", "one_subject": True,
                        "transitive": True, "relation_is": "A part of a whole."})
check("transitivity is carried in the class body", part.transitive and "transitive = True" in src)

# --- the judge: the look offers, a closed question decides ---
def judge_says(what, sure=0.95):
    return lambda a, a_of, b, b_of, doc: {"choice": what, "probabilities": {what: sure}}

near = book.look("chairperson")
check("a candidate is offered for deciding, not applied",
      near is not None and "offered, not applied" in near.how, str(near))
said = book.settle(near, "chairperson", "organization", judge_says("same"))
check("called one idea, the host is sent to what is already there",
      "ChairOf" in said and "rather than a second word" in said, said[:80])
said = book.settle(near, "chairperson", "organization", judge_says("apart"))
check("called two ideas, nothing is said at all — a false alarm is worse than silence",
      said == "", said)
ends = book.look("whole")
said = book.settle(ends, "whole", "", judge_says("two_ends", 0.97))
check("called the two ends of one relation, that is what it says",
      "two ENDS" in said and "PartOf" in said, said[:80])

print("\n--- what a host is shown ---")
print(book.offer())
print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
              else "the mechanism holds on the examples"))
raise SystemExit(1 if failures else 0)
