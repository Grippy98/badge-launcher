"""Dynamic application loader for Badge Launcher.

Discovers and loads applications from the applications/ directory,
organized by category (apps, games, tools, settings).
"""

import os
import sys
from . import app

# Default category display order (case-insensitive)
DEFAULT_CATEGORY_ORDER = ["apps", "demos", "games", "tools", "settings"]

# Settings apps display order
SETTINGS_ORDER = ["WiFi", "Bluetooth", "Sound", "About", "Reboot", "Shutdown"]


def load_categories(root_path="./applications"):
    """Scans for valid category directories.

    Args:
        root_path: Path to applications directory

    Returns:
        List of category names in sorted order
    """
    cats = []

    # Check if root path exists
    try:
        os.stat(root_path)
    except:
        return []

    try:
        for entry in os.listdir(root_path):
            # Skip hidden files and __pycache__
            if entry.startswith(".") or entry.startswith("__"):
                continue

            # Check if directory
            try:
                st = os.stat(f"{root_path}/{entry}")
                if st[0] & 0x4000:  # S_IFDIR bit
                    cats.append(entry)
            except:
                continue

    except:
        return []

    # Sort by predefined order (case-insensitive), then alphabetically
    def sort_key(category):
        cat_lower = category.lower()
        if cat_lower in DEFAULT_CATEGORY_ORDER:
            return (0, DEFAULT_CATEGORY_ORDER.index(cat_lower))
        return (1, category)

    cats.sort(key=sort_key)
    return cats


def load_app_from_module(mod_name, mod):
    """Helper function to find and instantiate App subclasses from a module.

    Args:
        mod_name: Name of the module (for error reporting)
        mod: The imported module object

    Returns:
        List of instantiated App objects found in the module
    """
    apps = []
    try:
        # Find and instantiate App subclasses
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            try:
                # Check if it's a class and subclass of App
                if (isinstance(attr, type) and
                    issubclass(attr, app.App) and
                    attr is not app.App):
                    # Instantiate the app
                    apps.append(attr())
            except TypeError:
                # Not a class, skip
                continue
    except Exception as e:
        print(f"Failed to process {mod_name}: {e}")

    return apps


def load_apps_from_category(category_name):
    """Scans a category folder and imports app classes.

    Supports two app structures:
    1. Flat files: app_name.py directly in the category folder
    2. Folder-based: app_name/{app_name}_app.py or app_name/app.py

    Args:
        category_name: Name of the category directory

    Returns:
        List of instantiated App objects
    """
    apps = []
    path = f"./applications/{category_name}"

    # Check if path exists
    try:
        os.stat(path)
    except:
        return []

    # Add category to path for imports
    if path not in sys.path:
        sys.path.append(path)

    try:
        for entry in os.listdir(path):
            # Skip hidden files and __pycache__
            if entry.startswith(".") or entry.startswith("__"):
                continue

            entry_path = f"{path}/{entry}"

            # Check if entry is a file or directory
            try:
                st = os.stat(entry_path)
                is_dir = st[0] & 0x4000  # S_IFDIR bit
            except:
                continue

            if is_dir:
                # Skip directories starting with underscore (templates, etc.)
                if entry.startswith("_"):
                    continue

                # Folder-based app: look for {folder_name}_app.py or app.py
                app_dir_path = entry_path

                # Add app directory to path
                if app_dir_path not in sys.path:
                    sys.path.append(app_dir_path)

                # Try multiple naming conventions
                entry_underscore = entry.replace("-", "_")
                possible_names = [
                    f"{entry}_app.py",
                    f"{entry_underscore}_app.py",
                    "app.py",
                    f"{entry}.py",
                    f"{entry_underscore}.py"
                ]

                loaded = False
                for app_file in possible_names:
                    app_file_path = f"{app_dir_path}/{app_file}"
                    try:
                        os.stat(app_file_path)
                        # File exists, try to load it
                        mod_name = app_file[:-3]  # Remove .py

                        try:
                            # Dynamic import
                            mod = __import__(mod_name)
                            apps.extend(load_app_from_module(mod_name, mod))
                            loaded = True
                            break
                        except Exception as e:
                            print(f"Failed to load {entry}/{app_file}: {e}")
                    except:
                        # File doesn't exist, try next convention
                        continue

                if not loaded:
                    print(f"Warning: No app file found in {entry}/ (tried {', '.join(possible_names)})")

            elif entry.endswith(".py") and not entry.startswith("_"):
                # Flat file app: app_name.py
                mod_name = entry[:-3]

                try:
                    # Dynamic import
                    mod = __import__(mod_name)
                    apps.extend(load_app_from_module(mod_name, mod))
                except Exception as e:
                    print(f"Failed to load {mod_name}: {e}")

    except Exception as e:
        print(f"Error loading category '{category_name}': {e}")

    # Sort settings apps in specific order
    if category_name.lower() == "settings":
        apps.sort(key=lambda x: (
            SETTINGS_ORDER.index(x.name)
            if hasattr(x, "name") and x.name in SETTINGS_ORDER
            else 999
        ))

    return apps
