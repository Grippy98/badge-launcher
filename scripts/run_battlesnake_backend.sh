#!/bin/sh
set -eu

BADGESNAKE_ROOT="${BADGESNAKE_ROOT:-$HOME/interactor/badge-demo}"
STATE_DIR="${BADGESNAKE_STATE_DIR:-/tmp/badgesnake}"
BADGESNAKE_BUILD_SCRIPT="${BADGESNAKE_BUILD_SCRIPT:-$BADGESNAKE_ROOT/scripts/build_badgesnake_ui_sim.sh}"
BADGESNAKE_BIN="${BADGESNAKE_BIN:-$BADGESNAKE_ROOT/.cache/badgesnake-ui-sim}"
BADGESNAKE_MATCHUP="${BADGESNAKE_MATCHUP:-demo}"

if ! command -v go >/dev/null 2>&1; then
    echo "go is required to run the BadgeSnake simulator backend" >&2
    exit 1
fi

if [ ! -f "$BADGESNAKE_BUILD_SCRIPT" ]; then
    echo "BadgeSnake build helper not found at $BADGESNAKE_BUILD_SCRIPT" >&2
    exit 1
fi

mkdir -p "$STATE_DIR"
BADGESNAKE_BIN="$(BADGESNAKE_BIN="$BADGESNAKE_BIN" sh "$BADGESNAKE_BUILD_SCRIPT")"
pkill -f "go run ./cmd/badgesnake ui-sim" 2>/dev/null || true
pkill -f "$BADGESNAKE_BIN ui-sim" 2>/dev/null || true
nohup sh -c "\"$BADGESNAKE_BIN\" ui-sim --state-file \"$STATE_DIR/state.json\" --command-file \"$STATE_DIR/command.json\" --matchup \"$BADGESNAKE_MATCHUP\"" >/tmp/badgesnake-backend.log 2>&1 &
