"""The account service: sign in with Google, the cabinet's JSON API, keys for the demo memory.

    GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… SESSION_SECRET=… \\
        .venv/bin/python site/auth/app.py            # 127.0.0.1:7120, behind Caddy

Caddy sends /auth/* here (site/deploy/Caddyfile); the cabinet itself is the static page /account/.
The Google client's redirect URI is BASE_URL/auth/callback (default https://terraweaver.life).
The first sign-in is the registration: the account is made when the first key is. A key is shown
once, when it is made (memory/keys.py).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memory import keys  # noqa: E402

BASE_URL = os.environ.get("BASE_URL", "https://terraweaver.life").rstrip("/")
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SECRET = (os.environ.get("SESSION_SECRET") or "").encode()
SESSION_DAYS = 7
SECURE = BASE_URL.startswith("https")
CABINET = f"{BASE_URL}/account/"


def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    mac = hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _unsign(value: str | None) -> dict | None:
    if not value or "." not in value:
        return None
    body, _, mac = value.rpartition(".")
    if not hmac.compare_digest(mac, hmac.new(SECRET, body.encode(), hashlib.sha256).hexdigest()):
        return None
    payload = json.loads(base64.urlsafe_b64decode(body))
    return payload if payload.get("exp", 0) > time.time() else None


def _cookie(response, name: str, value: str, max_age: int) -> None:
    response.set_cookie(name, value, max_age=max_age, httponly=True, secure=SECURE, samesite="lax", path="/auth")


def _error(title: str, text: str, status: int) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>TerraWeaver</title>
<link rel="stylesheet" href="/style.css"></head><body><main class="doc"><h1>{title}</h1><p>{text}</p>
<p><a href="/account/">Back to the account</a></p></main></body></html>""", status_code=status)


async def login(request: Request):
    if not CLIENT_ID:
        return _error("Sign-in is not set up", "GOOGLE_CLIENT_ID is missing on the server.", 503)
    state = secrets.token_urlsafe(24)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": CLIENT_ID, "redirect_uri": f"{BASE_URL}/auth/callback", "response_type": "code",
        "scope": "openid email", "state": state, "prompt": "select_account"})
    response = RedirectResponse(url)
    _cookie(response, "tw_state", _sign({"state": state, "exp": time.time() + 600}), 600)
    return response


async def callback(request: Request):
    saved = _unsign(request.cookies.get("tw_state"))
    if not saved or not hmac.compare_digest(saved["state"], request.query_params.get("state", "")):
        return _error("Sign-in expired", "Please try again.", 400)
    if "code" not in request.query_params:
        return _error("Sign-in cancelled", "Nothing was changed.", 400)
    async with httpx.AsyncClient(timeout=15) as client:
        token = await client.post("https://oauth2.googleapis.com/token", data={
            "code": request.query_params["code"], "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "redirect_uri": f"{BASE_URL}/auth/callback", "grant_type": "authorization_code"})
        if token.status_code != 200:
            return _error("Google refused the sign-in", "Please try again.", 502)
        who = await client.get("https://openidconnect.googleapis.com/v1/userinfo",
                               headers={"Authorization": f"Bearer {token.json()['access_token']}"})
    user = who.json()
    if who.status_code != 200 or not user.get("email_verified"):
        return _error("Google account not verified", "Use an account with a verified email.", 403)
    response = RedirectResponse(CABINET, status_code=303)
    _cookie(response, "tw_session", _sign({"sub": user["sub"], "email": user["email"],
                                           "exp": time.time() + SESSION_DAYS * 86400}), SESSION_DAYS * 86400)
    _cookie(response, "tw_state", "", 0)
    return response


def _session(request: Request) -> dict | None:
    return _unsign(request.cookies.get("tw_session"))


def _json(data: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status, headers={"Cache-Control": "no-store"})


def _same_site(request: Request) -> bool:
    """A page of another site must not be able to make or revoke keys."""
    origin = request.headers.get("origin")
    return not origin or origin == BASE_URL


async def me(request: Request):
    session = _session(request)
    if not session:
        return _json({"error": "signed out"}, 401)
    mine = keys.account(session["sub"]) or {"email": session["email"], "created": None, "keys": []}
    return _json({**mine, "email": session["email"], "max_keys": keys.MAX_KEYS, "endpoint": f"{BASE_URL}/mcp"})


async def make_key(request: Request):
    session = _session(request)
    if not session:
        return _json({"error": "signed out"}, 401)
    if not _same_site(request):
        return _json({"error": "refused"}, 403)
    try:
        name = str((await request.json()).get("name", ""))
    except ValueError:
        name = ""
    try:
        key, entry = keys.make(session["sub"], session["email"], name)
    except keys.Refused as e:
        return _json({"error": str(e)}, 409)
    return _json({"key": key, "entry": entry})


async def revoke_key(request: Request):
    session = _session(request)
    if not session:
        return _json({"error": "signed out"}, 401)
    if not _same_site(request):
        return _json({"error": "refused"}, 403)
    try:
        keys.revoke(session["sub"], request.path_params["key_id"])
    except keys.Refused as e:
        return _json({"error": str(e)}, 404)
    return _json({"ok": True})


async def delete_account(request: Request):
    session = _session(request)
    if not session:
        return _json({"error": "signed out"}, 401)
    if not _same_site(request):
        return _json({"error": "refused"}, 403)
    keys.delete_account(session["sub"])
    response = _json({"ok": True})
    _cookie(response, "tw_session", "", 0)
    return response


async def logout(request: Request):
    response = _json({"ok": True})
    _cookie(response, "tw_session", "", 0)
    return response


async def old_account(request: Request):
    return RedirectResponse(CABINET)


app = Starlette(routes=[
    Route("/auth/login", login),
    Route("/auth/callback", callback),
    Route("/auth/account", old_account),
    Route("/auth/api/me", me),
    Route("/auth/api/keys", make_key, methods=["POST"]),
    Route("/auth/api/keys/{key_id}", revoke_key, methods=["DELETE"]),
    Route("/auth/api/account", delete_account, methods=["DELETE"]),
    Route("/auth/api/logout", logout, methods=["POST"]),
])

if __name__ == "__main__":
    if len(SECRET) < 16:
        raise SystemExit("SESSION_SECRET is not set (at least 16 characters): "
                         "python -c 'import secrets; print(secrets.token_hex(32))'")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("AUTH_PORT", "7120")))
