#!/bin/sh
set -eu

DEST_ROOT="${BADGE_LAUNCHER_DEST:-$HOME/badge_launcher}"
BADGESNAKE_ROOT="${BADGESNAKE_ROOT:-$HOME/interactor/badge-demo}"
STATE_DIR="${BADGESNAKE_STATE_DIR:-/tmp/badgesnake}"

if [ ! -x "$DEST_ROOT/micropython" ]; then
    echo "Micropython binary not found at $DEST_ROOT/micropython" >&2
    exit 1
fi

if ! command -v go >/dev/null 2>&1; then
    echo "go is required to run the BadgeSnake simulator backend" >&2
    exit 1
fi

mkdir -p "$STATE_DIR"
pkill -f "go run ./cmd/badgesnake ui-sim" 2>/dev/null || true
nohup sh -c "cd \"$BADGESNAKE_ROOT\" && go run ./cmd/badgesnake ui-sim --state-file \"$STATE_DIR/state.json\" --command-file \"$STATE_DIR/command.json\"" >/tmp/badgesnake-backend.log 2>&1 &
sleep 1

cd "$DEST_ROOT"
killall -q micropython || true
sleep 0.5
echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null || true
setterm -cursor off > /dev/tty0 2>/dev/null || true
clear > /dev/tty0 2>/dev/null || true
"$DEST_ROOT/micropython" scripts/run_local_battlesnake.py
