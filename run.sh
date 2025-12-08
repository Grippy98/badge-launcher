#!/bin/sh
# Kill existing instances
killall -q micropython
# Wait a brief moment
sleep 0.5
# Run the app
cd ~/badge_launcher
./micropython main.py
