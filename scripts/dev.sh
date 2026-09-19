#!/usr/bin/env bash
# Start, stop and check the development services.
#
#   scripts/dev.sh start     world server on the LAN (7000) + MCP Inspector (7001, sandbox 7002)
#   scripts/dev.sh stop
#   scripts/dev.sh status
#   scripts/dev.sh logs      follow both logs
#
# Logs and pid files live in var/. The world database is worlds/job_search.db; it is built from
# the job_search fixture when empty (add REBUILD=1 to rebuild it on start).
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
var="$root/var"; mkdir -p "$var"
lan="${LAN_IP:-$(ip -4 route get 192.0.2.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')}"
world_port=7000; inspector_port=7001; sandbox_port=7002

running() { [ -f "$var/$1.pid" ] && kill -0 "$(cat "$var/$1.pid")" 2>/dev/null; }

start_world() {
  if running world; then echo "world: already running (pid $(cat "$var/world.pid"))"; return; fi
  rebuild=(); [ "${REBUILD:-0}" = 1 ] && rebuild=(--rebuild)
  nohup .venv/bin/python -m terraweaver.server --host 0.0.0.0 --port $world_port \
    --allow-origin "http://$lan:$inspector_port" "${rebuild[@]}" > "$var/world.log" 2>&1 &
  echo $! > "$var/world.pid"
  for _ in $(seq 40); do curl -s "http://127.0.0.1:$world_port/health" >/dev/null && break; sleep 0.25; done
  echo "world: http://$lan:$world_port/mcp  (token in .terraweaver-token)"
}

start_inspector() {
  if running inspector; then echo "inspector: already running (pid $(cat "$var/inspector.pid"))"; return; fi
  command -v mcp-inspector >/dev/null || { echo "inspector: not installed (npm install -g @modelcontextprotocol/inspector)"; return; }
  "$root/scripts/patch-inspector.sh" >/dev/null
  HOST="$lan" CLIENT_PORT=$inspector_port MCP_SANDBOX_PORT=$sandbox_port \
  ALLOWED_ORIGINS="http://$lan:$inspector_port" MCP_AUTO_OPEN_ENABLED=false \
  nohup mcp-inspector --web --transport http --server-url "http://$lan:$world_port/mcp" \
    --header "Authorization: Bearer $(cat .terraweaver-token)" "x-terraweaver-session: inspector" \
    > "$var/inspector.log" 2>&1 &
  echo $! > "$var/inspector.pid"
  for _ in $(seq 40); do grep -q "Auth token" "$var/inspector.log" 2>/dev/null && break; sleep 0.25; done
  grep -o "http://$lan:$inspector_port?MCP_INSPECTOR_API_TOKEN=[0-9a-f]*" "$var/inspector.log" | head -1 | sed 's/^/inspector: /'
}

stop_one() {
  if running "$1"; then
    pid="$(cat "$var/$1.pid")"; pkill -P "$pid" 2>/dev/null || true; kill "$pid" 2>/dev/null || true
    echo "$1: stopped"
  else
    echo "$1: not running"
  fi
  rm -f "$var/$1.pid"
}

case "${1:-status}" in
  start)  start_world; start_inspector ;;
  stop)   stop_one inspector; stop_one world ;;
  status) for s in world inspector; do running $s && echo "$s: running (pid $(cat "$var/$s.pid"))" || echo "$s: stopped"; done
          curl -s "http://127.0.0.1:$world_port/health" && echo ;;
  logs)   tail -f "$var/world.log" "$var/inspector.log" ;;
  *)      echo "usage: $0 start|stop|status|logs" >&2; exit 2 ;;
esac
