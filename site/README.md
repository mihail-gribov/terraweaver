# site

The website of TerraWeaver, served at https://terraweaver.life. Everything about the site lives in
this directory; the memory itself is the rest of the repository.

```
site/
  index.html          the landing page; privacy.html, style.css, robots.txt, sitemap.xml beside it
  demo/               replays of two real runs, generated (see below)
  auth/app.py         sign in with Google, issue a key (Starlette, 127.0.0.1:7120)
  deploy/Caddyfile    the web server config of the demo machine
  NOTES.md            content plan, decisions and open work for the site
```

## Preview

```bash
python3 -m http.server 8000 --directory site     # http://localhost:8000
```

## Rebuild the replays

The replays are single self-contained pages made by `scripts/replay.py` from the runs in
`benchmarks/runs/`:

```bash
.venv/bin/python scripts/replay.py benchmarks/runs/demo-recall-birthday-20261030-035627 --out site/demo/birthday.html
.venv/bin/python scripts/replay.py benchmarks/runs/demo-recall-home-20261030-035627 --out site/demo/home.html
```

## Deploy

The page is copied to the web root of the demo machine (`/var/www/terraweaver/`) and Caddy serves
it, sending `/mcp`, `/say`, `/ask` and the other memory routes to `127.0.0.1:7110` and `/auth/*` to
the sign-in service on `127.0.0.1:7120`. The machine, its address and the exact commands are not in
this repository.

```bash
rsync -a --delete site/index.html site/privacy.html site/style.css site/robots.txt site/sitemap.xml site/demo site/account "$SERVER":/var/www/terraweaver/
scp site/deploy/Caddyfile "$SERVER":/tmp/Caddyfile.new       # then: caddy validate, copy to /etc/caddy, reload
bash -s < site/deploy/prepare-server.sh                       # once, on the machine, as root
sh /opt/terraweaver/deploy.sh                                 # on the machine: the pushed main, then restart
```

## Sign-in and keys

`site/auth/app.py` signs a visitor in with Google and issues one key per account (`tw_…`, shown once,
kept as a SHA-256 in `var/keys.json` by `memory/keys.py`). The memory server accepts those keys
beside its own `TERRAWEAVER_TOKEN`; all keys open the same shared demo world.

Google Cloud Console: an OAuth client of type *Web application*, redirect URI
`https://terraweaver.life/auth/callback`. Then, on the machine:

```bash
GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… SESSION_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))') \
  .venv/bin/python site/auth/app.py
```

Both services need the same `TERRAWEAVER_KEYS` path if it is not the default `var/keys.json`.
