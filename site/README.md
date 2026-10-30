# site

The website of TerraWeaver, served at https://terraweaver.life. Everything about the site lives in
this directory; the memory itself is the rest of the repository.

```
site/
  index.html          the landing page: one static file, no build step
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

The machine and its state are described in the private `HOSTING.md`. The page is copied to
`/var/www/terraweaver/` and Caddy serves it, sending `/mcp`, `/say`, `/ask` and the other memory
routes to `127.0.0.1:7110`:

```bash
rsync -av --delete -e "ssh -i ~/.ssh/terraweaver" site/index.html site/demo root@51.15.66.70:/var/www/terraweaver/
scp -i ~/.ssh/terraweaver site/deploy/Caddyfile root@51.15.66.70:/etc/caddy/Caddyfile
ssh -i ~/.ssh/terraweaver root@51.15.66.70 systemctl reload caddy
```

The private repository `terraweaver-web` held the first version of the page and the Caddyfile;
this directory supersedes it.

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
