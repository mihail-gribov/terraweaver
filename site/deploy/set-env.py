"""Put KEY=VALUE lines from stdin into /opt/terraweaver/.env on the demo machine, and make the two
secrets the machine owns (TERRAWEAVER_TOKEN, SESSION_SECRET) if they are empty. Prints only which
keys are set, never a value.

    scp site/deploy/set-env.py root@$SERVER:/opt/terraweaver/set-env.py
    grep -E '^(NEBIUS_API_KEY|TAVILY_API_KEY|OPENROUTER_API_KEY|GOOGLE_CLIENT_ID|GOOGLE_CLIENT_SECRET)=' .env \\
      | ssh root@$SERVER python3 /opt/terraweaver/set-env.py
"""
import os
import secrets
import shutil
import sys

PATH = "/opt/terraweaver/.env"
SHOWN = ["NEBIUS_API_KEY", "TAVILY_API_KEY", "OPENROUTER_API_KEY", "TERRAWEAVER_TOKEN",
         "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET"]

lines = open(PATH).read().splitlines()
have = {l.split("=", 1)[0]: l.split("=", 1)[1] for l in lines if "=" in l and not l.startswith("#")}
new = dict(l.split("=", 1) for l in sys.stdin.read().splitlines() if "=" in l and not l.startswith("#"))
for key, size in (("TERRAWEAVER_TOKEN", 24), ("SESSION_SECRET", 32)):
    if not have.get(key) and key not in new:
        new[key] = secrets.token_hex(size)

out, seen = [], set()
for l in lines:
    key = l.split("=", 1)[0]
    if key in new and not l.startswith("#"):
        out.append(f"{key}={new[key]}")
        seen.add(key)
    else:
        out.append(l)
out += [f"{k}={v}" for k, v in new.items() if k not in seen]
open(PATH, "w").write("\n".join(out) + "\n")
shutil.chown(PATH, "terraweaver", "terraweaver")
os.chmod(PATH, 0o600)
final = {l.split("=", 1)[0]: l.split("=", 1)[1] for l in out if "=" in l and not l.startswith("#")}
print({k: ("set" if final.get(k) else "EMPTY") for k in SHOWN})
