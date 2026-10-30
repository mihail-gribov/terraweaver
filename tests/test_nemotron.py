"""`memory.nemotron`, with the model stood in: both orders, the temperature, the shapes of
answer, and the same client speaking as an LLM.

    .venv/bin/python tests/test_nemotron.py
"""
import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory.nemotron import CALIBRATION, CutOff, Nemotron, Reader, calibrate, fitted_for  # noqa: E402

failures = []


def check(name, condition):
    print(f"{'PASS' if condition else 'FAIL'}  {name}")
    if not condition:
        failures.append(name)


class Leaning:
    """A stand-in endpoint that likes the first mark, and the option containing `likes` more."""

    def __init__(self, likes):
        self.likes, self.calls = likes, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, messages, **_):
        self.calls += 1
        lines = [l for l in messages[1]["content"].splitlines() if len(l) > 2 and l[1] == ")"]
        tops = []
        for i, line in enumerate(lines):
            score = (2.0 if self.likes in line else 0.0) + (1.0 if i == 0 else 0.0)
            tops.append(SimpleNamespace(token=line[0], logprob=score - 4.0))
        return SimpleNamespace(choices=[SimpleNamespace(
            logprobs=SimpleNamespace(content=[SimpleNamespace(top_logprobs=tops)]))])


lean = Leaning("covers")
r = Reader(client=lean, calibration=False)
got = r.noul("policy", "Is it covered?", true="the policy covers it", false="the policy excludes it")
check("noul answers yes and no", set(got["p"]) == {"yes", "no"} and got["p"]["yes"] > 0.5)
check("two orders are two calls", lean.calls == 2)
check("the first-place lean cancels", abs((got["logits"]["true"] - got["logits"]["false"]) - 2.0) < 1e-9)

lean = Leaning("nothing")
one = Reader(client=lean, calibration={"noul": {"orders": 1, "temperature": 1.0}})
got = one.noul("x", "q?", true="a", false="b")
check("one order keeps the lean", got["p"]["yes"] > 0.5 and lean.calls == 1)

cold = Reader(client=Leaning("covers"), calibration=False).noul("p", "q?", true="covers", false="no")["p"]["yes"]
hot = Reader(client=Leaning("covers"), calibration={"noul": {"temperature": 2.0, "orders": 2}})
p_hot = hot.noul("p", "q?", true="covers", false="no")["p"]["yes"]
check("a temperature softens, never flips", 0.5 < p_hot < cold and abs(cold - 1 / (1 + math.exp(-2))) < 1e-9)

t = Reader(client=Leaning("neither"), calibration=False).tfu("x", "q?", true="a", false="b")
check("tfu has a third answer", t["verdict"] == "unsure" and set(t["p"]) == {"true", "false", "unsure"})

c = Reader(client=Leaning("capped"), calibration=False).choice(
    "x", "settle?", [("deny", "excluded"), ("sublimit", "covered but capped"), ("pay", "in full")])
check("choice names the option, not the letter", c["choice"] == "sublimit")

jev = Reader(client=Leaning("covered"), calibration=False).ask("policy", {
    "a": {"type": "noul", "instructions": "q?", "criteria": {"true": "covered", "false": "excluded"}},
    "b": {"type": "choice", "instructions": "q?", "criteria": {"x": "covered", "y": "excluded"}}})
check("ask answers in Jev's fields", "noul" in jev["a"] and jev["b"]["choice"] == "x")

shipped = fitted_for(CALIBRATION,
                     "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
check("the shipped calibration is the Nano's", set(shipped) >= {"noul", "tfu", "choice", "scale"})
check("another model gets none of it", fitted_for(
    CALIBRATION, "other/model") == {})

import json as _json  # noqa: E402
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    two = Path(d) / "decision.json"
    two.write_text(_json.dumps({"models": {"nvidia/a": {"calibration": {"noul": {"temperature": 2.0}}},
                                           "nvidia/b": {"calibration": {"noul": {"temperature": 0.5}}}}}))
    check("each Nemotron gets its own calibration", fitted_for(two, "nvidia/a")["noul"]["temperature"] == 2.0
          and fitted_for(two, "nvidia/b")["noul"]["temperature"] == 0.5)
    unfitted = Nemotron(model="nvidia/c", client=Leaning("x"), calibration=two)
    check("any other Nemotron still reads: both orders, temperature 1",
          unfitted._fitted("noul") == {"temperature": 1.0, "orders": 2})

rows = [({"true": 3.0, "false": 0.0}, "true" if i % 4 else "false") for i in range(40)]
fit = calibrate(rows)
check("calibrate softens an overconfident reader", fit["temperature"] > 1.0 and fit["ece_after"] < fit["ece_before"])



class Speaking:
    """A stand-in endpoint for the LLM role: says `said`, or is cut off with nothing said."""

    def __init__(self, said, finish="stop"):
        self.said, self.finish, self.asked = said, finish, None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.asked = kw
        return SimpleNamespace(usage=SimpleNamespace(completion_tokens=kw["max_tokens"]),
                               choices=[SimpleNamespace(finish_reason=self.finish,
                                                        message=SimpleNamespace(content=self.said))])


llm = Speaking('Here it is: {"name": "Celebration"}')
n = Nemotron(client=llm)
check("one client is also the LLM: say", n.say("sys", "hi").startswith("Here it is"))
check("thinking is on for the LLM, with room", llm.asked["extra_body"]["chat_template_kwargs"]["enable_thinking"]
      and llm.asked["max_tokens"] == Nemotron.ROOM)
check("json reads the object out of the words", n.json("sys", "hi") == {"name": "Celebration"})
check("json is None when there is no object", Nemotron(client=Speaking("no idea")).json("s", "p") is None)
try:
    Nemotron(client=Speaking("", finish="length")).say("s", "p", room=3000)
    check("a cut-off answer raises CutOff", False)
except CutOff as wrong:
    check("a cut-off answer raises CutOff, naming the room to give", "room=8000" in str(wrong))
check("Reader is the same client", Reader is Nemotron)

print(f"\n{len(failures)} failed" if failures else "\nall passed")
sys.exit(1 if failures else 0)
