DESCRIPTION = """The question assumes something the world doesn't hold: there is no interview with
QuantumLeap, only a call with Alan about QuantumLeap. The host must say so rather than present the
call as an interview, and must not change the world."""

SETUP = ""

TURNS = ["Using my world (terraweaver): when is my interview with QuantumLeap?"]

EXPECT = """
assert len(Event.all(limit=None, history=True)) == 3, "events were added or removed"
call = Event.get(title="Call with Alan about QuantumLeap")
assert call.kind == "call", f"the call became a {call.kind}"
"""

ANSWER_MUST = ["call", "Alan"]
