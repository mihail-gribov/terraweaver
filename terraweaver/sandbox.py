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


def check(code: str, protected: set[str] = frozenset()) -> ast.AST:
    """Parse and vet host code. Raises SandboxViolation, or SyntaxError for broken code.

    `protected` names can be read but not rebound — world variables change only via world.pin.
    """
    tree = ast.parse(code, "<run>")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in protected:
            raise SandboxViolation(
                f"'{node.id}' is a world variable; change it with world.pin({node.id}, value, "
                f"\"description\") or pick another name for a local variable"
            )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in protected:
            raise SandboxViolation(f"'{node.name}' is a world variable; pick another name")
        if isinstance(node, ast.arg) and node.arg in protected:
            raise SandboxViolation(f"'{node.arg}' is a world variable; pick another parameter name")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise SandboxViolation("imports aren't available: everything you can use is already in the namespace")
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
    "datetime": _datetime.datetime,
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
