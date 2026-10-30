"""Every test in one command: `.venv/bin/python tests/run_all.py`.

Each script here is its own runner with its own `check()` — deliberately, because a test that
needs no framework is a test anybody can read top to bottom. What was missing was something that
ran them all, so "the suite passes"
meant whatever the person typing it had remembered to type.

One process per script, so that no state of one leaks into another. A script fails if it exits
non-zero or prints a line beginning FAIL — some of them report failures and still exit 0.

    --only <text>   run the scripts whose name contains this
    -q              one line per script, nothing else
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAILED = re.compile(r"^FAIL", re.MULTILINE)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()

    scripts = [p for p in sorted(HERE.glob("test_*.py")) if args.only in p.name]
    if not scripts:
        print(f"no test script matches {args.only!r}")
        return 1
    bad = []
    started = time.monotonic()
    for script in scripts:
        began = time.monotonic()
        try:
            run = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                                 timeout=args.timeout, cwd=HERE.parent)
            out = run.stdout + run.stderr
            failures = len(FAILED.findall(out))
            wrong = run.returncode != 0 or failures
        except subprocess.TimeoutExpired:
            out, failures, wrong = f"timed out after {args.timeout:.0f}s", 0, True
        took = time.monotonic() - began
        print(f"{'FAIL' if wrong else 'ok  '}  {script.name:<28} {took:5.1f}s"
              + (f"  {failures} check(s) failed" if failures else ""))
        if wrong:
            bad.append(script.name)
            if not args.quiet:
                print("".join(f"      {line}\n" for line in out.splitlines()[-25:]))
    print(f"\n{len(scripts) - len(bad)} of {len(scripts)} scripts passed "
          f"in {time.monotonic() - started:.0f}s")
    if bad:
        print("failed: " + ", ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
