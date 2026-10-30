#!/bin/bash
# One-time preparation of the demo machine, run as root on it:
#   ssh root@$SERVER 'bash -s' < site/deploy/prepare-server.sh
# Installs uv, makes the terraweaver user, /opt/terraweaver, an empty .env, the two systemd units
# (not started: there is no code and no keys yet) and /opt/terraweaver/deploy.sh.
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q python3-venv python3-pip >/dev/null
python3 -m venv /opt/uv-venv && /opt/uv-venv/bin/pip install -q uv && ln -sf /opt/uv-venv/bin/uv /usr/local/bin/uv
id terraweaver >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/terraweaver --shell /usr/sbin/nologin terraweaver
install -d -o terraweaver -g terraweaver /opt/terraweaver/data
if [ ! -f /opt/terraweaver/.env ]; then
cat > /opt/terraweaver/.env <<'ENV'
# Fill in the values yourself; nothing here is committed anywhere.
NEBIUS_API_KEY=
TAVILY_API_KEY=
OPENROUTER_API_KEY=
TERRAWEAVER_EMBEDDINGS=openrouter
TERRAWEAVER_TOKEN=
TERRAWEAVER_KEYS=/opt/terraweaver/data/keys.json
# Sign in with Google (site/auth/app.py)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SESSION_SECRET=
BASE_URL=https://terraweaver.life
ENV
fi
chown terraweaver:terraweaver /opt/terraweaver/.env
chmod 600 /opt/terraweaver/.env

cat > /etc/systemd/system/terraweaver-memory.service <<'U'
[Unit]
Description=TerraWeaver memory (MCP)
After=network-online.target
Wants=network-online.target

[Service]
User=terraweaver
WorkingDirectory=/opt/terraweaver/app
EnvironmentFile=/opt/terraweaver/.env
ExecStart=/opt/terraweaver/app/.venv/bin/python -m memory.server --host 0.0.0.0 --port 7110
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
U

cat > /etc/systemd/system/terraweaver-auth.service <<'U'
[Unit]
Description=TerraWeaver sign-in and keys
After=network-online.target

[Service]
User=terraweaver
WorkingDirectory=/opt/terraweaver/app
EnvironmentFile=/opt/terraweaver/.env
ExecStart=/opt/terraweaver/app/.venv/bin/python site/auth/app.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
U

cat > /opt/terraweaver/deploy.sh <<'D'
#!/bin/sh
# Deploy a pushed ref (default main): sh /opt/terraweaver/deploy.sh [ref]   (as root)
set -e
ref=${1:-main}
app=/opt/terraweaver/app
[ -d $app/.git ] || git clone -q https://github.com/mihail-gribov/terraweaver $app
cd $app
git fetch -q origin
git checkout -q "$ref"
git reset -q --hard "origin/$ref"
[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install -q --python .venv/bin/python mcp openai
chown -R terraweaver:terraweaver /opt/terraweaver/app
rsync -a --delete site/index.html site/privacy.html site/style.css site/robots.txt site/sitemap.xml site/demo site/account /var/www/terraweaver/
systemctl daemon-reload
systemctl restart terraweaver-memory terraweaver-auth
git log --oneline -1
D
chmod 755 /opt/terraweaver/deploy.sh
systemctl daemon-reload
uv --version
systemctl list-unit-files | grep terraweaver
