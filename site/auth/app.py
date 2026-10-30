"""Sign in with Google, get a key for the demo memory.

    GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… SESSION_SECRET=… \\
        .venv/bin/python site/auth/app.py            # 127.0.0.1:7120, behind Caddy

Caddy sends /auth/* here (site/deploy/Caddyfile). The Google client's redirect URI is
BASE_URL/auth/callback (default https://terraweaver.life). The key is shown once, at issue; asking
for a new one retires the old (memory/keys.py).
"""
import base64
import hashlib
import hmac
import html
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
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from memory import keys  # noqa: E402

BASE_URL = os.environ.get("BASE_URL", "https://terraweaver.life").rstrip("/")
CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
SECRET = (os.environ.get("SESSION_SECRET") or "").encode()
SESSION_DAYS = 7
SECURE = BASE_URL.startswith("https")


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


def _page(body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>TerraWeaver key</title>
<style>:root{{--bg:#fbfaf7;--fg:#1c1b19;--muted:#6b675f;--accent:#2f6f5e;--line:#e2dfd6}}
@media(prefers-color-scheme:dark){{:root{{--bg:#161513;--fg:#ecebe6;--muted:#a09b90;--accent:#7fc4ae;--line:#33312c}}}}
body{{background:var(--bg);color:var(--fg);font:17px/1.6 system-ui,sans-serif;margin:0}}
main{{max-width:40rem;margin:0 auto;padding:3rem 16px}} a{{color:var(--accent)}}
code,pre{{background:var(--line);border-radius:6px;padding:.15em .4em;font-size:.9em}}
pre{{padding:.8rem 1rem;overflow-x:auto}} .key{{font-size:1rem;word-break:break-all}}
.btn{{display:inline-block;background:var(--accent);color:var(--bg);text-decoration:none;padding:.55rem 1.1rem;
border-radius:8px;font:600 1rem system-ui;border:0;cursor:pointer}} .muted{{color:var(--muted)}}</style></head>
<body><main>{body}</main></body></html>""", status_code=status)


async def login(request: Request):
    if not CLIENT_ID:
        return _page("<h1>Sign-in is not set up</h1><p>GOOGLE_CLIENT_ID is missing on the server.</p>", 503)
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
        return _page("<h1>Sign-in expired</h1><p><a href=\"/auth/login\">Try again</a></p>", 400)
    if "code" not in request.query_params:
        return _page("<h1>Sign-in cancelled</h1><p><a href=\"/\">Back to the site</a></p>", 400)
    async with httpx.AsyncClient(timeout=15) as client:
        token = await client.post("https://oauth2.googleapis.com/token", data={
            "code": request.query_params["code"], "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "redirect_uri": f"{BASE_URL}/auth/callback", "grant_type": "authorization_code"})
        if token.status_code != 200:
            return _page("<h1>Google refused the sign-in</h1><p><a href=\"/auth/login\">Try again</a></p>", 502)
        who = await client.get("https://openidconnect.googleapis.com/v1/userinfo",
                               headers={"Authorization": f"Bearer {token.json()['access_token']}"})
    user = who.json()
    if who.status_code != 200 or not user.get("email_verified"):
        return _page("<h1>Google account not verified</h1><p>Use an account with a verified email.</p>", 403)
    response = RedirectResponse(f"{BASE_URL}/auth/account", status_code=303)
    _cookie(response, "tw_session", _sign({"sub": user["sub"], "email": user["email"],
                                           "exp": time.time() + SESSION_DAYS * 86400}), SESSION_DAYS * 86400)
    _cookie(response, "tw_state", "", 0)
    return response


async def account(request: Request):
    session = _unsign(request.cookies.get("tw_session"))
    if not session:
        return RedirectResponse(f"{BASE_URL}/auth/login")
    email = html.escape(session["email"])
    have = keys.info(session["sub"])
    status = (f"<p class=\"muted\">A key was issued to this account on "
              f"{time.strftime('%Y-%m-%d', time.gmtime(have['issued']))}. It is not kept anywhere in clear: "
              f"if you lost it, make a new one (the old one stops working).</p>") if have else \
        "<p class=\"muted\">No key yet.</p>"
    return _page(f"""<h1>Your key</h1><p>Signed in as <strong>{email}</strong>.</p>{status}
<form method="post" action="/auth/key"><button class="btn" type="submit">{'Make a new key' if have else 'Get a key'}</button></form>
<p class="muted"><a href="/auth/logout">Sign out</a> · <a href="/">Back to the site</a></p>""")


async def make_key(request: Request):
    session = _unsign(request.cookies.get("tw_session"))
    if not session:
        return RedirectResponse(f"{BASE_URL}/auth/login", status_code=303)
    # A form from another site must not be able to retire the key.
    origin = request.headers.get("origin")
    if origin and origin != BASE_URL:
        return _page("<h1>Refused</h1>", 403)
    key = keys.issue(session["sub"], session["email"])
    response = _page(f"""<h1>Your key</h1><p>Shown once. Copy it now.</p>
<pre class="key">{key}</pre>
<p>Use it as the bearer token of the memory:</p>
<pre>export PERSONAL_MEMORY_URL=https://terraweaver.life
export PERSONAL_MEMORY_TOKEN={key}</pre>
<p>Or in an MCP client: <code>https://terraweaver.life/mcp</code> with the header
<code>Authorization: Bearer {key}</code>.</p>
<p class="muted">This is a shared demo for evaluation: do not enter personal data.</p>
<p><a href="/auth/account">Back</a></p>""")
    response.headers["Cache-Control"] = "no-store"
    return response


async def logout(request: Request):
    response = RedirectResponse(f"{BASE_URL}/", status_code=303)
    _cookie(response, "tw_session", "", 0)
    return response


app = Starlette(routes=[
    Route("/auth/login", login),
    Route("/auth/callback", callback),
    Route("/auth/account", account),
    Route("/auth/key", make_key, methods=["POST"]),
    Route("/auth/logout", logout),
])

if __name__ == "__main__":
    if len(SECRET) < 16:
        raise SystemExit("SESSION_SECRET is not set (at least 16 characters): python -c 'import secrets; print(secrets.token_hex(32))'")
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("AUTH_PORT", "7120")))
