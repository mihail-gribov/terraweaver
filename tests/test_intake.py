"""Tests for the intake (intake/): the exchange each step sees, the steps'
order, and the three sources read into one shape.

Run: .venv/bin/python tests/test_intake.py        # no model calls: the models are stand-ins
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intake import sources  # noqa: E402
from intake.intake import exchange, read, window  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Decide:
    """For the memory unless the last message is about code."""
    def __init__(self):
        self.shown = []

    def noul(self, state, question, true, false):
        self.shown.append(state)
        last = state.rsplit("\n", 1)[-1].lower()
        if "new topic" in question:
            yes = "test" in last
        else:
            yes = "test" not in last and "refactor" not in last
        return {"p": {"yes": 0.9 if yes else 0.1, "no": 0.1 if yes else 0.9}}

    def choice(self, state, question, options):
        kind = "memory" if "forget" in state.lower().rsplit("taken out of the last message:", 1)[-1] else "know"
        return {"choice": kind, "p": {kind: 0.8}}


class Resolver:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def say(self, system, prompt, room=None, thinking=True):
        self.prompts.append(prompt)
        return json.dumps(self.answer)


def main() -> int:
    talk = [{"role": "user", "text": "We need a new robot vacuum."},
            {"role": "agent", "text": "What budget do you have for the vacuum?"},
            {"role": "user", "text": "up to 400"}]
    resolver = Resolver({"message": "The vacuum's price must be up to 400 euros", "questions": []})
    got = read(talk, 2, Decide(), resolver)
    check("the message is kept as resolved", got.information == ["The vacuum's price must be up to 400 euros"], str(got))
    got = read(talk, 2, Decide(), Resolver({"questions": []}))
    check("no message from the resolver: kept as said", got.information == ["up to 400"], str(got.as_dict()))
    check("the resolver is shown the agent's message just before, and nothing earlier",
          "What budget do you have for the vacuum?" in resolver.prompts[0] and "We need a new robot vacuum" not in resolver.prompts[0])

    talk += [{"role": "agent", "text": "Noted."}, {"role": "user", "text": "Why does this test fail?"}]
    decide, resolver = Decide(), Resolver({"message": "", "questions": []})
    got = read(talk, 4, decide, resolver)
    check("a work message: nothing for the memory, the resolver never called", got.note == "nothing for the memory" and not resolver.prompts)
    check("the gate reads the last four messages", "Noted." in decide.shown[0] and "up to 400" in decide.shown[0], decide.shown[0])

    talk += [{"role": "agent", "text": "Shall I forget Olga's old number?"},
             {"role": "user", "text": "Mila wants a candlelight concert, find when it is, and yes forget it"}]
    resolver = Resolver({"message": "Mila wants a candlelight concert, find when it is, and yes forget Olga's old number",
                         "questions": ["When is the candlelight concert Mila wants?", "Forget Olga's old number."]})
    got = read(talk, 6, Decide(), resolver)
    check("the message whole as information, the questions apart, each with its kind",
          len(got.information) == 1 and "Mila wants a candlelight concert" in got.information[0]
          and [(q["kind"]) for q in got.requests] == ["know", "memory"], str(got.as_dict()))
    check("the exchange is the agent's message and the user's", len(exchange(talk, 6)) == 2)
    check("the gate's window is the last four messages", len(window(talk, 6)) == 4)
    alone = [{"role": "agent", "text": "Bye", "session": 0}, {"role": "user", "text": "she likes it", "session": 1}]
    got = read(alone, 1, Decide(), Resolver({"message": "Mila likes the concert", "questions": []}))
    check("no agent's message before it: the message is kept as said", got.information == ["she likes it"], str(got.as_dict()))
    check("across a session the agent's message is not shown",
          exchange([{"role": "agent", "text": "Bye", "session": 0}, {"role": "user", "text": "Hi", "session": 1}], 1)[0]["text"] == "Hi")
    runs = sorted(Path("experiments/results/13_dialogues").glob("*/run.json"))
    if runs:
        d = sources.dialogue(str(runs[0]))
        check("our dialogues read as user and agent turns", d and {m["role"] for m in d} == {"user", "agent"})
    names = sources.memops_names()
    if names:
        m = sources.memops(names[0])
        check("MemOps reads with gold on the user turns that trigger an operation",
              any(t.get("gold") for t in m if t["role"] == "user"), names[0])
    try:
        lme = sources.longmemeval(3)
        check("LongMemEval reads with its evidence turns marked", any(t.get("gold") for t in lme))
    except OSError:
        pass
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
