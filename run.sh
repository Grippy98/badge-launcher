#!/bin/sh
# Kill existing instances
killall -q micropython
# Wait a brief moment
sleep 0.5
# Disable framebuffer console cursor and blinking
echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null
setterm -cursor off > /dev/tty0 2>/dev/null
clear > /dev/tty0
# Run the app
APP_DIR="$(dirname "$(realpath "$0")")"
cd "$APP_DIR"
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:"$APP_DIR"/libtuxdriver/unix
./micropython main.py
