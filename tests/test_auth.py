"""The server behind a token: with TERRAWEAVER_TOKEN set, even bound to localhost behind a proxy,
every request — /mcp and every route of the memory — needs the token, and the proxy's host name
is accepted. Without a token or keys, on localhost, it stays open to localhost only."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["NEBIUS_API_KEY"] = os.environ.get("NEBIUS_API_KEY") or "test"

from starlette.testclient import TestClient  # noqa: E402

from memory import journal, server  # noqa: E402,F401 - server registers the memory's routes

ROUTES = [("POST", "/mcp"), ("POST", "/say"), ("POST", "/ask"), ("GET", "/world"), ("GET", "/notes")]


def test_a_token_guards_every_route_on_localhost_too():
    with tempfile.TemporaryDirectory() as d:
        journal.facts = Path(d) / "facts.md"
        os.environ["TERRAWEAVER_TOKEN"] = "secret-token"
        try:
            app, how = journal.app_for(7110, "127.0.0.1")
        finally:
            del os.environ["TERRAWEAVER_TOKEN"]
        assert "bearer" in how
        with TestClient(app, base_url="https://terraweaver.life") as client:
            for method, route in ROUTES:
                got = client.request(method, route, json={})
                assert got.status_code == 401, (route, got.status_code)
            ok = client.get("/world", headers={"Authorization": "Bearer secret-token"})
            assert ok.status_code == 200, ok.status_code
            # The proxy's host name passes: no 421 from the host check, the token is the guard.
            mcp = client.post("/mcp", json={}, headers={"Authorization": "Bearer secret-token"})
            assert mcp.status_code not in (401, 421), mcp.status_code


def test_without_a_token_localhost_is_open_to_localhost_only():
    with tempfile.TemporaryDirectory() as d:
        journal.facts = Path(d) / "facts.md"
        os.environ["TERRAWEAVER_KEYS"] = str(Path(d) / "none.json")
        try:
            os.environ.pop("TERRAWEAVER_KEYS")
            from memory import keys
            if keys.path().exists():
                print("skip: keys issued on this machine, so localhost is guarded")
                return
            app, how = journal.app_for(7110, "127.0.0.1")
        finally:
            os.environ.pop("TERRAWEAVER_KEYS", None)
        assert how == "localhost only"
        with TestClient(app, base_url="http://127.0.0.1:7110") as client:
            assert client.get("/world").status_code == 200


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            print("ok", name)
