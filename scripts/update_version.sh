#!/bin/bash
# Update version across all files
#
# Usage: ./scripts/update_version.sh <version>
# Example: ./scripts/update_version.sh 1.0.1

set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 2026.08.30~experimental2"
    exit 1
fi

RELEASE_VERSION="$1"
PYTHON_BIN="${PYTHON:-python3}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PYPROJECT="$ROOT_DIR/pyproject.toml"
CHANGELOG="$ROOT_DIR/debian/changelog"

if [ ! -f "$PYPROJECT" ] || [ ! -f "$CHANGELOG" ]; then
    echo "Release metadata is incomplete under $ROOT_DIR" >&2
    exit 1
fi

# Validate and derive the public Python version before changing release files.
PEP440_VERSION="$("$PYTHON_BIN" "$SCRIPT_DIR/versioning.py" "$RELEASE_VERSION")"

echo "Updating package version to $RELEASE_VERSION (Python: $PEP440_VERSION)..."

"$PYTHON_BIN" "$SCRIPT_DIR/versioning.py" \
    --update-pyproject "$PYPROJECT" "$RELEASE_VERSION" >/dev/null
echo "✓ Updated pyproject.toml"

# Update VERSION file
printf '%s\n' "$RELEASE_VERSION" > "$ROOT_DIR/VERSION"
echo "✓ Updated VERSION file"

# Update debian/changelog (prepend new entry)
TIMESTAMP=$(date -R)
TEMP_CHANGELOG=$(mktemp)
trap 'rm -f "$TEMP_CHANGELOG"' EXIT

cat > "$TEMP_CHANGELOG" << EOF
badge-launcher ($RELEASE_VERSION) unstable; urgency=medium

  * Version bump to $RELEASE_VERSION

 -- Andrei Aldea <andrei@ti.com>  $TIMESTAMP

EOF

cat "$CHANGELOG" >> "$TEMP_CHANGELOG"
mv "$TEMP_CHANGELOG" "$CHANGELOG"
trap - EXIT
echo "✓ Updated debian/changelog"

echo ""
echo "Version updated to $RELEASE_VERSION (Python package $PEP440_VERSION)"
echo "Don't forget to:"
echo "  1. Edit debian/changelog to add proper change notes"
echo "  2. Commit the changes: git add VERSION pyproject.toml debian/changelog"
echo "  3. Create a git tag: git tag -a v$RELEASE_VERSION -m 'Release $RELEASE_VERSION'"
