#!/bin/bash

# Configuration (Specific to this machine)
BADGE_IP="192.168.1.126"
BADGE_USER="root"
BADGE_PASS="beagle"
DEST_DIR="~/badge_launcher"

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo "sshpass is required for this script. Please install it: sudo apt install sshpass"
    exit 1
fi

echo "Syncing files to $BADGE_USER@$BADGE_IP:$DEST_DIR..."

# Create directory if it doesn't exist
sshpass -p "$BADGE_PASS" ssh -o StrictHostKeyChecking=no "$BADGE_USER@$BADGE_IP" "mkdir -p $DEST_DIR"

# Sync files (excluding git and other unnecessary files)
sshpass -p "$BADGE_PASS" rsync -avz --delete --exclude '.git' --exclude '.gitignore' --exclude 'sync.sh' --exclude 'micropython' --exclude 'build/' --exclude 'build-standard/' ./ "$BADGE_USER@$BADGE_IP:$DEST_DIR/"

# Set permissions
echo "Setting permissions..."
sshpass -p "$BADGE_PASS" ssh -o StrictHostKeyChecking=no "$BADGE_USER@$BADGE_IP" "chmod +x $DEST_DIR/run.sh $DEST_DIR/micropython 2>/dev/null || true"

echo "Sync complete!"
