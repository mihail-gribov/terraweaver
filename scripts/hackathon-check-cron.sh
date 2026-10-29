#!/bin/bash
# Weekly cron entry point for check-hackathon.py.
#
# Logs every run to var/hackathon-check.log and raises a desktop notification
# only when the pages actually moved. Snapshots are NOT auto-updated: the diff
# has to be read by a human (and logged in docs/archive/about.md) before it is accepted.

set -uo pipefail

PROJECT="/home/mike/Projects/terraweaver"
LOG="$PROJECT/var/hackathon-check.log"

mkdir -p "$PROJECT/var"

output=$(/usr/bin/python3 "$PROJECT/scripts/check-hackathon.py" 2>&1)
status=$?

{
    echo "=== $(date -Iseconds) exit=$status ==="
    echo "$output"
} >> "$LOG"

if [ "$status" -eq 1 ]; then
    export DISPLAY="${DISPLAY:-:0}"
    export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}"
    notify-send -u critical "Hackathon rules changed" \
        "Nebius x NVIDIA rules or overview page moved. See $LOG" 2>/dev/null
fi

exit "$status"
