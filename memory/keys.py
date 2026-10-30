"""Personal access keys for the demo instance: one per Google account, kept as hashes in one file.

The site's sign-in service issues them (`site/auth/app.py`), the memory server only checks them
(`valid`), so the two share nothing but this file: TERRAWEAVER_KEYS, default var/keys.json. A key
is shown once, when it is issued; what is kept is its SHA-256, so the file leaks no working key.
"""
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

PREFIX = "tw_"
_lock = threading.Lock()
_cache: tuple[float, set[str]] = (0.0, set())


def path() -> Path:
    return Path(os.environ.get("TERRAWEAVER_KEYS") or Path(__file__).resolve().parents[1] / "var" / "keys.json")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load() -> dict:
    p = path()
    return json.loads(p.read_text()) if p.exists() else {}


def issue(sub: str, email: str) -> str:
    """A new key for this account; the one it had before stops working."""
    key = PREFIX + secrets.token_urlsafe(32)
    with _lock:
        users = _load()
        users[sub] = {"email": email, "hash": _hash(key), "issued": int(time.time())}
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.touch(mode=0o600)
        tmp.write_text(json.dumps(users, indent=1))
        tmp.replace(p)
    return key


def info(sub: str) -> dict | None:
    """When this account's key was issued (the key itself is not kept)."""
    return _load().get(sub)


def valid(key: str) -> bool:
    """Is this a key that was issued? The file is re-read when it changes."""
    global _cache
    p = path()
    try:
        mtime = p.stat().st_mtime
    except FileNotFoundError:
        return False
    if mtime != _cache[0]:
        _cache = (mtime, {u["hash"] for u in _load().values()})
    return _hash(key) in _cache[1]
