"""Configuration management for Badge Launcher.

Handles loading and saving user preferences including sound settings,
badge name/info, and logo selection. Configuration is stored in JSON format.
"""

import json
import os

# Use relative path - works for both /opt/badge_launcher and ~/badge_launcher
# run.sh sets the working directory to APP_DIR before launching
CONFIG_FILE = "config.json"
VERSION_FILE = "VERSION"

# Defaults
sound_enabled = True
badge_name = "Beagle\nBadge"
badge_info = "Linux (CES Port)\nBuild - Python"
badge_logo = 0 # 0: Random, 1: Beagle, 2: TI
badge_qr_link = "https://beagleboard.org"
version = "1.0.0"  # Default fallback

def load_version():
    """Load version from VERSION file.

    Returns:
        Version string, or default if file doesn't exist
    """
    try:
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    except:
        return "1.0.0"

def load():
    """Load configuration from JSON file.

    Reads config.json and updates global configuration variables.
    Also loads version from VERSION file.
    Silently fails if file doesn't exist (uses defaults).
    """
    global sound_enabled, badge_name, badge_info, badge_logo, badge_qr_link, version
    try:
        # Simple existence check by opening for read
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            sound_enabled = data.get("sound_enabled", True)
            badge_name = data.get("badge_name", "Beagle\nBadge")
            badge_info = data.get("badge_info", "Linux (CES Port)\nBuild - Python")
            badge_logo = data.get("badge_logo", 0)
            badge_qr_link = data.get("badge_qr_link", "https://beagleboard.org")
    except:
        # File likely missing
        pass

    # Load version from VERSION file
    version = load_version()

def save():
    """Save current configuration to JSON file.

    Writes all configuration variables to config.json and syncs to disk.
    Prints error message if save fails.
    """
    try:
        with open(CONFIG_FILE, 'w') as f:
            data = {
                "sound_enabled": sound_enabled,
                "badge_name": badge_name,
                "badge_info": badge_info,
                "badge_logo": badge_logo,
                "badge_qr_link": badge_qr_link
            }
            json.dump(data, f)
            # Ensure it's written to disk
            f.flush()
        try:
            os.sync()
        except AttributeError:
            pass
    except Exception as e:
        print(f"Error saving config: {e}")

# Load configuration on module import
load()
