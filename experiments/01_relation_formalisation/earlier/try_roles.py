"""Every claim the long argument arrived at, tried on examples. No world, no models."""
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent))
from roles import World, Thing, Pair

failures = []
def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"   {detail}" if not condition else ""))
    if not condition: failures.append(name)

d = lambda y: datetime(y, 1, 1)

# --- направление не бывает неверным: его несут роли, а не порядок ---
w = World(); w.pair('capital', 'country', one_object=True, one_subject=True)
gb, london = Thing('Great Britain'), Thing('London')
said = w.relate(gb, 'country', london, 'capital').reads()
check("a link said from the far end lands the right way round",
      said == "London is Great Britain's capital", said)
try:
    w.relate(gb, 'capital', london, 'country')
    wrong_is_possible = True
except Exception:
    wrong_is_possible = False
check("and calling the country a capital is a thing you must do on purpose",
      wrong_is_possible, "it was refused, which is even stronger")

# --- симметрия это одно слово с обеих сторон, без флага ---
check("symmetry is the roles being the same word",
      Pair('sibling', 'sibling').symmetric and not Pair('mother', 'child').symmetric)

# --- кардинальность 1: периоды не пересекаются ---
w = World(); w.pair('employee', 'employer', one_object=True)
anna, a_corp, b_corp = Thing('Anna'), Thing('A Corp'), Thing('B Corp')
w.relate(anna, 'employee', a_corp, 'employer', starts=d(2018))
w.relate(anna, 'employee', b_corp, 'employer', starts=d(2022))
first = w.links[0]
check("a second one ends the first where it begins",
      first.until == d(2022) and first.until_is == "exact", str(first.until))
check("and both are true, each in its turn",
      first.holds_at(d(2019)) is True and first.holds_at(d(2023)) is False)
check("and the reading gives the one that holds now", w.read(anna, 'employer') is b_corp)
check("while the one that held then is still answerable",
      [l.object for l in w.links if l.holds_at(d(2019)) is True] == [a_corp])

# --- без даты: кончилось, когда — неизвестно. Ничего не выдумано ---
w = World(); w.pair('capital', 'country', one_object=True, one_subject=True)
germany, bonn, berlin = Thing('Germany'), Thing('Bonn'), Thing('Berlin')
w.relate(bonn, 'capital', germany, 'country')
w.relate(berlin, 'capital', germany, 'country')
old = w.links[0]
check("with no date the earlier one is ended, not erased", old.until is not None)
check("and its end is marked as unsaid, not invented", old.until_is == "before")
check("so asking about the past answers 'nobody knows', not yes and not no",
      old.holds_at(d(1985)) is None, str(old.holds_at(d(1985))))
check("and what holds now is the later one", w.read(germany, 'capital') is berlin)

# --- список или значение падает из кардинальности, не объявляется ---
w = World()
w.pair('mother', 'child', one_subject=True)
w.pair('sibling', 'sibling')
anna, boris, vera = Thing('Anna'), Thing('Boris'), Thing('Vera')
w.relate(anna, 'mother', boris, 'child'); w.relate(anna, 'mother', vera, 'child')
w.relate(boris, 'sibling', vera, 'sibling')
check("many children read as a list", w.read(anna, 'child') == [boris, vera], str(w.read(anna,'child')))
check("one mother reads as a value", w.read(boris, 'mother') is anna)
check("and a symmetric role answers from either end",
      w.read(vera, 'sibling') == [boris] and w.read(boris, 'sibling') == [vera],
      f"{w.read(vera,'sibling')} / {w.read(boris,'sibling')}")

# --- транзитивность: ответ на вопрос, под который связи никто не писал ---
w = World(); w.pair('part', 'whole', transitive=True)
office, kreuzberg, berlin, germany = (Thing('the office'), Thing('Kreuzberg'),
                                      Thing('Berlin'), Thing('Germany'))
w.relate(office, 'part', kreuzberg, 'whole')
w.relate(kreuzberg, 'part', berlin, 'whole')
w.relate(berlin, 'part', germany, 'whole')
reached = w.read(office, 'whole')
check("a chain nobody wrote answers", germany in reached, str(reached))
check("and every step of it is there", reached == [kreuzberg, berlin, germany], str(reached))

# --- два хоста, разные слова, одно отношение ---
w = World()
one = w.pair('chair', 'organization', one_object=True)
two = w.pair('chair', 'organization')
check("the same pair of roles is the same relation, whatever it would have been called",
      one is two)
check("and the word is read off the roles, not asked for", one.word() == "chair_of", one.word())

# --- атрибуты сущностей падают из ролей, ничего не объявлено ---
w = World()
w.pair('capital', 'country', one_object=True, one_subject=True)
w.pair('mother', 'child', one_subject=True)
w.pair('sibling', 'sibling')
w.pair('part', 'whole', transitive=True)
paris, france = w.thing('Paris'), w.thing('France')
anna, boris, vera = w.thing('Anna'), w.thing('Boris'), w.thing('Vera')
office, berlin = w.thing('the office'), w.thing('Berlin')
w.relate(paris, 'capital', france, 'country')
w.relate(anna, 'mother', boris, 'child'); w.relate(anna, 'mother', vera, 'child')
w.relate(boris, 'sibling', vera, 'sibling')
w.relate(office, 'part', berlin, 'whole')
check("the one holding the role is asked <role>_of", paris.capital_of is france)
check("and the other end is asked <role>", france.capital is paris)
check("many reads as a list without anyone declaring the type",
      anna.mother_of == [boris, vera], str(anna.mother_of))
check("one reads as a value, from the same pair", boris.mother is anna)
check("a symmetric role answers from either end", boris.sibling_of == [vera])
check("a chain is followed through the attribute too", office.part_of == [berlin], str(office.part_of))
missing = None
try:
    paris.mayor
except AttributeError as said:
    missing = str(said)
check("and a word no role carries is refused, with what the world does have",
      missing is not None and "capital_of" in missing, str(missing)[:90])

print("\n" + (f"{len(failures)} failed: " + ", ".join(failures) if failures
              else "every claim holds on the examples"))
raise SystemExit(1 if failures else 0)
