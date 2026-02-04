# App Store Submission Guide

Quick guide for developers who want to submit their apps to the badge app store.

## Prerequisites

- Your app in a git repository
- App follows the badge launcher structure
- App has been tested on actual hardware or simulator

## App Requirements Checklist

Before submitting, ensure your app meets these requirements:

### Required Files
- [ ] Main app file: `{app_id}_app.py`
- [ ] README.md with usage instructions
- [ ] LICENSE file (MIT, GPL, Apache, etc.)

### Code Requirements
- [ ] Extends `app.App` base class
- [ ] Implements `enter(on_exit=None)` method
- [ ] Implements `exit()` method for cleanup
- [ ] Handles keyboard input via LVGL events
- [ ] No hardcoded paths (use relative paths)
- [ ] Cleans up resources on exit
- [ ] No network access without user consent

### Testing
- [ ] Tested on badge hardware or simulator
- [ ] No crashes or exceptions
- [ ] Proper cleanup when exiting
- [ ] Input handling works correctly
- [ ] Memory usage is reasonable

## Validation

Use the validation script to check your app structure:

```bash
./scripts/validate_app.sh ../my-app-repo
```

Fix any errors before proceeding.

## Submission Steps

### 1. Prepare Your Repository

Ensure your repository is public and follows this structure:

```
my-app-repo/
├── my_app_app.py      # Main file (matches {app_id}_app.py)
├── README.md          # Documentation
├── LICENSE            # License file
├── assets/            # Optional: images, sounds
│   └── icon.bin       # Optional: app icon
└── data/              # Optional: app data
```

### 2. Create Metadata

Create a metadata file describing your app. Use this template:

```json
{
  "id": "my-app",
  "name": "My App Name",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Brief description under 80 characters",
  "category": "apps",
  "repo": "https://github.com/USERNAME/my-app-repo.git",
  "main_file": "my_app_app.py",
  "dependencies": [],
  "requires_img2bin": false,
  "license": "MIT"
}
```

**Categories:**
- `apps` - General applications
- `games` - Games and entertainment
- `tools` - System utilities and development tools
- `media` - Photo, music, video apps
- `settings` - Configuration and system settings

### 3. Fork the App Store Repository

```bash
# Fork on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/badge-app-store.git
cd badge-app-store
```

### 4. Add Your App

```bash
# Create app directory
mkdir -p apps/my-app

# Add your repo as a submodule
git submodule add https://github.com/YOUR_USERNAME/my-app-repo.git apps/my-app/app

# Copy your metadata
cp ../my-app-metadata.json apps/my-app/metadata.json

# Update manifest.json (see below)
```

### 5. Update manifest.json

Add your app entry to the `apps` array in `manifest.json`:

```json
{
  "version": "1.0",
  "apps": [
    {
      "id": "my-app",
      "name": "My App Name",
      "version": "1.0.0",
      "author": "Your Name",
      "description": "Brief description",
      "category": "apps",
      "repo": "https://github.com/YOUR_USERNAME/my-app-repo.git",
      "main_file": "my_app_app.py",
      "dependencies": [],
      "requires_img2bin": false
    }
  ]
}
```

Keep apps sorted alphabetically by name.

### 6. Test Locally

Test the installation process:

```bash
# On your badge, test installing your app
# Navigate to Settings → App Store
# Your app should appear in the list
# Try installing it and verify it works
```

### 7. Submit Pull Request

```bash
# Commit your changes
git add .
git commit -m "Add my-app to store"
git push origin main

# Create PR on GitHub
# Title: "Add [App Name] to store"
# Description: Brief overview of what the app does
```

## Pull Request Template

Use this template for your PR description:

```markdown
## App Information

- **Name**: My App Name
- **Category**: apps
- **Version**: 1.0.0
- **License**: MIT

## Description

[Brief description of what the app does and why it's useful]

## Testing

- [x] Validated with validate_app.sh
- [x] Tested on badge hardware
- [x] No crashes or memory leaks
- [x] Proper cleanup on exit

## Screenshots

[Optional: Add screenshots showing the app in action]

## Dependencies

[List any system dependencies or none]
```

## After Submission

### Review Process

Your submission will be reviewed for:
1. Code quality and safety
2. Proper resource cleanup
3. User experience
4. Documentation completeness
5. License compatibility

### Updates

To update your app:

1. Push changes to your app repository
2. Update version in metadata.json
3. Update the submodule in the store:
   ```bash
   cd apps/my-app/app
   git pull origin main
   cd ../../..
   git add apps/my-app/app
   git commit -m "Update my-app to v1.1.0"
   ```
4. Update manifest.json with new version
5. Submit PR with changes

## Best Practices

### Performance
- Keep file sizes small (target <1MB total)
- Minimize memory usage
- Use lazy loading for large assets
- Cache files in `/tmp/` for temporary data

### User Experience
- Provide clear instructions in-app
- Handle errors gracefully with user-friendly messages
- Show loading indicators for long operations
- Support ESC key to exit everywhere

### Code Quality
- Use descriptive variable names
- Add comments for complex logic
- Handle exceptions properly
- Follow Python naming conventions

### Documentation
- Write clear README with usage instructions
- Document any special requirements
- Include screenshots if helpful
- Provide examples of expected input/output

## Common Issues

### App Not Appearing in Menu

Check:
- Main file named correctly: `{app_id}_app.py`
- App class extends `app.App`
- File is executable and readable
- No syntax errors

### Installation Fails

Common causes:
- Repository not public
- Main file name doesn't match metadata
- Missing dependencies not listed
- Submodule not initialized

### App Crashes

Debug:
- Check error logs: `journalctl -u badge-launcher.service`
- Verify all imports are available
- Check file paths are relative, not absolute
- Ensure proper LVGL object cleanup

## Example Apps

Study these examples for reference:

- **Simple**: [dvd_app.py](applications/apps/dvd_app.py) - Bouncing DVD logo
- **Folder-based**: [chiptunez](applications/apps/chiptunez/) - Music player with data files
- **Network**: [xkcd_app.py](applications/apps/xkcd_app.py) - Fetches and displays content

## Getting Help

- Review [FOLDER_APPS_GUIDE.md](FOLDER_APPS_GUIDE.md) for app structure
- Check [APP_STORE_SETUP.md](APP_STORE_SETUP.md) for store details
- See [applications/README.md](applications/README.md) for API reference
- Open an issue for questions

## Resources

- [Badge Launcher Repository](https://github.com/YOUR_ORG/badge-slop)
- [App Store Repository](https://github.com/YOUR_ORG/badge-app-store)
- [LVGL Documentation](https://docs.lvgl.io/)
- [MicroPython Docs](https://docs.micropython.org/)
