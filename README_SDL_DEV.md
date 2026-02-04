# Badge Launcher - SDL Development Mode

This guide explains how to run and test the Badge Launcher on macOS (or Linux desktop) using SDL for development.

## Why SDL Mode?

SDL mode allows you to:
- Test UI changes without deploying to physical badge
- Rapid iteration during development
- Debug with full Python tooling
- See visual feedback in a desktop window
- Use mouse and keyboard for testing

## Setup

### macOS (Automated Build from Source)

```bash
# Run the automated setup script (builds LVGL from source)
./setup_mac_dev.sh
```

This script will:
1. Install SDL2, cmake, and build tools via Homebrew
2. Clone LVGL Python bindings repository
3. Build LVGL with SDL support (takes 5-10 minutes)
4. Install MicroPython with LVGL or Python LVGL module

### Linux

```bash
sudo apt-get install libsdl2-dev cmake build-essential
./setup_mac_dev.sh  # Same script works on Linux
```

## Running

If you built LVGL with the setup script (Python module in venv):

```bash
# Activate the virtual environment
source ~/.lvgl_build/venv/bin/activate

# Run the launcher
python main_sdl.py
```

If you built MicroPython with LVGL:

```bash
micropython-lvgl main_sdl.py
```

A window will open showing the Badge Launcher UI.

## Controls

| Input | Action |
|-------|--------|
| Arrow Keys | Navigate menu/games |
| Enter | Select/Confirm |
| Escape | Back/Exit |
| Mouse | Click to interact |

## What's Mocked?

The SDL version automatically mocks these Linux-specific features:

### Hardware
- `/dev/fb0` → SDL window
- `/dev/input/event*` → SDL keyboard/mouse
- System beeper → Console output (🔊♪♫♬)

### System Files
- `/proc/stat` → Fake CPU stats
- `/proc/meminfo` → Fake memory stats
- `/sys/class/power_supply/` → Fake battery (75-100%)

### Network
- `nmcli` / `iwgetid` → Mock WiFi "MockWiFi" @ 192.168.1.100
- `bluetoothctl` → Mock Bluetooth (powered on)
- `lsusb` → Mock USB devices

### TTY
- `stty` commands → No-op (silent)

## Differences from Badge

1. **Display**: Color SDL window vs. E-Ink grayscale
2. **Resolution**: 400x300 (configurable in main_sdl.py)
3. **Refresh**: Instant vs. E-Ink refresh delays
4. **Input**: Keyboard/mouse vs. physical buttons
5. **Sound**: Console indicators vs. actual beeps

## Development Workflow

1. Edit code on Mac
2. Test in SDL mode: `python3 main_sdl.py`
3. Iterate quickly
4. Deploy to badge for final hardware testing

## Customization

Edit `main_sdl.py` to change:

```python
# Display resolution
WIDTH = 400
HEIGHT = 300

# Mock data values (CPU, RAM, battery, etc.)
# See mock_open() and mock_popen() functions
```

## Troubleshooting

### SDL not found
```bash
# Ensure SDL2 is installed
brew list sdl2  # macOS
dpkg -l | grep libsdl2  # Linux
```

### LVGL import error
```bash
pip3 install --upgrade lvgl
```

### Window doesn't appear
Check for error messages. Ensure no other application is using SDL.

### Apps not loading
Verify `applications/` directory structure:
```
applications/
├── apps/          (Photos, ChipTunez, etc.)
├── games/         (Snake, Brick)
├── settings/      (WiFi, Bluetooth, etc.)
└── tools/         (I2C Scanner, etc.)
```

## Known Limitations

1. **No actual I2C/SPI**: Hardware tools will show mock data
2. **No real WiFi/BT**: Network apps show simulated connections
3. **Photos app**: Requires actual image files in `photos/` directory
4. **System apps**: Show mocked system information

## See Also

- [README.md](README.md) - Badge hardware deployment
- [test_apps_mac.py](test_apps_mac.py) - Simple import testing without UI
