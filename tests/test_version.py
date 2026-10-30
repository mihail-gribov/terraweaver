"""One version for the memory and the plugin that talks to it."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import memory  # noqa: E402


def test_plugin_and_memory_have_one_version():
    plugin = json.loads((ROOT / "adapters/claude_code/plugin/.claude-plugin/plugin.json").read_text())
    assert plugin["version"] == memory.__version__, (plugin["version"], memory.__version__)


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
