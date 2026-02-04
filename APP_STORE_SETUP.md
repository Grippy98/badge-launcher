# Badge App Store Setup Guide

This guide explains how to set up and manage a badge app store using git submodules.

## Overview

The app store uses a two-repository architecture:
- **Store Repository**: Contains metadata and references to apps via git submodules
- **App Repositories**: Individual repos for each app

## Store Repository Structure

```
badge-app-store/
├── manifest.json          # Master list of available apps
├── README.md
└── apps/
    ├── weather/
    │   ├── metadata.json  # App metadata for the store
    │   └── app/          # Git submodule → weather app repo
    ├── calculator/
    │   ├── metadata.json
    │   └── app/          # Git submodule → calculator app repo
    └── my-game/
        ├── metadata.json
        └── app/          # Git submodule → game app repo
```

## Setting Up the Store Repository

### 1. Create the Store Repository

```bash
mkdir badge-app-store
cd badge-app-store
git init

# Create directory structure
mkdir -p apps

# Create README
cat > README.md << 'EOF'
# Badge App Store

Community apps for the TI Badge.

## Available Apps

See [manifest.json](manifest.json) for the full list.
EOF

git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_ORG/badge-app-store.git
git push -u origin main
```

### 2. Add an App to the Store

For each app you want to add:

```bash
# Create app directory
mkdir -p apps/my-app

# Add the app as a git submodule
git submodule add https://github.com/USER/my-app-repo.git apps/my-app/app

# Create metadata
cat > apps/my-app/metadata.json << 'EOF'
{
  "id": "my-app",
  "name": "My Awesome App",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "A cool app that does awesome things",
  "category": "tools",
  "repo": "https://github.com/USER/my-app-repo.git",
  "main_file": "my_app_app.py",
  "dependencies": [],
  "requires_img2bin": false,
  "license": "MIT"
}
EOF

# Update manifest.json (see below for format)

# Commit changes
git add .
git commit -m "Add my-app to store"
git push
```

## Manifest Format

The `manifest.json` file lists all available apps:

```json
{
  "version": "1.0",
  "last_updated": "2026-02-04",
  "apps": [
    {
      "id": "weather",
      "name": "Weather",
      "version": "1.0.0",
      "author": "John Doe",
      "description": "Check current weather conditions",
      "category": "tools",
      "repo": "https://github.com/user/weather-app.git",
      "main_file": "weather_app.py",
      "dependencies": [],
      "requires_img2bin": false
    },
    {
      "id": "calculator",
      "name": "Calculator",
      "version": "1.2.0",
      "author": "Jane Smith",
      "description": "Simple calculator app",
      "category": "tools",
      "repo": "https://github.com/user/calc-app.git",
      "main_file": "calculator_app.py",
      "dependencies": [],
      "requires_img2bin": false
    },
    {
      "id": "snake-deluxe",
      "name": "Snake Deluxe",
      "version": "2.0.0",
      "author": "Game Dev",
      "description": "Classic snake game with power-ups",
      "category": "games",
      "repo": "https://github.com/user/snake-deluxe.git",
      "main_file": "snake_deluxe_app.py",
      "dependencies": [],
      "requires_img2bin": false
    }
  ]
}
```

## Metadata Fields

Each app's `metadata.json` should include:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique app identifier (folder name) |
| `name` | string | Yes | Display name in app store |
| `version` | string | Yes | Semantic version (e.g., "1.0.0") |
| `author` | string | Yes | Creator name |
| `description` | string | Yes | Short description |
| `category` | string | Yes | Category: "apps", "games", "tools", "media", "settings" |
| `repo` | string | Yes | Git repository URL |
| `main_file` | string | Yes | Main Python file (e.g., "app_app.py") |
| `dependencies` | array | No | List of required system packages |
| `requires_img2bin` | boolean | No | Whether app needs img2bin tool |
| `license` | string | No | License (e.g., "MIT", "GPL-3.0") |
| `icon` | string | No | Icon filename (if included in app) |

## App Repository Structure

Each app repository should follow this structure:

```
my-app-repo/
├── my_app_app.py          # Main app file (must match main_file in metadata)
├── README.md              # App documentation
├── assets/                # Optional: images, sounds, etc.
│   └── icon.bin
└── LICENSE                # License file
```

### App Naming Convention

- Repository name: `my-app` or `my-app-repo`
- Main file: `{app_id}_app.py` (e.g., `calculator_app.py`)
- App folder will be installed to: `applications/apps/{app_id}/`

## Using the App Store on the Badge

### 1. Access the App Store

Navigate to: **Settings → App Store**

### 2. Install an App

1. Browse the list of available apps
2. Use ↑/↓ to select an app
3. Press ENTER to install
4. Wait for download and installation
5. Restart the badge to see the new app

### 3. Update Configuration

Before using, update the store URL in [applications/tools/app_store_app.py](applications/tools/app_store_app.py):

```python
self.store_repo = "https://github.com/YOUR_ORG/badge-app-store.git"
self.manifest_url = "https://raw.githubusercontent.com/YOUR_ORG/badge-app-store/main/manifest.json"
```

## Updating Apps

### Update App Version

1. Make changes in the app repository
2. Commit and push changes
3. Update version in app's metadata.json
4. In store repo:
   ```bash
   cd apps/my-app/app
   git pull origin main
   cd ../../..
   git add apps/my-app/app
   git commit -m "Update my-app to v1.1.0"
   git push
   ```
5. Update manifest.json with new version
6. Users can reinstall to get the update

## Helper Scripts

### Add App to Store Script

```bash
#!/bin/bash
# scripts/add_app_to_store.sh

APP_ID=$1
APP_REPO=$2
APP_NAME=$3
AUTHOR=$4
DESCRIPTION=$5

if [ -z "$APP_ID" ] || [ -z "$APP_REPO" ]; then
    echo "Usage: $0 <app-id> <repo-url> <name> <author> <description>"
    exit 1
fi

# Add submodule
git submodule add "$APP_REPO" "apps/$APP_ID/app"

# Create metadata
cat > "apps/$APP_ID/metadata.json" << EOF
{
  "id": "$APP_ID",
  "name": "$APP_NAME",
  "version": "1.0.0",
  "author": "$AUTHOR",
  "description": "$DESCRIPTION",
  "category": "apps",
  "repo": "$APP_REPO",
  "main_file": "${APP_ID}_app.py",
  "dependencies": [],
  "requires_img2bin": false
}
EOF

echo "App added! Now update manifest.json and commit changes."
```

## Categories

Recommended categories:
- **apps**: Utility applications
- **games**: Games and entertainment
- **tools**: Development and system tools
- **media**: Photo, music, video viewers
- **settings**: Configuration apps

## Best Practices

1. **Version Control**: Use semantic versioning (major.minor.patch)
2. **Testing**: Test apps thoroughly before adding to store
3. **Documentation**: Include clear README in app repos
4. **Dependencies**: List any system requirements
5. **Licensing**: Always include a license file
6. **Updates**: Keep manifest.json updated with latest versions

## Troubleshooting

### App won't install
- Check network connectivity
- Verify git is installed on the badge
- Check repository URL is correct and public

### App doesn't appear after install
- Restart the badge
- Check app was copied to `applications/apps/{app_id}/`
- Verify main_file matches the actual filename

### Submodule issues
```bash
# Reset all submodules
git submodule update --init --recursive --force

# Update specific submodule
cd apps/my-app/app
git pull origin main
cd ../../..
git add apps/my-app/app
git commit -m "Update submodule"
```

## Example Store

See the official store for examples:
- Store repo: `https://github.com/YOUR_ORG/badge-app-store`
- Example apps: Check the `apps/` directory

## Contributing Apps

To contribute an app to the community store:

1. Create your app following the structure above
2. Host it in a public git repository
3. Submit a pull request to the store repo with:
   - Added submodule in `apps/{your-app}/app`
   - Created `apps/{your-app}/metadata.json`
   - Updated `manifest.json`
4. Wait for review and approval
