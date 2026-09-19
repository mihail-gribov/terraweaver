#!/usr/bin/env bash
# Run scenarios in world and baseline mode at once, one process (and one world server) each.
#
#   scripts/compare.sh                      # hard pool, default model
#   scripts/compare.sh --model haiku        # hard pool, Haiku as the host
#   scripts/compare.sh --model haiku s06 s13
#
# Uses ports 7010–7029 (two per scenario, at most ten scenarios at a time). Per-run logs go to
# var/compare/, results to experiments/results/scenarios/.
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
flags=(); names=()
while [ $# -gt 0 ]; do
  case "$1" in
    --model) flags+=(--model "$2"); shift 2 ;;
    *) names+=("$1"); shift ;;
  esac
done
if [ ${#names[@]} -eq 0 ]; then
  names=($(.venv/bin/python -c "
import importlib.util, glob
for f in sorted(glob.glob('scenarios/s*.py')):
    s = importlib.util.spec_from_file_location('m', f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    if getattr(m, 'LEVEL', 'basic') == 'hard': print(f.split('/')[-1].split('_')[0])"))
fi
logs="$root/var/compare"; mkdir -p "$logs"; rm -f "$logs"/*.log
port=7010
for name in "${names[@]}"; do
  .venv/bin/python scenarios/run.py "${flags[@]}" --port $port "$name" > "$logs/world-$name.log" 2>&1 &
  .venv/bin/python scenarios/run.py "${flags[@]}" --baseline --port $((port+1)) "$name" > "$logs/baseline-$name.log" 2>&1 &
  port=$((port+2))
done
wait
cat "$logs"/*.log | grep -E "^(PASS|FAIL)" | sort -k2,2 -k3,3
for mode in world baseline; do
  echo "$mode: $(cat "$logs"/$mode-*.log | grep -c '^PASS')/$(cat "$logs"/$mode-*.log | grep -cE '^(PASS|FAIL)') passed"
done
