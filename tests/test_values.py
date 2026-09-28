"""Tests for value kinds: each normalizes to one canonical form, and the world compares by it.

Run: .venv/bin/python tests/test_values.py
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.values import Domain, Email, Phone, Url, Value

import base  # noqa: E402

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

    # --- the world compares by them, on attributes the world grew for itself ---
    # A world starts with names only. An address, a number, a website are attributes it grows
    # when it is told one, and the kind the attribute is given is what it is compared by.
    rt = base.world()
    base.attribute(rt, "Person", "email", "The address this person reads their mail at.", type="email")
    base.attribute(rt, "Person", "phone", "The number this person answers.", type="phone")
    base.attribute(rt, "Thing", "website", "Where this thing is on the web.", type="domain")
    base.attribute(rt, "Event", "kind", "What kind of event this is — recorded, not read off the title.",
                   type="enum[interview, call, meeting, appointment, other]")
    classes = rt.world.classes
    Person, Thing = classes["Person"], classes["Thing"]
    Person.new(full_name="Ada Lovelace", email="ada@example.com")
    check("find by email ignores case and spaces", Person.get(email="  ADA@example.com ").full_name == "Ada Lovelace")
    ada = Person.get(email="ada@example.com")
    ada.phone = " +1 (555) 010-2030 "
    check("a stored value keeps its own format, only stripped", ada.phone == "+1 (555) 010-2030")
    check("find by phone ignores formatting", Person.get(phone="+15550102030") is ada)
    techcorp = Thing.new(name="TechCorp")
    techcorp.website = "https://www.techcorp.com/"
    check("a website matches on its domain, however the address was written",
          Thing.find(website="techcorp.com/jobs").matches == [techcorp])
    twin = Person.new(full_name="Ada L", email="Ada@Example.com")
    # An address nobody else has is not a resemblance. The same rule identification uses
    # everywhere here: one candidate, nothing that disagrees, no question — and what the host
    # called them is kept as another name they answer to.
    check("an email written differently is the same person, not a question", twin is ada)
    check("and the name it was given is kept as one of theirs",
          any(a.lower() == "ada l" for a in (ada.aliases or [])), str(ada.aliases))

    # --- one word for one thing, however it was typed ---
    event = classes["Event"].new(title="Sync", kind="Meeting", start_time=datetime(2026, 10, 1, 10, 0))
    check("a vocabulary word is kept in the world's spelling", event.kind == "meeting", str(event.kind))
    refused = None
    try:
        classes["Event"].new(title="Chat", kind="catch-up", start_time=datetime(2026, 10, 1, 11, 0))
    except (ValueError, TypeError) as exc:
        refused = str(exc)
    check("a word outside the vocabulary is refused with the list",
          refused is not None and "interview, call, meeting" in refused, str(refused))
    check("and the refusal says what to do instead", refused is not None and "remark" in refused)

    # --- a value that can't be its kind is kept, and asked about ---
    ada = Person.get(email="ada@example.com")
    ada.phone = "call me maybe"
    asked = [q for q in ada.questions() if "phone" in q.text]
    check("a phone with no number in it is questioned, not refused",
          ada.phone == "call me maybe" and len(asked) == 1, str(asked))
    ada.phone = "+1 (555) 010-2030"
    check("a real number raises nothing",
          len([q for q in ada.questions() if "010-2030" in q.text]) == 0)

    # --- a name the class answers with a call is not a value it can hold ---
    # Written as an assignment, `set_speaks` was taken for a new attribute, and the old value
    # history then read off the class for it was the bound setter: json.dumps raised on a method
    # and every write to any Person in that world raised after it, for the rest of a measured run.
    rt = base.world()
    rt.run('world.define_relation("speaks", "a person and a language they speak", '
           'nature="related_to", cardinality="many-to-many", subject_is="the speaker", '
           'object_is="the language")', "k")
    rt.run('p = Person.new(full_name="Kukai")\nl = Thing.new(name="Japanese")', "k")
    said = str(rt.run('p.set_speaks = l', "k").get("error") or "")
    check("an assignment to a word for a link is refused with the call to write",
          "set_speaks(other)" in said and "not an assignment" in said, said[-160:])
    said = str(rt.run('p.describe = "a monk"', "k").get("error") or "")
    check("and so is an assignment over anything else the class does",
          "does, not a value it holds" in said, said[-160:])
    check("while the call itself goes through", rt.run('p.set_speaks(l)', "k").get("error") is None)
    check("and a name nothing answers still grows",
          rt.run('p.mood = "calm"', "k").get("error") is None)

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all value tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
