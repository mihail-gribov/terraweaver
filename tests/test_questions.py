"""Tests for open questions: what doesn't add up is taken, remembered, and raised again.

Run: .venv/bin/python tests/test_questions.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.runtime import format_result

import base  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def main() -> int:
    # A base world and the few people these checks talk about, said the way a host says them.
    rt = base.world("host")
    base.word(rt, "patient_of", "a person and the dentist who treats them", "many-to-one",
              "a patient", "their dentist")
    base.attribute(rt, "Person", "phone", "The number this person answers.", type="phone")
    rt.run('Person.new(full_name="Ada Lovelace")\nPerson.new(full_name="Anna Peterson")\n'
           'Person.new(full_name="Anna Sullivan")\nPerson.new(full_name="Annie Moore")\n'
           'Person.new(full_name="Annie Lee")', "host")

    # --- a doubt about a link: taken, and remembered ---
    first = rt.run('rao = Person.new(full_name="Arun Rao")\n'
                   'user.set_patient_of(rao)\n'
                   'user.question("two dentists? the user also named Nina Patel", '
                   'options=["Nina replaced Arun", "both stand"], about="patient_of")', "host")
    check("the write goes through", first["ok"], str(first["error"]))
    check("and the doubt is recorded", any("two dentists" in q.text for q in rt.world.questions.open_(limit=100)),
          str(rt.world.questions.open_(limit=100)))

    # --- it outlives the run and the session, and surfaces where it bears on the answer ---
    quiet_touch = rt.run('m = user', "another-host")
    check("merely touching the entity is not interrupted with it",
          not quiet_touch["ask_now"], str(quiet_touch["ask_now"]))
    later = rt.run('print([p.full_name for p in user.related("patient_of")])', "another-host")
    check("a read that depends on it is told, in another session",
          any("two dentists" in line for line in later["ask_now"]), str(later["ask_now"]))
    check("the answers that would settle it come with it",
          "both stand" in format_result(later), format_result(later))

    # --- a question whose reason is gone closes itself ---
    # A thing that came in as a bare name is asked about; saying what it is is the answer, and
    # the question has no reason left the moment there are words on it.
    rt.run('rome = Thing.identify(name="Rome")[0]', "host")
    asked_rome = [q for q in rt.world.questions.open_(limit=100) if getattr(q.about, "name", None) == "Rome"]
    check("a bare name is asked about", len(asked_rome) == 1, str(asked_rome))
    rt.run('rome.describe("the city the user lived in until 2019")', "host")
    check("and the question closes itself once it is said",
          not [q for q in rt.world.questions.open_(limit=100) if getattr(q.about, "name", None) == "Rome"],
          str(rt.world.questions.open_(limit=100)))

    # --- settling who the task is about, when the name fits two people ---
    rt2 = base.world("host")
    rt2.run('Person.new(full_name="Olga Gribova")\nPerson.new(full_name="Olga Pavlova")', "host")
    made_new = rt2.run('q = Person.get(full_name="Olga")\nolga = world.settle(q, new=True)', "host")
    check("settling as new goes through", made_new["ok"], str(made_new["error"]))
    check("and leaves the doubt about the twin",
          any("the same one?" in q for q in made_new["questions"]), str(made_new["questions"]))

    # --- answering closes it, and it isn't raised again ---
    answered = rt2.run('q = olga.questions()[0]\nq.answer("a different Olga — the user said so")\n'
                       'print(olga.questions())', "host")
    check("answering closes it", answered["output"].strip() == "[]", answered["output"])
    again = rt2.run('other = Person.get(full_name="Olga")\nworld.settle(other, new=True)', "host")
    check("the same doubt about the same pair isn't raised twice",
          not any("Olga Gribova" in q and "the same one?" in q for q in again["questions"]),
          str(again["questions"]))

    # One world is current at a time, and the rest of this talks to the first one again.
    from terraweaver import ontology
    ontology.set_world(rt.world)

    # --- one the host noticed itself ---
    own = rt.run('before = len(world.questions())\n'
                 'anna = Person.get(full_name="Anna Peterson")\n'
                 'anna.question("two numbers on file, which is current?", options=["the mobile", "the old one"])\n'
                 'print(len(world.questions()) - before)', "host")
    check("the host can record a question of its own", own["output"].strip() == "1", own["output"])
    dropped = rt.run('anna.questions()[0].drop("asked, it is the mobile")\nprint(anna.questions())', "host")
    check("and drop it when it stops mattering", dropped["output"].strip() == "[]", dropped["output"])

    # --- there is always one reading, even unanswered ---
    rule = rt.run('q = user.questions()[0]\nprint(q.assumption)', "host")
    check("an unanswered question says what stands meanwhile", "latest" in rule["output"], rule["output"])

    # --- a read that depends on the doubt is told before it answers ---
    depends = rt.run('print([p.full_name for p in user.related("patient_of")])', "reader")
    check("a read of the questioned relation is told to ask first",
          any("two dentists" in line for line in depends["ask_now"]), str(depends["ask_now"]))
    check("and isn't repeated in the passive list",
          not any("two dentists" in q for q in depends["questions"]), str(depends["questions"]))
    quiet = rt.run('print(user.full_name)', "reader")
    check("an unrelated read is left alone", not quiet["ask_now"], str(quiet["ask_now"]))

    # --- what this task touched, offered when the task ends ---
    mine = rt.run('print(len(world.questions(here=True)))', "host")
    check("a session can ask what it left open", mine["output"].strip() not in ("", "0"), mine["output"])
    fresh = rt.run('print(world.questions(here=True))', "untouched-session")
    check("a session that touched nothing is offered nothing", fresh["output"].strip() == "[]", fresh["output"])
    left = rt.reset_session("host")
    check("ending a task hands the leftovers over", "two dentists" in left, left)

    # --- the ones worth asking come first ---
    rt.run('anna = Person.get(full_name="Anna Peterson")\n'
           'anna.question("two numbers on file, which is current?", about="phone")', "host")
    for _ in range(4):
        rt.run('Person.get(full_name="Anna Peterson")', "host")
    order = rt.run('print([getattr(q.about, "full_name", None) for q in world.questions()])', "host")
    check("the entity that comes up most often is asked about first",
          order["output"].strip().startswith("['Anna Peterson'"), order["output"])
    attr = rt.run('a = Person.get(full_name="Anna Peterson")\nprint(a.phone)', "reader")
    check("a read of the questioned attribute is told to ask first",
          any("two numbers" in line for line in attr["ask_now"]), str(attr["ask_now"]))

    # --- an answer keeps where it came from ---
    sourced = rt.run('a = Person.get(full_name="Anna Peterson")\n'
                     'a.question("is DataWorks its registered name?", about="works_at")\n'
                     'q = [one for one in a.questions() if "DataWorks" in one.text][0]\n'
                     'q.answer("DataWorks Ltd", by="companies-house.gov.uk")\n'
                     'past = [one for one in a.questions(include_closed=True) if "DataWorks" in one.text][-1]\n'
                     'print(past.answer_text, "|", past.answered_by)', "host")
    check("a question can be settled by a source, not only by the user",
          sourced["output"].strip() == "DataWorks Ltd | companies-house.gov.uk",
          str(sourced["error"]) or sourced["output"])
    # --- the world doesn't fight how the host writes code ---
    styled = rt.run('from datetime import date, timedelta\n'
                    'from collections import Counter\n'
                    'print(date(2026, 1, 1), timedelta(days=1), Counter("aab")["a"])', "host")
    check("an import of what is already provided is granted, not refused",
          styled["ok"] and styled["output"].startswith("2026-01-01"), str(styled["error"]))
    habit = rt.run('from datetime import datetime, timedelta\n'
                   'import datetime\n'
                   'from datetime import time\n'
                   'print(datetime.datetime(2026, 10, 1), time(9, 15), timedelta(days=1))', "host")
    check("an import of what is already here is simply not needed",
          habit["ok"] and "2026-10-01" in habit["output"] and "09:15" in habit["output"],
          str(habit["error"]) or habit["output"])
    # An import this world hasn't got used to cost the whole block it stood in — twenty-five
    # facts thrown away over a habit on line one. It is dropped now, and the name stays unbound.
    skipped = rt.run('import os\nprint("the rest still runs")', "host")
    check("an import of something the world doesn't provide is dropped, not refused",
          skipped["ok"] and "the rest still runs" in skipped["output"], str(skipped["error"]))
    check("and the host is told which one went",
          any("skipped the import of os" in h for h in skipped.get("hints", [])),
          str(skipped.get("hints")))
    unbound = rt.run('import os\nprint(os.listdir("/"))', "host")
    check("what it stood for is not reachable", not unbound["ok"]
          and "not defined" in str(unbound["error"]), str(unbound["error"]))

    # --- a world structure misused answers where it can, teaches where it can't ---
    misused = rt.run('print(Person.find(full_name="Ada").full_name)', "host")
    check("a search result with one match answers as that one",
          misused["ok"] and "Ada Lovelace" in misused["output"], str(misused["error"]))
    check("and says the answer came from the one match",
          any("read from the one match" in line for line in misused["assumed"]), str(misused["assumed"]))
    crowd = rt.run('print(Person.find(full_name="Anna").similar.full_name)', "host")
    check("with several it says which one to name",
          "result.similar[0].full_name" in str(crowd["error"]), str(crowd["error"]))
    asked = rt.run('print(Person.find(full_name="Annie").full_name)', "host")
    check("a question mistaken for the entity says what settles it",
          "world.settle" in str(asked["error"]), str(asked["error"]))

    # --- a question blocks nothing ---
    check("nothing about it raised an error", own["ok"] and dropped["ok"], str(own["error"] or dropped["error"]))

    print()
    if failures:
        print(f"{len(failures)} failed: {', '.join(failures)}")
        return 1
    print("all question tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
