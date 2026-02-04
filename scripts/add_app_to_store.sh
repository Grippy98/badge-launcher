#!/bin/bash
# Add an app to the badge app store

set -e

# Check arguments
if [ "$#" -lt 5 ]; then
    echo "Usage: $0 <store-dir> <app-id> <repo-url> <name> <author> [description] [category] [version]"
    echo ""
    echo "Example:"
    echo "  $0 ../badge-app-store weather https://github.com/user/weather-app.git \"Weather\" \"John Doe\" \"Check the weather\" \"tools\" \"1.0.0\""
    echo ""
    exit 1
fi

STORE_DIR=$1
APP_ID=$2
APP_REPO=$3
APP_NAME=$4
AUTHOR=$5
DESCRIPTION=${6:-"A badge app"}
CATEGORY=${7:-"apps"}
VERSION=${8:-"1.0.0"}

cd "$STORE_DIR"

echo "Adding app to store..."
echo "  ID: $APP_ID"
echo "  Name: $APP_NAME"
echo "  Repo: $APP_REPO"
echo "  Category: $CATEGORY"
echo ""

# Create app directory
mkdir -p "apps/$APP_ID"

# Add as submodule
echo "Adding git submodule..."
git submodule add "$APP_REPO" "apps/$APP_ID/app" || {
    echo "Failed to add submodule. It may already exist."
    echo "Updating existing submodule..."
    cd "apps/$APP_ID/app"
    git pull origin main
    cd ../../..
}

# Create metadata.json
echo "Creating metadata..."
cat > "apps/$APP_ID/metadata.json" << EOF
{
  "id": "$APP_ID",
  "name": "$APP_NAME",
  "version": "$VERSION",
  "author": "$AUTHOR",
  "description": "$DESCRIPTION",
  "category": "$CATEGORY",
  "repo": "$APP_REPO",
  "main_file": "${APP_ID}_app.py",
  "dependencies": [],
  "requires_img2bin": false,
  "license": "MIT"
}
EOF

# Update manifest.json
echo "Updating manifest..."
python3 - "$APP_ID" << 'PYTHON_EOF'
import json
import sys
from datetime import datetime

# Get app_id from command line argument
app_id = sys.argv[1]

# Read current manifest
try:
    with open('manifest.json', 'r') as f:
        manifest = json.load(f)
except:
    manifest = {"version": "1.0", "apps": []}

# Read new app metadata
with open(f'apps/{app_id}/metadata.json', 'r') as f:
    new_app = json.load(f)

# Check if app already exists
existing_idx = None
for i, app in enumerate(manifest['apps']):
    if app['id'] == new_app['id']:
        existing_idx = i
        break

# Add or update app
if existing_idx is not None:
    print(f"Updating existing app: {new_app['id']}")
    manifest['apps'][existing_idx] = new_app
else:
    print(f"Adding new app: {new_app['id']}")
    manifest['apps'].append(new_app)

# Sort apps by name
manifest['apps'].sort(key=lambda x: x['name'])

# Update timestamp
manifest['last_updated'] = datetime.now().strftime('%Y-%m-%d')

# Write updated manifest
with open('manifest.json', 'w') as f:
    json.dump(manifest, f, indent=2)

print("✓ Manifest updated")
PYTHON_EOF

# Commit changes
echo ""
echo "Committing changes..."
git add .
git commit -m "Add/update $APP_ID to app store"

echo ""
echo "✓ App added successfully!"
echo ""
echo "Next steps:"
echo "1. Review the changes: git diff HEAD~1"
echo "2. Push to remote: git push"
echo "3. App will be available in the badge app store"
echo ""
