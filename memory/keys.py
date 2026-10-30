"""Personal access keys for the demo instance: named keys per Google account, kept as hashes in one file.

The site's account service issues them (`site/auth/app.py`), the memory server only checks them
(`valid`), so the two share nothing but this file: TERRAWEAVER_KEYS, default var/keys.json. A key
is shown once, when it is made; what is kept is its SHA-256 and its first characters (to tell the
keys apart in a list), so the file leaks no working key.
"""
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

PREFIX = "tw_"
MAX_KEYS = 5
_lock = threading.Lock()
_cache: tuple[float, set[str]] = (0.0, set())


class Refused(Exception):
    """Something the account may not do (too many keys, an unknown key, a bad name)."""


def path() -> Path:
    return Path(os.environ.get("TERRAWEAVER_KEYS") or Path(__file__).resolve().parents[1] / "var" / "keys.json")


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load() -> dict:
    p = path()
    return json.loads(p.read_text()) if p.exists() else {}


def _save(users: dict) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.touch(mode=0o600)
    tmp.write_text(json.dumps(users, indent=1))
    tmp.replace(p)


def make(sub: str, email: str, name: str = "") -> tuple[str, dict]:
    """A new key for this account: the key itself (shown once) and its listing."""
    name = " ".join(name.split())[:40] or "Key"
    key = PREFIX + secrets.token_urlsafe(32)
    with _lock:
        users = _load()
        user = users.setdefault(sub, {"email": email, "created": int(time.time()), "keys": []})
        user["email"] = email
        if len(user["keys"]) >= MAX_KEYS:
            raise Refused(f"At most {MAX_KEYS} keys: revoke one first.")
        entry = {"id": secrets.token_hex(4), "name": name, "prefix": key[:len(PREFIX) + 4],
                 "hash": _hash(key), "created": int(time.time())}
        user["keys"].append(entry)
        _save(users)
    return key, _public(entry)


def _public(entry: dict) -> dict:
    return {k: entry[k] for k in ("id", "name", "prefix", "created")}


def account(sub: str) -> dict | None:
    """The account as the cabinet shows it: no hashes."""
    user = _load().get(sub)
    if user is None:
        return None
    return {"email": user["email"], "created": user["created"], "keys": [_public(k) for k in user["keys"]]}


def revoke(sub: str, key_id: str) -> None:
    with _lock:
        users = _load()
        user = users.get(sub)
        keys = [k for k in (user or {}).get("keys", []) if k["id"] != key_id]
        if user is None or len(keys) == len(user["keys"]):
            raise Refused("No such key.")
        user["keys"] = keys
        _save(users)


def delete_account(sub: str) -> None:
    """The account and every key of it."""
    with _lock:
        users = _load()
        users.pop(sub, None)
        _save(users)


def valid(key: str) -> bool:
    """Is this a key that was made and not revoked? The file is re-read when it changes."""
    global _cache
    p = path()
    try:
        mtime = p.stat().st_mtime
    except FileNotFoundError:
        return False
    if mtime != _cache[0]:
        _cache = (mtime, {k["hash"] for u in _load().values() for k in u["keys"]})
    return _hash(key) in _cache[1]
