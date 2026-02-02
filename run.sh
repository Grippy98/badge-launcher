#!/bin/sh
# Kill existing instances
killall -q micropython
# Wait a brief moment
sleep 0.5
# Run the app
cd ~/badge_launcher
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/root/badge_launcher/libtuxdriver/unix
./micropython main.py
