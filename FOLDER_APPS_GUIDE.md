# Folder-Based Apps Guide

This guide explains the new folder-based app structure that enables better organization and an app store ecosystem.

## What Changed?

The app loader now supports **two app structures**:

### 1. Flat Files (Original)
```
applications/apps/
├── simple_app.py
└── another_app.py
```

### 2. Folders (New!)
```
applications/apps/
├── myapp/
│   ├── myapp_app.py
│   ├── data/
│   └── assets/
└── anotherapp/
    └── anotherapp_app.py
```

Both structures work simultaneously - no breaking changes!

## Quick Start

### Creating a Folder-Based App

```bash
# 1. Copy the template
cp -r applications/apps/_template_app applications/apps/myapp

# 2. Rename the main file
cd applications/apps/myapp
mv template_app_app.py myapp_app.py

# 3. Edit the code
# - Change class name
# - Update app name
# - Add your logic

# 4. Launch - your app will appear automatically!
```

## Why Folder-Based Apps?

✅ **Self-contained** - All resources in one place
✅ **Easy to share** - Copy/delete entire folder
✅ **Git-friendly** - Can be separate repos
✅ **App store ready** - Easy to distribute
✅ **Better organized** - Separate code from data

## File Naming Convention

The loader looks for your main app file in this order:

1. `{folder_name}_app.py` ← **Recommended**
2. `app.py`
3. `{folder_name}.py`

Example:
```
chiptunez/
└── chiptunez_app.py  ✅ Preferred naming
```

## Examples

### ChipTunez (Complete Example)

```
applications/apps/chiptunez/
├── chiptunez_app.py      # Main app
├── songs/                # Data directory
│   ├── imperial_march.json
│   ├── super_mario.json
│   └── ...
└── README.md
```

The ChipTunez app demonstrates:
- Folder-based structure
- JSON data files
- Self-contained resources
- Clean organization

## Git Submodules

Folder-based apps work great as Git submodules:

```bash
# Add an app as a submodule
cd applications/apps
git submodule add https://github.com/user/awesome-app.git

# Update all apps
git submodule update --remote

# Clone project with all apps
git clone --recursive https://github.com/user/badge-project.git
```

## Migration Guide

### Converting a Flat App to Folder-Based

1. **Create folder:**
   ```bash
   mkdir applications/apps/myapp
   ```

2. **Move app file:**
   ```bash
   mv applications/apps/myapp.py applications/apps/myapp/myapp_app.py
   ```

3. **Add resources:**
   ```bash
   cd applications/apps/myapp
   mkdir data assets
   # Move your data files here
   ```

4. **Update paths in code** (if needed):
   ```python
   # Before:
   data_path = "data/file.json"

   # After (if using relative paths):
   data_path = "applications/apps/myapp/data/file.json"
   ```

5. **Done!** The app loader will find it automatically.

## App Store Vision

This structure enables:

- 📦 **Package Distribution** - Share apps as ZIP or Git repos
- 🔄 **Easy Updates** - `git pull` or `git submodule update`
- 🏪 **App Registry** - Central catalog of available apps
- ⚡ **Quick Install** - `badge-store install awesome-app`
- 🔐 **Version Control** - Each app independently versioned

See [APP_STORE.md](APP_STORE.md) for the complete app store vision.

## Resources

- [applications/README.md](applications/README.md) - Complete app development guide
- [applications/apps/_template_app/](applications/apps/_template_app/) - Copy this to start
- [applications/apps/chiptunez/](applications/apps/chiptunez/) - Complete working example
- [APP_STORE.md](APP_STORE.md) - App store concept and future plans

## FAQ

**Q: Do I have to use folders?**
A: No! Flat `.py` files still work perfectly. Use folders when you need resources or want better organization.

**Q: Can I mix both structures?**
A: Yes! You can have both flat files and folders in the same category.

**Q: Will old apps break?**
A: No! All existing flat-file apps continue to work without changes.

**Q: What if my folder doesn't follow the naming convention?**
A: The loader tries multiple names. If none match, you'll see a warning message but it won't break anything.

**Q: Can I have subfolders in my app?**
A: Yes! Organize your app however you want. Just make sure the main file follows the naming convention.

**Q: How do I test if my app loads?**
A: Just launch the badge launcher. If your app appears in the menu, it loaded successfully!

## Contributing

Have ideas for improving the app system?

1. Create example apps
2. Suggest naming conventions
3. Help design the app store
4. Build developer tools
5. Write documentation

Join us in building an awesome app ecosystem!
