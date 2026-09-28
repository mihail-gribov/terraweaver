#!/usr/bin/env bash
# Run a measurement so that it survives: as a transient systemd service, with its log on disk.
#
#   scripts/measure.sh gate            25 facts, the reading, 3 questions — the cheap gate first
#   scripts/measure.sh full            455 facts, the reading, 100 questions — the number
#   scripts/measure.sh read <dir>      the reading alone, over a world that is already written
#   scripts/measure.sh ask <dir> [n]   the questions alone, over a world that is already read
#   scripts/measure.sh status          what is running, where its log is, what it has done
#   scripts/measure.sh stop            stop whatever is running
#
# <dir> is a world kept by --keep: it holds world.db and grown/ side by side.
#
# **Why a service and not `&` or `nohup`.** Measured 2026-09-28, three times: a run started with
# `&`, with `nohup`, or even with `systemd-run --scope` stays in the calling shell's process group
# and is killed with it — every one of them died around the thirty-minute mark with nothing in its
# log to say why, twice after the write phase had already been paid for. A transient service
# (`systemd-run --user --unit=…`, no `--scope`) is owned by systemd and outlives the shell.
#
# **Why the phases are separate.** The write phase costs money and the reading costs time, and the
# reading is resumable — every reading is marked, so the queue only shrinks. So a crash in the
# reading never means paying for the writing again: `read` picks up where it stopped.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
python="$root/.venv/bin/python"
logs="$root/var"
mkdir -p "$logs"

# One place to change the model, the slice and how many facts a recording turn is given.
model="${MODEL:-haiku}"
hops="${HOPS:-sh}"
context="${CONTEXT:-6k}"
chunk="${CHUNK:-25}"

serve() {                                    # serve <unit> <log> <command…>
  local unit="$1" log="$2"; shift 2
  systemctl --user reset-failed "$unit.service" 2>/dev/null || true
  if systemctl --user is-active --quiet "$unit.service"; then
    echo "$unit: already running — scripts/measure.sh status" >&2
    exit 1
  fi
  systemd-run --user --unit="$unit" --collect \
    --working-directory="$root" \
    --property=StandardOutput=append:"$log" \
    --property=StandardError=append:"$log" \
    "$@" >/dev/null
  echo "$unit: running.  log: $log"
  echo "         follow it with: tail -f $log"
}

case "${1:-status}" in

gate)
  # The cheap gate, and it earns its place: of the failures found on 2026-09-28, every one showed
  # itself in the first batch or in the first reading — a batch of 5 turns where the others took 20,
  # a reading that typed nothing, a host with no tools at all. None of them needed 455 facts to see.
  # No questions: the hundred are about the whole slice, so a question drawn for a gate of 25 facts
  # asks about a fact nobody wrote and the world rightly answers "not recorded". Measured — the gate
  # scored 0/3 and it meant nothing. What a gate is judged on is `check_expected.py`, which reads the
  # world against what each fact owed: per fact, no model, free, and it names the ones that failed.
  rm -rf "$root/var/gate" "$logs/gate.log"
  serve tw-gate "$logs/gate.log" \
    "$python" -u benchmarks/run_fc.py --hops "$hops" --context "$context" --model "$model" \
    --chunk "$chunk" --facts 25 --questions 0 --keep var/gate --port 7074
  echo "         when it is done: $python experiments/check_expected.py var/gate --upto 25 --by 5"
  ;;

full)
  where="${2:-var/fc455}"
  rm -rf "$root/$where" "$logs/full.log"
  mkdir -p "$root/$where"
  serve tw-full "$logs/full.log" \
    "$python" -u benchmarks/run_fc.py --hops "$hops" --context "$context" --model "$model" \
    --chunk "$chunk" --questions 100 --keep "$where/world" --port 7075
  ;;

read)
  world="${2:?say which world: scripts/measure.sh read var/fc455/world}"
  serve tw-read "$logs/read.log" \
    "$python" -u experiments/catch_up.py "$world/world.db" --grown "$world/grown" --limit 500
  ;;

ask)
  world="${2:?say which world: scripts/measure.sh ask var/fc455/world [100]}"
  many="${3:-100}"
  serve tw-ask "$logs/ask.log" \
    "$python" -u benchmarks/reask.py --db "$world/world.db" --questions "$many" \
    --hops "$hops" --context "$context" --model "$model" --port 7076 \
    --label "$(basename "$(dirname "$world")")"
  ;;

direction)
  # Which way round, put to every picker that can be reached, in the words the world itself uses.
  # Reads and asks; writes nothing. See experiments/02_link_direction/README.md for what it settles.
  world="${2:?say which world: scripts/measure.sh direction var/gate-noread}"
  many="${3:-60}"
  rm -f "$logs/direction.log"
  serve tw-direction "$logs/direction.log" \
    "$python" -u experiments/02_link_direction/run.py "$world" --limit "$many"
  ;;

status)
  for unit in tw-gate tw-full tw-read tw-ask; do
    state="$(systemctl --user is-active "$unit.service" 2>/dev/null || true)"
    printf '%-9s %s\n' "$unit" "${state:-inactive}"
  done
  echo
  for log in "$logs"/gate.log "$logs"/full.log "$logs"/read.log "$logs"/ask.log; do
    [ -s "$log" ] || continue
    echo "--- $(basename "$log") (last lines)"
    tail -4 "$log" | sed 's/^/    /'
  done
  # What the world itself says, which is the part no log can be wrong about.
  for world in "$root"/var/*/world "$root"/var/gate; do
    [ -f "$world/world.db" ] || continue
    echo "--- $world"
    "$python" - "$world" <<'PY' | sed 's/^/    /'
import sys
from pathlib import Path
sys.path.insert(0, ".")                      # run from the repository root, as the service is
from terraweaver import open_world, portraits, sentences
from terraweaver.formalise import record
where = Path(sys.argv[1])
rt = open_world(str(where / "world.db"), home=where)
said, waiting = sentences.count(rt.world)
asked, unread = portraits.count(rt.world)
print(f"{said} said in words, {waiting} still unread; {asked} bare names, {unread} unread")
print(record.readable(record.distribution(rt.world)))
PY
  done
  ;;

stop)
  for unit in tw-gate tw-full tw-read tw-ask; do
    systemctl --user is-active --quiet "$unit.service" && systemctl --user stop "$unit.service" \
      && echo "$unit: stopped" || true
  done
  ;;

*)
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
  ;;
esac
