#!/bin/bash
# Update version across all files
#
# Usage: ./scripts/update_version.sh <version>
# Example: ./scripts/update_version.sh 1.0.1

if [ -z "$1" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.1"
    exit 1
fi

VERSION="$1"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Updating version to $VERSION..."

# Update VERSION file
echo "$VERSION" > "$ROOT_DIR/VERSION"
echo "✓ Updated VERSION file"

# Update debian/changelog (prepend new entry)
CHANGELOG="$ROOT_DIR/debian/changelog"
TIMESTAMP=$(date -R)
TEMP_CHANGELOG=$(mktemp)

cat > "$TEMP_CHANGELOG" << EOF
badge-launcher ($VERSION) unstable; urgency=medium

  * Version bump to $VERSION

 -- Andrei Aldea <andrei@ti.com>  $TIMESTAMP

EOF

cat "$CHANGELOG" >> "$TEMP_CHANGELOG"
mv "$TEMP_CHANGELOG" "$CHANGELOG"
echo "✓ Updated debian/changelog"

echo ""
echo "Version updated to $VERSION"
echo "Don't forget to:"
echo "  1. Edit debian/changelog to add proper change notes"
echo "  2. Commit the changes: git add VERSION debian/changelog"
echo "  3. Create a git tag: git tag -a v$VERSION -m 'Release $VERSION'"
