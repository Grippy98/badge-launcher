# Badge Applications

This directory contains applications for the Badge Launcher, organized by category.

## Directory Structure

```
applications/
├── apps/        # User applications
├── games/       # Games
├── tools/       # Utility tools
└── settings/    # System settings
```

## App Organization

Apps can be organized in two ways:

### 1. Flat File Structure (Simple Apps)

For simple apps with no additional resources:

```
applications/apps/
└── simple_app.py
```

The file should contain an App subclass:

```python
from core import app
import lvgl as lv

class SimpleApp(app.App):
    def __init__(self):
        super().__init__("Simple App")

    def enter(self, on_exit=None):
        # Your app code here
        pass
```

### 2. Folder-Based Structure (Complex Apps)

For apps with resources, data files, or multiple modules:

```
applications/apps/
└── myapp/
    ├── myapp_app.py      # Main app file (preferred naming)
    ├── data/             # App data
    ├── assets/           # Images, fonts, etc.
    └── README.md         # App documentation
```

#### Naming Conventions

The loader will look for the main app file in this order:
1. `{folder_name}_app.py` (e.g., `chiptunez/chiptunez_app.py`) - **Preferred**
2. `app.py` (e.g., `myapp/app.py`)
3. `{folder_name}.py` (e.g., `myapp/myapp.py`)

#### Example: ChipTunez

```
applications/apps/
└── chiptunez/
    ├── chiptunez_app.py  # Main app
    ├── songs/            # Song data
    │   ├── song1.json
    │   └── song2.json
    └── README.md
```

## Benefits of Folder-Based Apps

1. **Self-contained** - All app resources in one place
2. **Easy to distribute** - Copy/delete the entire folder
3. **Git-friendly** - Can be separate repositories
4. **App store ready** - Easy to package and distribute
5. **Better organization** - Separate code from data

## Creating a Folder-Based App

1. Create a folder in the appropriate category (apps/games/tools)
2. Create your main app file following the naming convention
3. Add any resources (data, assets, etc.) to subdirectories
4. The app will be automatically discovered and loaded

## Git Submodules/Subrepos

Folder-based apps can be managed as Git submodules or subrepos:

```bash
# Add an app as a submodule
cd applications/apps
git submodule add https://github.com/user/awesome-app.git awesome_app

# Update all app submodules
git submodule update --remote
```

This allows apps to:
- Have independent version control
- Be developed separately
- Be easily shared across projects
- Receive updates independently

## App Discovery

The system automatically:
1. Scans all category directories
2. Discovers both flat files and folders
3. Imports and instantiates App subclasses
4. Displays them in the launcher menu

No configuration needed - just add your app and it appears!
