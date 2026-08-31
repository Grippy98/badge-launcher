#!/bin/sh
set -eu

: "${BADGE_HOST:?Set BADGE_HOST to the badge hostname or IP address}"
BADGE_USER=${BADGE_USER:-root}
BADGE_DEST=${BADGE_DEST:-/root/badge-launcher-dev}

case "$BADGE_USER" in (*[!A-Za-z0-9_.-]*) echo "Unsafe BADGE_USER" >&2; exit 2;; esac
case "$BADGE_HOST" in (*[!A-Za-z0-9_.:-]*) echo "Unsafe BADGE_HOST" >&2; exit 2;; esac
case "$BADGE_DEST" in (/*) ;; (*) echo "BADGE_DEST must be absolute" >&2; exit 2;; esac
case "$BADGE_DEST" in (*[!A-Za-z0-9_./-]*) echo "Unsafe BADGE_DEST" >&2; exit 2;; esac

TARGET="$BADGE_USER@$BADGE_HOST"
ssh "$TARGET" mkdir -p "$BADGE_DEST"
rsync -avz --delete \
    --exclude .git \
    --exclude '.venv*' \
    --exclude __pycache__ \
    --exclude .pytest_cache \
    --exclude '*.egg-info' \
    --exclude '*.deb' \
    ./ "$TARGET:$BADGE_DEST/"
ssh "$TARGET" chmod +x "$BADGE_DEST/scripts/run.sh" "$BADGE_DEST/scripts/badgebeam_bleserver.py"

echo "Synced to $TARGET:$BADGE_DEST"
