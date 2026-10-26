"""The decision model as the world uses it, with the model stood in.

Run: .venv/bin/python tests/test_decision.py

What is tested is the world's side — `decision.Decision` as an `outside.Closed`, its Jev shapes, the
calibration it picks up, and `outside.Nemotron` as the engineer over the same client. The reading
itself (orders, temperatures, marks) is tested in tests/test_nemotron.py; Nemotron is
measured in experiments/09_decision.
"""
import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terraweaver.nemotron import Nemotron  # noqa: E402
from terraweaver import decision, outside  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


class Leaning:
    """A stand-in endpoint: likes the first letter, and likes the option containing `likes` more."""

    def __init__(self, likes: str):
        self.likes, self.shown = likes, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, messages, **_):
        lines = [l for l in messages[1]["content"].splitlines() if len(l) > 2 and l[1] == ")"]
        self.shown.append([l[3:] for l in lines])
        tops = [SimpleNamespace(token=l[0], logprob=(-0.2 if i == 0 else -2.0) + (1.0 if self.likes in l else 0.0))
                for i, l in enumerate(lines)]
        return SimpleNamespace(choices=[SimpleNamespace(
            logprobs=SimpleNamespace(content=[SimpleNamespace(top_logprobs=tops)]))])


def picker(likes: str, calibration=False):
    return decision.Decision(client=Leaning(likes), calibration=calibration)


def main() -> int:
    one = picker("no", {"noul": {"orders": 1, "temperature": 1.0}})
    check("one order: the first letter's lean decides", one.yes("s", "q?", "yes", "no") > 0.5)
    both = picker("no")
    check("both orders: the lean cancels and the liked option wins", both.yes("s", "q?", "yes", "no") < 0.5)
    check("both orders: shown as given and reversed",
          both.reader.client.shown == [["yes", "no"], ["no", "yes"]], str(both.reader.client.shown))

    got = picker("neither").ask("s", {"q": {"type": "tfu", "instructions": "q?",
                                            "criteria": {"true": "yes", "false": "no"}}})["q"]
    check("tfu: a third option, the text does not settle it",
          set(got["probabilities"]) == {"true", "false", "unsure"} and got["unsure"] > 0.5, str(got))

    picked = picker("Place").choose("s", "which?", {"Person": "a Person", "Place": "a Place", "Event": "an Event"})
    check("choice: probabilities by option name, summing to one",
          max(picked, key=picked.get) == "Place" and math.isclose(sum(picked.values()), 1.0), str(picked))

    cold = picker("yes", {"noul": {"temperature": 4.0, "orders": 2}}).yes("s", "q?", "yes", "no")
    warm = picker("yes").yes("s", "q?", "yes", "no")
    check("a temperature above one softens without reordering", 0.5 < cold < warm, f"{cold:.2f} vs {warm:.2f}")

    check("it reads links as claims in the check", getattr(picker("x"), "asks_claims", False))
    shipped = decision.Decision(client=Leaning("x"))
    check("the shipped calibration is picked up for the Nano",
          set(shipped.reader.calibration) >= {"noul", "tfu", "choice"}, str(shipped.reader.calibration))
    other = decision.Decision(model="other/model", client=Leaning("x"))
    check("and none of it for another model", other.reader.calibration == {}, str(other.reader.calibration))

    # The engineer is the same client in its other role.
    seen: dict = {}
    said = SimpleNamespace(usage=SimpleNamespace(completion_tokens=5),
                           choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="a word"))])

    def create(**kw):
        seen.update(kw)
        return said

    engineer = outside.Nemotron.__new__(outside.Nemotron)
    engineer.room = 1234
    engineer.client = Nemotron(client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))),
                               calibration=False)
    check("the engineer speaks through the same client", engineer.say("sys", "hi") == "a word")
    check("with the room the world gives it", seen.get("max_tokens") == 1234, str(seen.get("max_tokens")))

    print(f"\n{'all passed' if not failures else f'{len(failures)} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
