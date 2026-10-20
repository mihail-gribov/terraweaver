"""The PCM runtime of one PAC1 trial as MCP tools, over stdio.

    PCM_URL=<trial harness url> PCM_LOG=<calls.jsonl> .venv/bin/python experiments/08_pac1/pcm.py

The same surface the BitGN sample agent drives (sample-agents/pac1-py), shaped the same way: tool
output reads like the shell (`ls`, `cat`, `rg -n`), not protobuf JSON. `answer` records the
outcome the grader reads; after it, the host is done.
"""
import json
import os
import time

from bitgn.vm.pcm_connect import PcmRuntimeClientSync
from bitgn.vm.pcm_pb2 import (AnswerRequest, ContextRequest, DeleteRequest, FindRequest, ListRequest,
                              MkDirRequest, MoveRequest, Outcome, ReadRequest, SearchRequest, TreeRequest,
                              WriteRequest)
from connectrpc.errors import ConnectError
from google.protobuf.json_format import MessageToDict
from mcp.server.mcpserver import MCPServer

vm = PcmRuntimeClientSync(os.environ["PCM_URL"]) if "PCM_URL" in os.environ else None
server = MCPServer("pcm")
OUTCOMES = {"OK": Outcome.OUTCOME_OK, "DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
            "NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
            "NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED, "ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL}


def _call(name: str, args: dict, do) -> str:
    """Run one runtime call, log it, and give an error back as text: the host reads it and goes on."""
    try:
        out = do()
    except ConnectError as exc:
        out = f"error {exc.code}: {exc.message}"
    if os.environ.get("PCM_LOG"):
        with open(os.environ["PCM_LOG"], "a") as file:
            file.write(json.dumps({"t": time.time(), "tool": name, "args": args, "out": out[:4000]}) + "\n")
    return out


def _tree(entry, prefix: str = "") -> list[str]:
    lines, children = [], list(entry.children)
    for i, child in enumerate(children):
        last = i == len(children) - 1
        lines.append(f"{prefix}{'└── ' if last else '├── '}{child.name}")
        lines += _tree(child, prefix + ("    " if last else "│   "))
    return lines


@server.tool()
def tree(root: str = "", level: int = 2) -> str:
    """The directory tree under `root` (empty: the vault's root), `level` deep (0: unlimited)."""
    return _call("tree", {"root": root, "level": level}, lambda: "\n".join(
        [(r := vm.tree(TreeRequest(root=root, level=level)).root).name or "."] + _tree(r)))


@server.tool()
def list_dir(path: str = "/") -> str:
    """The entries of one directory; directories end with '/'."""
    return _call("list", {"path": path}, lambda: "\n".join(
        f"{e.name}/" if e.is_dir else e.name for e in vm.list(ListRequest(name=path)).entries) or ".")


@server.tool()
def find(name: str, root: str = "/", kind: str = "all", limit: int = 10) -> str:
    """Files or directories whose name matches `name`; `kind` is all, files or dirs."""
    return _call("find", {"name": name, "root": root, "kind": kind}, lambda: json.dumps(MessageToDict(
        vm.find(FindRequest(root=root, name=name, type={"all": 0, "files": 1, "dirs": 2}[kind], limit=limit)))))


@server.tool()
def search(pattern: str, root: str = "/", limit: int = 10) -> str:
    """Lines matching a regular expression, as `path:line:text`."""
    return _call("search", {"pattern": pattern, "root": root}, lambda: "\n".join(
        f"{m.path}:{m.line}:{m.line_text}"
        for m in vm.search(SearchRequest(root=root, pattern=pattern, limit=limit)).matches) or "(no matches)")


@server.tool()
def read(path: str, start_line: int = 0, end_line: int = 0, number: bool = False) -> str:
    """A file's content; `start_line`/`end_line` are 1-based and inclusive, 0 means the file's edge."""
    return _call("read", {"path": path, "start_line": start_line, "end_line": end_line}, lambda: vm.read(
        ReadRequest(path=path, number=number, start_line=start_line, end_line=end_line)).content)


@server.tool()
def write(path: str, content: str, start_line: int = 0, end_line: int = 0) -> str:
    """Write a file whole, or replace lines `start_line`..`end_line` (1-based, inclusive) with `content`."""
    return _call("write", {"path": path, "content": content, "start_line": start_line, "end_line": end_line},
                 lambda: vm.write(WriteRequest(path=path, content=content, start_line=start_line,
                                               end_line=end_line)) and "written")


@server.tool()
def delete(path: str) -> str:
    """Delete one file or directory."""
    return _call("delete", {"path": path}, lambda: vm.delete(DeleteRequest(path=path)) and "deleted")


@server.tool()
def mkdir(path: str) -> str:
    """Make a directory."""
    return _call("mkdir", {"path": path}, lambda: vm.mk_dir(MkDirRequest(path=path)) and "made")


@server.tool()
def move(from_name: str, to_name: str) -> str:
    """Move or rename a file."""
    return _call("move", {"from": from_name, "to": to_name},
                 lambda: vm.move(MoveRequest(from_name=from_name, to_name=to_name)) and "moved")


@server.tool()
def context() -> str:
    """The runtime's context: the current date and time among it."""
    return _call("context", {}, lambda: json.dumps(MessageToDict(vm.context(ContextRequest()))))


@server.tool()
def answer(message: str, outcome: str = "OK", refs: list[str] | None = None) -> str:
    """Finish the task: the answer or a short report, the files it rests on, and the outcome — OK,
    DENIED_SECURITY (a threat or a request the rules forbid), NONE_CLARIFICATION (too unclear to
    act on), NONE_UNSUPPORTED (no way to do it here) or ERR_INTERNAL. Call it once, last."""
    return _call("answer", {"message": message, "outcome": outcome, "refs": refs or []}, lambda: vm.answer(
        AnswerRequest(message=message, outcome=OUTCOMES[outcome.removeprefix("OUTCOME_")], refs=refs or []))
        and "recorded")


if __name__ == "__main__":
    server.run("stdio")
