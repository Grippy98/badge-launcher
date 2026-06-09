#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
SRC_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
DEST_ROOT="${BADGE_LAUNCHER_DEST:-/opt/badge_launcher}"
APP_NAME="battlesnake"
SRC_APP_DIR="$SRC_DIR/applications/games/$APP_NAME"
DEST_APP_DIR="$DEST_ROOT/applications/games/$APP_NAME"
SRC_BACKEND_SH="$SRC_DIR/scripts/run_battlesnake_backend.sh"
SRC_RUN_SH="$SRC_DIR/scripts/run_local_battlesnake.sh"
SRC_RUN_PY="$SRC_DIR/scripts/run_local_battlesnake.py"
DEST_SCRIPTS_DIR="$DEST_ROOT/scripts"

if [ ! -d "$SRC_APP_DIR" ]; then
    echo "Source app directory not found: $SRC_APP_DIR" >&2
    exit 1
fi

mkdir -p "$DEST_APP_DIR"
mkdir -p "$DEST_SCRIPTS_DIR"

rsync -av --delete \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$SRC_APP_DIR/" "$DEST_APP_DIR/"

install -m 0755 "$SRC_RUN_SH" "$DEST_SCRIPTS_DIR/run_local_battlesnake.sh"
install -m 0644 "$SRC_RUN_PY" "$DEST_SCRIPTS_DIR/run_local_battlesnake.py"
install -m 0755 "$SRC_BACKEND_SH" "$DEST_SCRIPTS_DIR/run_battlesnake_backend.sh"

echo "Deployed $APP_NAME to $DEST_APP_DIR"
