"""Limits on what a host's code can do: the world, plain computation, nothing else.

No files, no processes, no network, no imports. Enforced three ways:

- the code is checked before it runs (`check`): no import statements, no access to names or
  attributes that lead into the interpreter's internals;
- it runs with a reduced set of builtins (`BUILTINS`): no `open`, `eval`, `exec`,
  `__import__`, `input` — and `getattr`/`setattr` that refuse private names;
- useful modules are handed over as whitelists of functions (`MODULES`), never as modules:
  a real module drags in others (`statistics.sys`, `re.enum.sys`), and `sys` reaches `os`.

This is a guard against sloppy or misled host code, not a security boundary against a
determined attacker — CPython can't be sandboxed reliably in-process. That is why the server
also requires a token for network access; real isolation means a separate restricted process.
"""
import ast
import builtins
import collections
import datetime as _datetime
import itertools
import json
import math
import re
import signal
import statistics
from typing import Any
from contextlib import contextmanager
from types import SimpleNamespace

from terraweaver import conditions

TIMEOUT_SECONDS = 10


class SandboxViolation(Exception):
    """The code tried something the world doesn't allow."""


# Attributes that aren't private by name yet lead straight to frames, code and globals.
_FORBIDDEN_ATTRS = {
    "gi_frame", "gi_code", "gi_yieldfrom", "cr_frame", "cr_code", "cr_await", "ag_frame",
    "ag_code", "f_globals", "f_locals", "f_builtins", "f_back", "f_code", "tb_frame", "tb_next",
    "format_map", "mro",
}
# Names that are only strings — `type(e).__name__` is how code says which error it caught.
_SAFE_DUNDERS = {"__name__", "__qualname__", "__doc__"}
# A format string can reach attributes too: "{0.__class__}".format(x).
_FORMAT_FIELD_ATTR = re.compile(r"\{[^}]*[.\[]")


class _ImportsAlreadyHere(ast.NodeTransformer):
    """Drop an import that asks for what the namespace already holds.

    `from datetime import datetime, timedelta` is a habit, not a request — it was written 55
    times in one pool, and each one cost the statement it stood in. Nothing is imported and
    nothing is hidden: the names were already bound, so the line is simply not needed. An
    import of anything else is still refused, because that is about what the code may reach.
    """

    def __init__(self, lenient: bool):
        super().__init__()
        self.lenient = lenient          # code run once may lose a line; code kept must not
        self.skipped: list[str] = []

    def visit_Import(self, node):
        wanted = [alias.asname or alias.name.split(".")[0] for alias in node.names]
        if all(name in MODULES for name in wanted):
            return None
        return self._skip(node, [a.name for a in node.names if a.name.split(".")[0] not in MODULES])

    def visit_ImportFrom(self, node):
        holder = MODULES.get(node.module)
        if holder is None:
            return self._skip(node, [node.module or "?"])
        binds = []
        for alias in node.names:
            if not hasattr(holder, alias.name) and alias.name not in MODULES:
                return self._skip(node, [f"{node.module}.{alias.name}"])
            if (alias.asname or alias.name) in MODULES and not alias.asname:
                continue         # already bound under that very name
            # `from datetime import time` asks for something real that simply isn't bound yet:
            # bind it rather than refuse the line.
            source = ast.Attribute(value=ast.Name(id=node.module, ctx=ast.Load()),
                                   attr=alias.name, ctx=ast.Load())
            binds.append(ast.Assign(targets=[ast.Name(id=alias.asname or alias.name,
                                                      ctx=ast.Store())], value=source))
        return [ast.copy_location(ast.fix_missing_locations(b), node) for b in binds] or None


    def _skip(self, node, names: list[str]):
        """An import of what this world hasn't got is dropped, not refused.

        Refusing it threw away the whole block, so host code run once drops it instead. Code
        that is stored — a procedure — is still refused: keeping something that cannot run is a
        lasting defect, not a lost line.

        Refusing it threw away the whole block: `import inspect` on line 1 cost twenty-five facts
        on lines 2 to 40, and the import was usually a habit the code never used. Dropping leaves
        the name unbound, so code that really wanted it fails on that one statement and everything
        around it still stands — and nothing unavailable becomes reachable by dropping a line.
        """
        if not self.lenient:
            return node                 # left for the walk below, which refuses it
        self.skipped.extend(names)
        return None


def check(code: str, protected: set[str] = frozenset(), always: set[str] = frozenset(),
          skipped: list | None = None) -> ast.AST:
    """Parse and vet host code. Raises SandboxViolation, or SyntaxError for broken code.

    What may be refused is what touches the data: writing where the world keeps its own state,
    reaching past the object model, running longer than a host should. How the host writes its
    code is its own business.

    `protected` names can be read but not rebound — world variables change only via world.pin.
    """
    imports = _ImportsAlreadyHere(lenient=skipped is not None)
    tree = ast.fix_missing_locations(imports.visit(ast.parse(code, "<run>")))
    if skipped is not None:
        # Named here, told to the host by whoever is recording — this runs before there is
        # anywhere to note it.
        skipped.extend(sorted(set(imports.skipped)))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in protected:
            if node.id in always:
                raise SandboxViolation(
                    f"'{node.id}' is one of the two this world is between and is in every namespace; "
                    f"pick another name for a local variable"
                )
            raise SandboxViolation(
                f"'{node.id}' is a world variable; change it with world.pin({node.id}, value, "
                f"\"description\") or pick another name for a local variable"
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in protected:
            raise SandboxViolation(f"'{node.name}' is a world variable; pick another name")
        if isinstance(node, ast.arg) and node.arg in protected:
            raise SandboxViolation(f"'{node.arg}' is a world variable; pick another parameter name")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxViolation(
                "that import isn't available — " + AVAILABLE.split(". No files")[0].lower() +
                ". Importing one of those is fine; it's already bound for you."
            )
        if isinstance(node, ast.Attribute) and node.attr not in _SAFE_DUNDERS and (
                node.attr.startswith("_") or node.attr in _FORBIDDEN_ATTRS):
            raise SandboxViolation(f"attribute '{node.attr}' is not accessible")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise SandboxViolation(f"name '{node.id}' is not accessible")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            receiver = node.func.value
            if not (isinstance(receiver, ast.Constant) and isinstance(receiver.value, str)):
                raise SandboxViolation("str.format is only allowed on a literal string; use an f-string")
            if _FORMAT_FIELD_ATTR.search(receiver.value):
                raise SandboxViolation("format fields can't access attributes or items; use an f-string")
    return tree


def _public(name) -> str:
    if not isinstance(name, str) or name.startswith("_") or name in _FORBIDDEN_ATTRS:
        raise SandboxViolation(f"attribute {name!r} is not accessible")
    return name


def _getattr(obj, name, *default):
    return getattr(obj, _public(name), *default)


def _hasattr(obj, name) -> bool:
    return hasattr(obj, _public(name))


def _setattr(obj, name, value) -> None:
    setattr(obj, _public(name), value)


_ALLOWED_BUILTINS = [
    "abs", "all", "any", "ascii", "bin", "bool", "bytes", "callable", "chr", "dict", "dir",
    "divmod", "enumerate", "filter", "float", "format", "frozenset", "hash", "hex", "id", "int",
    "isinstance", "issubclass", "iter", "len", "list", "map", "max", "min", "next", "object",
    "oct", "ord", "pow", "print", "range", "repr", "reversed", "round", "set", "slice", "sorted",
    "str", "sum", "tuple", "type", "zip", "True", "False", "None", "NotImplemented", "Ellipsis",
    # Exceptions, so code can raise and catch the ordinary ones.
    "Exception", "ArithmeticError", "AssertionError", "AttributeError", "IndexError", "KeyError",
    "LookupError", "NameError", "NotImplementedError", "RuntimeError", "StopIteration",
    "TypeError", "ValueError", "ZeroDivisionError",
]

BUILTINS = {name: getattr(builtins, name) for name in _ALLOWED_BUILTINS}
BUILTINS.update(getattr=_getattr, hasattr=_hasattr, setattr=_setattr)


class _Dt(_datetime.datetime):
    """`datetime` as hosts reach for it: the class, and also the module they expect around it.

    `datetime(2026, 10, 1)` is what the world's own examples use, and `datetime.datetime(...)`
    is what a host writes out of habit after `import datetime`. Both work here, so neither
    costs a statement."""

    datetime = _datetime.datetime
    date = _datetime.date
    time = _datetime.time
    timedelta = _datetime.timedelta
    timezone = _datetime.timezone


def _only(module, *names) -> SimpleNamespace:
    return SimpleNamespace(**{name: getattr(module, name) for name in names})


MODULES = {
    "math": _only(math, "ceil", "floor", "sqrt", "log", "log10", "exp", "pow", "fabs", "isclose",
                  "inf", "nan", "pi", "e", "fsum", "prod", "isnan", "isinf"),
    "statistics": _only(statistics, "mean", "median", "mode", "stdev", "pstdev", "variance",
                        "quantiles", "fmean"),
    "re": _only(re, "search", "match", "fullmatch", "findall", "finditer", "sub", "split",
                "compile", "escape", "IGNORECASE", "I", "MULTILINE", "M", "DOTALL", "S"),
    "json": _only(json, "dumps", "loads"),
    "collections": _only(collections, "Counter", "defaultdict", "OrderedDict", "namedtuple", "deque"),
    "itertools": _only(itertools, "chain", "groupby", "islice", "combinations", "permutations",
                       "product", "accumulate", "count"),
    "datetime": _Dt,
    "date": _datetime.date,
    "timedelta": _datetime.timedelta,
    "timezone": _datetime.timezone,
    "after": conditions.after,
    "before": conditions.before,
    "between": conditions.between,
    "now": conditions.now,
    "today": conditions.today,
}

AVAILABLE = (
    "Available without importing: math, statistics, re, json, collections, itertools (common "
    "functions of each), datetime, date, timedelta, timezone, and now() / today(). No files, processes, network or "
    f"imports. A run is stopped after {TIMEOUT_SECONDS} seconds."
)


class RunTimeout(BaseException):
    """BaseException, so host code can't swallow it with `except Exception`."""
    pass


@contextmanager
def time_limit(seconds: int = TIMEOUT_SECONDS):
    """Stop a run that takes too long. Works only on the main thread, where the server runs it."""
    def expire(signum, frame):
        raise RunTimeout(f"the run took longer than {seconds} seconds and was stopped")

    try:
        previous = signal.signal(signal.SIGALRM, expire)
    except ValueError:  # not the main thread: no timer available
        yield
        return
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
