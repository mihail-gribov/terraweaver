"""The account behind the site: named keys per Google account (memory/keys.py) and the cabinet's
JSON API (site/auth/app.py). No Google call is made: the session cookie is signed here."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "site" / "auth"))
_dir = tempfile.mkdtemp()
os.environ.update(TERRAWEAVER_KEYS=_dir + "/keys.json", SESSION_SECRET="x" * 32, GOOGLE_CLIENT_ID="cid",
                  BASE_URL="http://testserver")

from starlette.testclient import TestClient  # noqa: E402

import app as site  # noqa: E402
from memory import journal, keys  # noqa: E402


def signed_in(sub="1", email="a@example.com") -> TestClient:
    client = TestClient(site.app, follow_redirects=False)
    client.cookies.set("tw_session", site._sign({"sub": sub, "email": email, "exp": 9e9}), path="/auth")
    return client


def test_a_key_works_until_it_is_revoked():
    key, entry = keys.make("k1", "a@example.com", "laptop")
    assert keys.valid(key) and not keys.valid(key + "x") and not keys.valid("tw_nope")
    assert entry["name"] == "laptop" and key.startswith(entry["prefix"])
    assert "hash" not in entry and "hash" not in str(keys.account("k1"))
    keys.revoke("k1", entry["id"])
    assert not keys.valid(key)


def test_one_account_holds_a_few_keys_and_deleting_it_takes_them_all():
    made = [keys.make("k2", "b@example.com", f"key {i}")[0] for i in range(keys.MAX_KEYS)]
    try:
        keys.make("k2", "b@example.com", "one too many")
        raise AssertionError("the limit was not enforced")
    except keys.Refused:
        pass
    assert all(keys.valid(k) for k in made)
    keys.delete_account("k2")
    assert not any(keys.valid(k) for k in made) and keys.account("k2") is None


def test_the_cabinet_api_needs_a_session():
    client = TestClient(site.app, follow_redirects=False)
    assert client.get("/auth/api/me").status_code == 401
    assert client.post("/auth/api/keys", json={}).status_code == 401
    assert client.delete("/auth/api/keys/abc").status_code == 401
    assert client.get("/auth/login").status_code == 307


def test_the_cabinet_makes_lists_and_revokes_keys():
    client = signed_in("c1")
    assert client.get("/auth/api/me").json()["keys"] == []
    made = client.post("/auth/api/keys", json={"name": "Claude Code"}).json()
    assert keys.valid(made["key"])
    listed = client.get("/auth/api/me").json()
    assert [k["name"] for k in listed["keys"]] == ["Claude Code"] and made["key"] not in str(listed)
    assert client.delete("/auth/api/keys/" + made["entry"]["id"]).status_code == 200
    assert not keys.valid(made["key"])
    assert client.delete("/auth/api/keys/nope").status_code == 404
    # and the key works as the memory's bearer token
    again = client.post("/auth/api/keys", json={}).json()["key"]
    assert journal._issued(f"Bearer {again}".encode()) and not journal._issued(b"Bearer tw_x")


def test_a_page_of_another_site_cannot_touch_the_keys():
    client = signed_in("c2")
    assert client.post("/auth/api/keys", json={}, headers={"origin": "http://evil"}).status_code == 403
    assert client.delete("/auth/api/account", headers={"origin": "http://evil"}).status_code == 403


def test_deleting_the_account_takes_its_keys():
    client = signed_in("c3")
    key = client.post("/auth/api/keys", json={}).json()["key"]
    assert client.delete("/auth/api/account").status_code == 200
    assert not keys.valid(key)


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
