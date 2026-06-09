#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
SRC_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
DEST_ROOT="${BADGE_LAUNCHER_DEST:-/opt/badge_launcher}"
DEST_DEMOS_DIR="$DEST_ROOT/applications/demos"
DEST_SCRIPTS_DIR="$DEST_ROOT/scripts"

mkdir -p "$DEST_DEMOS_DIR"
mkdir -p "$DEST_SCRIPTS_DIR"

install -m 0644 \
    "$SRC_DIR/applications/demos/sensor_visualizer_app.py" \
    "$DEST_DEMOS_DIR/sensor_visualizer_app.py"
install -m 0644 \
    "$SRC_DIR/applications/demos/README.md" \
    "$DEST_DEMOS_DIR/README.md"
install -m 0755 \
    "$SRC_DIR/scripts/run_local_iio_sensors.sh" \
    "$DEST_SCRIPTS_DIR/run_local_iio_sensors.sh"
install -m 0644 \
    "$SRC_DIR/scripts/run_local_iio_sensors.py" \
    "$DEST_SCRIPTS_DIR/run_local_iio_sensors.py"

echo "Deployed IIO Sensors demo to $DEST_ROOT"
