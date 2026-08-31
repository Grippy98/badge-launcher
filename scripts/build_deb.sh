#!/bin/bash
set -e

# Configuration
PKG_NAME="badge-launcher"
PKG_VERSION="$(tr -d '\r\n' < VERSION)"
PKG_ARCH="arm64"
DEB_FILE="${PKG_NAME}_${PKG_VERSION}_${PKG_ARCH}.deb"

# Temporary build directory
readonly BUILD_DIR=$(mktemp -d -t deb-build-XXXXXXXXXX)
STAGING_DIR="$BUILD_DIR/staging"
INSTALL_DIR="$STAGING_DIR/usr/lib/badge-launcher"
BIN_DIR="$STAGING_DIR/usr/bin"
SERVICE_DIR="$STAGING_DIR/usr/lib/systemd/system"
STATE_DIR="$STAGING_DIR/var/lib/badge-launcher"
DEFAULT_DIR="$STAGING_DIR/etc/default"
DEBIAN_DIR="$STAGING_DIR/DEBIAN"

# Cleanup only the directory returned by mktemp.
cleanup() {
    if [ -d "$BUILD_DIR" ]; then
        rm -rf -- "$BUILD_DIR"
    fi
}
trap cleanup EXIT

echo "Using temporary build directory: $BUILD_DIR"

# Create directory structure
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$SERVICE_DIR"
mkdir -p "$DEFAULT_DIR"
mkdir -p "$DEBIAN_DIR"
mkdir -p "$STATE_DIR/app-data" "$STATE_DIR/installed-apps"

echo "Copying application files..."
rsync -av \
    --exclude='debian' \
    --exclude='.git' \
    --exclude='.venv*' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='*.egg-info' \
    --exclude='build' \
    --exclude='dist' \
    --exclude='.DS_Store' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='tests' \
    --exclude='*.deb' \
    --exclude='build_deb.sh' \
    --exclude='sync.sh' \
    ./ "$INSTALL_DIR/"

echo "Copying packaging metadata from debian/..."
MAINTAINER=$(grep "^Maintainer:" debian/control | head -1 | cut -d' ' -f2-)
VERSION="$PKG_VERSION"

# Extract only the binary package part of control and add Maintainer/Version
{
    sed -n '/^Package:/,$p' debian/control | \
        sed 's/\${shlibs:Depends}, //g' | \
        sed 's/\${misc:Depends}, //g'
    echo "Maintainer: $MAINTAINER"
    echo "Version: $VERSION"
} > "$DEBIAN_DIR/control"
cp debian/postinst "$DEBIAN_DIR/"
cp debian/preinst "$DEBIAN_DIR/"
cp debian/prerm "$DEBIAN_DIR/"
cp debian/postrm "$DEBIAN_DIR/"
cp debian/conffiles "$DEBIAN_DIR/"
cp debian/badge-launcher.service "$SERVICE_DIR/"
cp debian/badgebeam-receiver.service "$SERVICE_DIR/"
cp debian/badgebeam-receiver.default "$DEFAULT_DIR/badgebeam-receiver"
cp debian/badge-launcher.wrapper "$BIN_DIR/badge-launcher"
cp debian/badge-app.wrapper "$BIN_DIR/badge-app"


echo "Fixing permissions..."
chmod 755 "$DEBIAN_DIR/postinst"
chmod 755 "$DEBIAN_DIR/preinst"
chmod 755 "$DEBIAN_DIR/prerm"
chmod 755 "$DEBIAN_DIR/postrm"
chmod +x "$INSTALL_DIR/scripts/run.sh"
chmod +x "$INSTALL_DIR/scripts/badgebeam_bleserver.py"
chmod 755 "$BIN_DIR/badge-launcher"
chmod 755 "$BIN_DIR/badge-app"

echo "Building package manually (using ar/tar)..."

# Prepare control.tar.gz
cd "$DEBIAN_DIR"
COPYFILE_DISABLE=1 tar -czf "$BUILD_DIR/control.tar.gz" --format=ustar --owner=0 --group=0 *
cd - > /dev/null

# Prepare data.tar.gz
cd "$STAGING_DIR"
COPYFILE_DISABLE=1 tar -czf "$BUILD_DIR/data.tar.gz" --format=ustar --owner=0 --group=0 etc usr var
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
