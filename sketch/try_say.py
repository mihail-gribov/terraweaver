"""Both doors into the world, and what each costs. No reader: the typed door needs none."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from relation_class import Relation
from say import World

failures = []
def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   {detail}" if not ok else ""))
    if not ok: failures.append(name)


class HusbandWife(Relation):
    """A married couple, one at a time on each side."""
    subject_is = "a husband"; object_is = "a wife"
    one_object = True; one_subject = True


class PartWhole(Relation):
    """A part of a whole, and a part of a part is a part of the whole."""
    subject_is = "part"; object_is = "whole"
    one_subject = True; transitive = True


w = World()                       # no reader at all
w.book.add(HusbandWife); w.book.add(PartWhole); w._placed = []
boris, anna, olga = w.thing("Boris"), w.thing("Anna"), w.thing("Olga")

check("a role is readable before anything is written under it", boris.husband_of.is_ is None)
check("and the world can say what it is able to read",
      w.readable() == {"husband_of", "wife_of", "part_of", "whole_of"}, str(w.readable()))

boris.husband_of(anna)
check("a typed door writes without asking anybody", w.asked == 0)
check("and both ends read by their own role",
      boris.husband_of == anna and anna.wife_of == boris,
      f"{boris.husband_of} / {anna.wife_of}")

boris.husband_of = olga
check("assignment is the same door", boris.husband_of == olga)
check("and the earlier one is ended, not erased",
      len(w.placed()) == 2 and not w.placed()[0].holds())
check("so the one who was is nobody's wife now", anna.wife_of.is_ is None, str(anna.wife_of))
check("and the record still holds both tellings",
      [s.words for s in w.record] == ["Boris is Anna's husband", "Boris is Olga's husband"],
      str([s.words for s in w.record]))

boris.related(olga, HusbandWife)
check("passing the relation itself is the same door again",
      w.asked == 0 and len(w.record) == 3)

# --- the chain, through the same attribute ---
office, kreuzberg, berlin = w.thing("the office"), w.thing("Kreuzberg"), w.thing("Berlin")
office.part_of(kreuzberg); kreuzberg.part_of(berlin)
check("a transitive role answers the whole chain",
      list(office.part_of) == [kreuzberg, berlin], str(list(office.part_of)))
missing = None
try:
    boris.mayor_of
except AttributeError as said:
    missing = str(said)
check("and a word no role carries is refused, with what the world does have",
      missing is not None and "husband_of" in missing, str(missing)[:90])

print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
              else "both doors hold on the examples"))
raise SystemExit(1 if failures else 0)
