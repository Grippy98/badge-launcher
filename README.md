# Python Badge Launcher

A MicroPython-based launcher for the BeagleBadge, using LVGL (Light and Versatile Graphics Library) for the UI. This project provides a robust application launcher with games, tools, and media players.

## Prerequisites

### Hardware
- BeagleBadge (or compatible Linux-based badge device)

### OS Requirements
- Linux distribution with `systemd` (e.g., Debian)
- Display: 400x300 E-Ink display
- Input: GPIO buttons or compatible input device

### Host System Requirements (for development)
- `gcc` (for compiling asset conversion tools)
- `sshpass` (optional, for deployment scripts)

## Project Structure

```
badge-slop/
├── main.py                  # Application entry point
├── config.py                # Configuration management
├── core/                    # Framework core
│   ├── app.py              # Base app class
│   ├── app_loader.py       # Dynamic app loader
│   ├── menu.py             # Main menu interface
│   ├── statusbar.py        # Status bar (CPU, RAM, battery)
│   └── bottombar.py        # Bottom bar (network, USB)
├── applications/            # User applications
│   ├── apps/               # General applications (flat files & folders)
│   │   ├── chiptunez/     # Folder-based app example
│   │   ├── dvd_app.py     # Flat file app example
│   │   └── ...
│   ├── games/              # Games (Snake, Brick, etc.)
│   ├── settings/           # System settings
│   └── tools/              # Utilities (I2C scanner, etc.)
├── drivers/                 # Hardware drivers
│   ├── display.py          # Display driver
│   ├── input.py            # Input handling
│   ├── sound.py            # Sound/beeper driver
│   └── tty.py              # TTY management
├── lib/                     # Helper libraries
├── assets/                  # Binary assets
│   ├── *.bin               # Converted images
│   └── *.c                 # C source images
├── scripts/                 # Build and deployment
│   ├── run.sh              # Launcher script
│   ├── sync.sh             # Deploy to device
│   └── build_deb.sh        # Build debian package
├── tools/                   # Development tools
│   ├── img2bin.c           # Image converter
│   ├── convert_assets.py   # Asset conversion helper
│   └── debug_loader.py     # Debug utility
├── tests/                   # Test scripts
├── debian/                  # Debian packaging files
├── lv_micropython/         # MicroPython with LVGL (submodule)
└── libtuxdriver/           # Tux driver library (submodule)
```

## System Dependencies

### Required Packages on Device

```bash
# Basic build tools (if building MicroPython on device)
apt install -y build-essential libreadline-dev libffi-dev pkg-config

# I2C tools (for I2C Scanner application)
apt install -y i2c-tools
```

### Required Packages for Development (Linux/SDL)
```bash
sudo apt-get install libsdl2-dev cmake build-essential python3-dev python3-pip python3-venv libffi-dev
```

## Installation

### Option 1: Debian Package (Recommended)

#### 1. Build the Package

On your development machine, from the project root:

```bash
# Make sure you have the MicroPython binary
# (see "Building MicroPython" section below)

# Build the .deb package
./scripts/build_deb.sh
```

This creates `badge-launcher_<version>_arm64.deb` in the current directory.

#### 2. Install on Device

```bash
# Copy package to device
scp badge-launcher_*.deb root@<device-ip>:~

# Install on device
ssh root@<device-ip>
dpkg -i badge-launcher_*.deb

# Enable autostart
systemctl enable badge-launcher.service
systemctl start badge-launcher.service
```

The package installs to `/opt/badge_launcher` and sets up systemd autostart.

### Option 2: Manual Development Install

For active development, use the sync script to deploy directly:

#### 1. Configure sync.sh

Edit `scripts/sync.sh` and set your device information:

```bash
BADGE_IP="192.168.1.xxx"      # Your device IP
BADGE_USER="root"
BADGE_PASS="your-password"
DEST_DIR="~/badge_launcher"   # Installation directory
```

#### 2. Deploy Files

```bash
./scripts/sync.sh
```

This syncs all files to `~/badge_launcher` on the device.

#### 3. Run Manually

```bash
ssh root@<device-ip>
cd ~/badge_launcher
./scripts/run.sh
```

## Building MicroPython

The launcher requires MicroPython with LVGL bindings. Build natively on the BeagleBadge for best compatibility.

### 1. Initialize Submodules

```bash
git submodule update --init --recursive
```

### 2. Apply LVGL Binding Patch

A small patch is required for header inclusion:

```bash
sed -i 's|INC += -I$(LVGL_BINDING_DIR)|INC += -I$(LVGL_BINDING_DIR) -I$(LVGL_DIR)|' \
    lv_micropython/user_modules/lv_binding_micropython/micropython.mk
```

### 3. Build mpy-cross

On the device:

```bash
cd lv_micropython/mpy-cross
make -j$(nproc)
```

### 4. Build Unix Port with LVGL

```bash
cd ../ports/unix
make -j$(nproc) \
    USER_C_MODULES=../../user_modules \
    LV_CFLAGS="-DLV_LVGL_H_INCLUDE_SIMPLE"
```

### 5. Install Binary

```bash
# For debian package build
cp ports/unix/build-standard/micropython /path/to/badge-slop/micropython

# For manual install
cp ports/unix/build-standard/micropython ~/badge_launcher/micropython
chmod +x ~/badge_launcher/micropython
```

## Asset Conversion

Images must be converted to raw binary format for fast loading on the E-Ink display.

### 1. Build Conversion Tool

The `img2bin` tool is required for the Photos app to convert images on-the-fly.

> **Note:** The source file `tools/img2bin.c` is currently missing from the repository. Using the pre-compiled binary is recommended if available for your architecture.

```bash
# If source is available:
gcc -o img2bin tools/img2bin.c -lm -O2
```


This creates the `img2bin` binary in the project root.

### 2. Convert Images

```bash
# Basic usage (default 128x128)
./img2bin input_image.png output_file.bin

# Specify custom dimensions
./img2bin input_image.png output.bin 400 300

# Maintain aspect ratio with 'contain' mode (adds white borders)
./img2bin input_image.png output.bin 400 300 contain

# Fill the area with 'cover' mode (crops if needed)
./img2bin input_image.png output.bin 400 300 cover

# Stretch to fill (ignores aspect ratio)
./img2bin input_image.png output.bin 400 300 stretch
```

**Fit Modes:**
- `stretch` - Stretch to exact dimensions (default, ignores aspect ratio)
- `contain` - Fit inside target area, maintain aspect ratio, add white borders if needed
- `cover` - Cover target area, maintain aspect ratio, crop from center if needed

The tool:
- Resizes images to specified dimensions (default: 400x300)
- Converts to L8 (grayscale) format
- Applies Floyd-Steinberg dithering for E-Ink display
- Supports aspect ratio preservation with letterboxing/pillarboxing
- Outputs raw binary files

**Usage with Photos App:**
- Place `.jpg`, `.jpeg`, `.png`, or `.bmp` files in the `photos/` directory
- The Photos app automatically converts them to 400x300 on first view
- Uses `contain` mode to preserve aspect ratio with white borders
- Converted images are cached in `/tmp/` for fast subsequent loading within the same session
- Cache files are automatically cleaned up when you exit the Photos app

**Pre-converted Assets:**
- Place `.bin` files in the `assets/` directory for use by other apps

## Configuration

The launcher stores configuration in `config.json` in the application directory:

```json
{
  "sound_enabled": true,
  "badge_name": "Beagle\nBadge",
  "badge_info": "Linux (CES Port)\nBuild - Python",
  "badge_logo": 0
}
```

**Settings:**
- `sound_enabled`: Enable/disable beeper sounds
- `badge_name`: Name shown in Badge Mode
- `badge_info`: Info text shown in Badge Mode
- `badge_logo`: Logo preference (0=Random, 1=Beagle, 2=TI)

Configuration is editable through the Settings app or Badge Mode interface.

## Developing Apps

The badge launcher supports two app structures:

### Flat File Apps (Simple)

Create a single `.py` file in the appropriate category:

```python
# applications/apps/myapp.py
from core import app
import lvgl as lv

class MyApp(app.App):
    def __init__(self):
        super().__init__("My App")

    def enter(self, on_exit=None):
        # Your app logic here
        pass
```

### Folder-Based Apps (Advanced)

For apps with resources, data files, or multiple modules:

```
applications/apps/
└── myapp/
    ├── myapp_app.py          # Main app file
    ├── data/                 # Data files
    ├── assets/               # Images, fonts, etc.
    └── README.md             # Documentation
```

**Benefits:**
- Self-contained and portable
- Easy to distribute as Git repos
- Can be managed as Git submodules
- App store ready

**Quick Start:**

```bash
# Copy the template
cp -r applications/apps/_template_app applications/apps/myapp

# Rename the main file
cd applications/apps/myapp
mv template_app_app.py myapp_app.py

# Edit and customize
```

**See also:**
- [FOLDER_APPS_GUIDE.md](FOLDER_APPS_GUIDE.md) - Complete guide to folder-based apps
- [applications/README.md](applications/README.md) - Detailed app development docs
- [APP_STORE.md](APP_STORE.md) - App store vision and distribution
- [applications/apps/chiptunez/](applications/apps/chiptunez/) - Working example

## App Store

The badge launcher includes an integrated app store for discovering and installing community-developed apps.

### Using the App Store

1. Navigate to **Settings → App Store** on your badge
2. Browse available apps
3. Use ↑/↓ to select an app
4. Press ENTER to install
5. Restart the launcher to see new apps

### Setting Up Your Own App Store

Create a community app store repository:

```bash
# Create store repository
./scripts/create_app_store_repo.sh ../badge-app-store
cd ../badge-app-store

# Push to GitHub
git remote add origin https://github.com/YOUR_ORG/badge-app-store.git
git push -u origin main
```

### Adding Apps to the Store

```bash
# Validate your app first
./scripts/validate_app.sh ../my-awesome-app

# Add to store
./scripts/add_app_to_store.sh \
    ../badge-app-store \
    my-app \
    https://github.com/user/my-app-repo.git \
    "My Awesome App" \
    "Your Name" \
    "Description of the app" \
    "tools" \
    "1.0.0"

# Push changes
cd ../badge-app-store
git push
```

### Configuring the App Store

Update the store URLs in [applications/tools/app_store_app.py](applications/tools/app_store_app.py):

```python
self.store_repo = "https://github.com/YOUR_ORG/badge-app-store.git"
self.manifest_url = "https://raw.githubusercontent.com/YOUR_ORG/badge-app-store/main/manifest.json"
```

**Documentation:**
- [APP_STORE_SETUP.md](APP_STORE_SETUP.md) - Complete setup and management guide
- [APP_SUBMISSION_GUIDE.md](APP_SUBMISSION_GUIDE.md) - Quick guide for app developers
- Learn about store architecture, app submission, and best practices

**Technical Details:**
- Uses git submodules for version control
- Apps are downloaded on-demand
- Each app has metadata (name, version, author, category)
- Supports automatic dependency checking
- Apps install to `applications/apps/{app-id}/`

## Running the Launcher

### Autostart via systemd

The debian package automatically sets up systemd integration:

```bash
# Check status
systemctl status badge-launcher.service

# Stop service
systemctl stop badge-launcher.service

# Start service
systemctl start badge-launcher.service

# Disable autostart
systemctl disable badge-launcher.service

# View logs
journalctl -u badge-launcher.service -f
```

### Manual Launch

```bash
cd /opt/badge_launcher  # or ~/badge_launcher
./scripts/run.sh
```

The launcher will:
1. Kill any existing MicroPython instances
2. Disable the framebuffer cursor
3. Clear the screen
4. Launch the application

## Development

### Creating New Applications

1. Create a new Python file in the appropriate `applications/` subdirectory:
   - `applications/apps/` - General applications
   - `applications/games/` - Games
   - `applications/tools/` - Utilities
   - `applications/settings/` - Settings screens

2. Import the base app class:

```python
import sys
if "core" not in sys.path: sys.path.append("core")
from core import app
import lvgl as lv

class MyApp(app.App):
    def __init__(self):
        super().__init__("My App Name")

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        # Create your UI here

    def exit(self):
        # Clean up resources
        pass
```

3. The app will be automatically discovered by `core/app_loader.py` and appear in the menu.

### File Organization

- **Keep apps self-contained** - Each app should be in a single file
- **Use relative paths** - Assets in `assets/`, drivers in `drivers/`
- **Follow naming conventions** - Apps end with `_app.py`
- **Handle cleanup** - Always implement the `exit()` method

### Version Management

The application version is managed centrally through the `VERSION` file at the project root. This version is automatically displayed in the menu and synced with the debian package.

#### Updating the Version

Use the provided script to update the version across all files:

```bash
./scripts/update_version.sh 1.0.1
```

This will:
- Update the `VERSION` file
- Prepend a new entry to `debian/changelog`
- Display instructions for committing and tagging

#### Manual Version Update

If you prefer to update manually:

1. Edit the `VERSION` file:
   ```bash
   echo "1.0.1" > VERSION
   ```

2. Update `debian/changelog`:
   ```bash
   dch -v 1.0.1 "Your changelog message"
   # OR manually edit debian/changelog
   ```

3. The version will automatically appear in the menu on next launch

The version is loaded by [config.py](config.py) and displayed in [core/menu.py](core/menu.py).

## Troubleshooting

### Input Not Working

The launcher reads from `/dev/input/event*` devices. Ensure proper permissions:

```bash
# Check input devices
ls -l /dev/input/event*

# Run as root or add user to input group
usermod -aG input <username>
```

### MicroPython Import Errors

If you see "ImportError" for `lvgl`:

1. Verify MicroPython was built with LVGL bindings
2. Check that the patch was applied to `micropython.mk`
3. Rebuild with `USER_C_MODULES` flag

### Images Not Loading

1. Ensure images were converted using `img2bin`
2. Check that `.bin` files are in `assets/` directory
3. Verify file permissions (should be readable)

### Display Issues

If the display shows artifacts or doesn't refresh:

- The launcher uses E-Ink refresh sweeps to clear ghosting
- Check that `/dev/fb0` exists and is accessible
- Verify the display driver is loaded

### Service Won't Start

Check systemd logs:

```bash
journalctl -u badge-launcher.service -n 50
```

Common issues:
- Missing `micropython` binary
- Wrong working directory
- Missing dependencies

## Features

### Main Menu
- Logo display (TI/Beagle, configurable)
- Category-based app organization
- Status bar with system info
- Bottom bar with network status

### Badge Mode
- Customizable name and info display
- Logo selection (Random, TI, Beagle)
- Editable via on-screen keyboard
- Configuration persistence

### Built-in Apps
- **Media**: Image viewer, music player
- **Games**: Snake, Brick
- **Tools**: I2C scanner, serial monitor
- **Settings**: WiFi, Bluetooth, system info

### System Integration
- Real-time CPU/RAM monitoring
- Battery status display
- Network status (Ethernet/WiFi)
- USB device detection

## License

See LICENSE file for details.

## Credits

- LVGL Graphics Library: https://lvgl.io
- MicroPython: https://micropython.org
- BeagleBoard.org Foundation
