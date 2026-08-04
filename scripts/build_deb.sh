#!/bin/bash
set -e

# Configuration
PKG_NAME="badge-launcher"
PKG_VERSION="$(tr -d '\r\n' < VERSION)"
PKG_ARCH="arm64"
DEB_FILE="${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

# Temporary build directory
BUILD_DIR=$(mktemp -d -t deb-build-XXXXXXXXXX)
STAGING_DIR="$BUILD_DIR/staging"
INSTALL_DIR="$STAGING_DIR/opt/badge_launcher"
SERVICE_DIR="$STAGING_DIR/etc/systemd/system"
DEBIAN_DIR="$STAGING_DIR/DEBIAN"

# Cleanup on exit
trap "rm -rf $BUILD_DIR" EXIT

echo "Using temporary build directory: $BUILD_DIR"

# Create directory structure
mkdir -p "$INSTALL_DIR"
mkdir -p "$SERVICE_DIR"
mkdir -p "$DEBIAN_DIR"

echo "Copying application files..."
rsync -av \
    --exclude='debian' \
    --exclude='.git' \
    --exclude='.DS_Store' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='lv_micropython' \
    --exclude='tests' \
    --exclude='*.deb' \
    --exclude='build_deb.sh' \
    --exclude='sync.sh' \
    --exclude='.gemini' \
    --exclude='metadata' \
    --exclude='img2bin' \
    ./ "$INSTALL_DIR/"

echo "Copying packaging metadata from debian/..."
MAINTAINER=$(grep "^Maintainer:" debian/control | head -1 | cut -d' ' -f2-)
VERSION=$(head -1 debian/changelog | cut -d"(" -f2 | cut -d")" -f1)

# Extract only the binary package part of control and add Maintainer/Version
{
    sed -n '/^Package:/,$p' debian/control | \
        sed 's/\${shlibs:Depends}, //g' | \
        sed 's/\${misc:Depends}, //g'
    echo "Maintainer: $MAINTAINER"
    echo "Version: $VERSION"
} > "$DEBIAN_DIR/control"
cp debian/postinst "$DEBIAN_DIR/"
cp debian/badge-launcher.service "$SERVICE_DIR/"


echo "Fixing permissions..."
chmod 755 "$DEBIAN_DIR/postinst"
chmod +x "$INSTALL_DIR/scripts/run.sh"
[ -f "$INSTALL_DIR/micropython" ] && chmod +x "$INSTALL_DIR/micropython"

echo "Building package manually (using ar/tar)..."

# Prepare control.tar.gz
cd "$DEBIAN_DIR"
COPYFILE_DISABLE=1 tar -czf "$BUILD_DIR/control.tar.gz" --format=ustar *
cd - > /dev/null

# Prepare data.tar.gz
cd "$STAGING_DIR"
COPYFILE_DISABLE=1 tar -czf "$BUILD_DIR/data.tar.gz" --format=ustar --owner=0 --group=0 opt etc
cd - > /dev/null

# Create debian-binary
echo "2.0" > "$BUILD_DIR/debian-binary"

# Combine into .deb. BSD ar on macOS silently drops non-object members, while
# bsdtar can write a valid ar container. GNU/Linux keeps using GNU ar.
if tar --version 2>/dev/null | grep -q '^bsdtar'; then
    COPYFILE_DISABLE=1 tar --format=ar -cf "$DEB_FILE" -C "$BUILD_DIR" \
        debian-binary control.tar.gz data.tar.gz
else
    rm -f "$DEB_FILE"
    ar r "$DEB_FILE" "$BUILD_DIR/debian-binary" "$BUILD_DIR/control.tar.gz" "$BUILD_DIR/data.tar.gz"
fi

echo "Done! Package created: $DEB_FILE"
