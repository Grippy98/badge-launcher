#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP_DIR=$(dirname "$SCRIPT_DIR")
cd "$APP_DIR"

exec /usr/bin/python3 -u main.py --backend framebuffer "$@"
