#!/bin/sh
set -eu

DEST_ROOT="${BADGE_LAUNCHER_DEST:-/opt/badge_launcher}"

if [ ! -x "$DEST_ROOT/micropython" ]; then
    echo "Micropython binary not found at $DEST_ROOT/micropython" >&2
    exit 1
fi

cd "$DEST_ROOT"
killall -q micropython || true
sleep 0.5
echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null || true
setterm -cursor off > /dev/tty0 2>/dev/null || true
clear > /dev/tty0 2>/dev/null || true
"$DEST_ROOT/micropython" scripts/run_local_iio_sensors.py
