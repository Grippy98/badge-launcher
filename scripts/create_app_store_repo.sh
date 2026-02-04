#!/bin/bash
# Create a new badge app store repository structure

set -e

STORE_DIR=${1:-"../badge-app-store"}

echo "Creating badge app store repository at: $STORE_DIR"

# Create directory structure
mkdir -p "$STORE_DIR/apps"
cd "$STORE_DIR"

# Initialize git
git init

# Create README
cat > README.md << 'EOF'
# Badge App Store

Community apps for the TI Badge launcher.

## Available Apps

Browse available apps in the [manifest.json](manifest.json) file, or use the App Store app on your badge to install apps directly.

## Contributing

To contribute an app:

1. Create your app following the [app structure guidelines](https://github.com/YOUR_ORG/badge-slop/blob/main/APP_STORE_SETUP.md)
2. Host your app in a public git repository
3. Submit a PR adding your app as a submodule in `apps/{your-app-id}/app`
4. Include a `metadata.json` file in `apps/{your-app-id}/`
5. Update the `manifest.json` file

See [APP_STORE_SETUP.md](https://github.com/YOUR_ORG/badge-slop/blob/main/APP_STORE_SETUP.md) for detailed instructions.

## App Categories

- **apps**: Utility applications
- **games**: Games and entertainment
- **tools**: Development and system tools
- **media**: Photo, music, video viewers
- **settings**: Configuration apps

## License

Individual apps are licensed under their respective licenses. See each app's repository for details.
EOF

# Create initial manifest
cat > manifest.json << 'EOF'
{
  "version": "1.0",
  "last_updated": "2026-02-04",
  "store_url": "https://github.com/YOUR_ORG/badge-app-store",
  "apps": []
}
EOF

# Create example metadata template
mkdir -p .github
cat > .github/app_metadata_template.json << 'EOF'
{
  "id": "my-app",
  "name": "My App Name",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Short description of what the app does",
  "category": "apps",
  "repo": "https://github.com/USER/my-app-repo.git",
  "main_file": "my_app_app.py",
  "dependencies": [],
  "requires_img2bin": false,
  "license": "MIT"
}
EOF

# Create .gitignore
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so

# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp
*.swo
*~

# Temp
*.tmp
.tmp/
EOF

# Initial commit
git add .
git commit -m "Initial app store structure"

echo ""
echo "✓ App store repository created!"
echo ""
echo "Next steps:"
echo "1. Update URLs in README.md and manifest.json"
echo "2. Add remote: git remote add origin <your-repo-url>"
echo "3. Push: git push -u origin main"
echo "4. Start adding apps with: ../badge-slop/scripts/add_app_to_store.sh"
echo ""
