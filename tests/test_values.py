"""Tests for value kinds: each normalizes to one canonical form, and the world compares by it.

Run: .venv/bin/python tests/test_values.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.impls import IMPLS
from terraweaver.ontology import build_classes, load_specs
from terraweaver.store import Store
from terraweaver.values import Domain, Email, Phone, Url, Value
from terraweaver.world import World
from worlds.job_search import build

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent / "ontology" / "core"

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    # --- each kind on its own ---
    check("a plain value is only stripped", Value.normalize("  Ada Lovelace ") == "Ada Lovelace")
    check("email: case and mailto: don't matter", Email.normalize(" MailTo:Ada@Example.COM ") == "ada@example.com")
    check("phone: formatting doesn't matter", Phone.normalize("+1 (555) 010-2030") == "+15550102030")
    check("phone: 00 is the same as +", Phone.normalize("0044 20 7946 0958") == "+442079460958")
    check("phone: no country code stays digits only", Phone.normalize("555-0102") == "5550102")
    check("domain: no scheme, path or www", Domain.normalize("https://WWW.Example.com/path") == "example.com")
    check("domain: international names as punycode", Domain.normalize("bücher.de") == "xn--bcher-kva.de")
    raw = "HTTP://Example.com:80/Jobs/?b=2&a=1&utm_source=x#top"
    check("url exact keeps the query and fragment",
          Url.normalize(raw, level="exact") == "http://example.com/Jobs?b=2&a=1&utm_source=x#top")
    check("url page drops tracking and fragment, sorts the rest",
          Url.normalize(raw, level="page") == "https://example.com/Jobs?a=1&b=2")
    check("url site is the registered domain, public suffixes respected",
          Url.normalize("https://careers.acme.co.uk/jobs/42", level="site") == "acme.co.uk")

    # --- the world compares by them ---
    classes = build_classes(load_specs(ONTOLOGY_DIR), IMPLS)
    store = Store(":memory:")
    build(classes, store)
    World(store, classes)
    Person, Organization = classes["Person"], classes["Organization"]
    check("find by email ignores case and spaces", Person.get(email="  ADA@example.com ").full_name == "Ada Lovelace")
    ada = Person.get(email="ada@example.com")
    ada.phone = " +1 (555) 010-2030 "
    check("a stored value keeps its own format, only stripped", ada.phone == "+1 (555) 010-2030")
    check("find by phone ignores formatting", Person.get(phone="+15550102030") is ada)
    techcorp = Organization.get(name="TechCorp")
    techcorp.website = "https://www.techcorp.com/"
    check("a company website matches on its domain",
          Organization.find(website="https://careers.techcorp.com/jobs").main == [techcorp])
    twin = Person.new(full_name="Ada L", email="Ada@Example.com")
    check("an email written differently still reveals a twin", getattr(twin, "skill", None) == "resolve_ambiguity")

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all value tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
