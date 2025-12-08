import json
import os

# Use absolute path to avoid WD issues
CONFIG_DIR = "/root/badge_launcher"
CONFIG_FILE = CONFIG_DIR + "/config.json"

# Defaults
sound_enabled = True
badge_name = "Beagle\nBadge"
badge_info = "Linux (CES Port)\nBuild - Python"
badge_logo = 0 # 0: Random, 1: Beagle, 2: TI

def load():
    global sound_enabled, badge_name, badge_info, badge_logo
    try:
        # Simple existence check by opening for read
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            sound_enabled = data.get("sound_enabled", True)
            badge_name = data.get("badge_name", "Beagle\nBadge")
            badge_info = data.get("badge_info", "Linux (CES Port)\nBuild - Python")
            badge_logo = data.get("badge_logo", 0)
    except:
        # File likely missing
        pass

def save():
    try:
        with open(CONFIG_FILE, 'w') as f:
            data = {
                "sound_enabled": sound_enabled,
                "badge_name": badge_name,
                "badge_info": badge_info,
                "badge_logo": badge_logo
            }
            json.dump(data, f)
            # Ensure it's written to disk
            f.flush()
            os.sync()
            # print(f"Config saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"Error saving config: {e}")

load()
