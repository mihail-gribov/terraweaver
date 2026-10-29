#!/usr/bin/env bash
# Re-apply the local patch to the globally installed MCP Inspector web UI.
#
# Opened over plain http from another machine, the browser gives the page no crypto.randomUUID
# (it exists only on HTTPS or localhost) and the Inspector fails with "crypto.randomUUID is not a
# function". The patch adds a small polyfill script to its index.html. `npm install -g` of a new
# Inspector version drops it — run this again afterwards.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
dist="$(npm root -g)/@modelcontextprotocol/inspector/clients/web/dist"
[ -f "$dist/index.html" ] || { echo "MCP Inspector not installed: npm install -g @modelcontextprotocol/inspector" >&2; exit 1; }
cp "$here/scripts/inspector-uuid-polyfill.js" "$dist/assets/uuid-polyfill.js"
[ -f "$dist/index.html.orig" ] || cp "$dist/index.html" "$dist/index.html.orig"
if ! grep -q uuid-polyfill "$dist/index.html"; then
  sed -i 's#    <title>MCP Inspector</title>#    <title>MCP Inspector</title>\n    <script src="/assets/uuid-polyfill.js"></script>#' "$dist/index.html"
fi
echo "Inspector patched: $dist/index.html"
