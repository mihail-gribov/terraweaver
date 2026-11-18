"""A forget reaches the trace: no line keeps a forgotten entry (memory/trace.py)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import trace  # noqa: E402


def test_forget_takes_the_lines_out():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trace.jsonl"
        trace.to(path)
        try:
            phone = "The user's old phone number is 555-0100."
            said = "my old number was 555-0100"
            trace.step("gate", said=said, rewritten=phone, personal=0.9)
            trace.step("kept", entry=7, text=f'{phone}\n(said: "{said}")')
            trace.step("read", entry=7, links=[{"quote": "phone number is 555-0100"}])
            trace.step("ask", question="What is my number?", found=f"#7 {phone}", answer="555-0100")
            trace.step("gate", said="I bought a bicycle.", rewritten="The user bought a bicycle.", personal=0.8)
            trace.step("kept", entry=8, text="The user bought a bicycle.")
            trace.forget([(7, f'{phone}\n(said: "{said}")')])
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            assert "555-0100" not in path.read_text(), rows
            assert [(r["step"], r.get("entry")) for r in rows] == [("gate", None), ("kept", 8)], rows
        finally:
            trace.to(None)


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
