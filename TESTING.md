# Badge Launcher - Testing Guide

Multiple testing approaches for development without physical hardware.

## Quick Testing (No Build Required)

### 1. Import/Instantiation Test
Fastest way to verify apps load correctly:

```bash
python3 test_apps_sdl.py
```

Tests that all apps can be imported and instantiated without errors.

### 2. Logic Testing
Tests app logic, game mechanics, and state management:

```bash
# Test all apps
python3 test_logic_sdl.py

# Test specific app
python3 test_logic_sdl.py snake
python3 test_logic_sdl.py chiptunez

# Verbose output with full tracebacks
python3 test_logic_sdl.py --verbose
```

**What it tests:**
- App instantiation
- State management (Snake movement, Brick collision, etc.)
- Game logic (scoring, collision detection)
- Configuration loading
- Basic UI setup

**What it doesn't test:**
- Actual display rendering
- Real hardware I/O (buttons, display, sound)
- Timing-sensitive behavior

## Full UI Testing (Requires Build)

### Setup SDL Environment

```bash
./setup_mac_dev.sh
```

This builds LVGL from source with SDL support (takes 5-10 minutes).

### Run with SDL Display

```bash
# If using Python LVGL module (installed in venv)
source ~/.lvgl_build/venv/bin/activate
python main_sdl.py

# Or using MicroPython with LVGL
micropython-lvgl main_sdl.py
```

Opens a window showing the actual Badge UI with full interactivity.

**Features:**
- Visual display in SDL window
- Mouse and keyboard input
- All apps fully functional
- Mocked system stats and hardware

## Testing on Physical Badge

### Deploy and Test

```bash
# Copy files to badge
scp -r * debian@badge.local:/home/debian/badge-slop/

# SSH into badge
ssh debian@badge.local

# Run
cd badge-slop
micropython main.py
```

## Test Results

Current test status (as of last run):

```
✓ Snake: PASSED (state management, movement logic)
✓ Brick Breaker: PASSED (collision detection, 110 bricks)
✓ ChipTunez: PASSED (9 songs loaded)
✓ Photos: PASSED (handles missing images gracefully)
✗ DVD Screensaver: Edge case with screen size calculations
✓ Badge Mode: PASSED (logo modes, config access)
✓ About: PASSED (info screen)

Overall: 6/7 passing (86%)
```

## CI/CD Integration

The logic tests can be integrated into CI/CD:

```yaml
# .github/workflows/test.yml
name: Test Badge Apps
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: python3 test_logic_sdl.py
```

## Development Workflow

1. **Quick Iteration**: Edit code → Run `python3 test_logic_sdl.py` → Fix issues
2. **Visual Check**: Run `python3 main_sdl.py` (if SDL is set up)
3. **Final Validation**: Deploy to physical badge for hardware testing

## Troubleshooting

### Test Failures

If tests fail, run with `--verbose` to see full tracebacks:

```bash
python3 test_logic_sdl.py snake --verbose
```

### Missing Mock Functions

If you see `AttributeError` for missing LVGL functions, add them to [test_logic_sdl.py](test_logic_sdl.py) in the `MockLVGL` class.

### SDL Build Failures

See [README_SDL_DEV.md](README_SDL_DEV.md) for SDL-specific troubleshooting.

## Adding Tests for New Apps

When creating a new app, add it to the test suite:

```python
# In test_logic_mac.py
test_apps = [
    # ... existing apps ...
    ("My New App", "apps.my_new_app", "MyNewApp", "Description"),
]
```

Then add app-specific logic tests:

```python
elif "My New App" in name:
    # Test specific functionality
    assert app_instance.some_state == expected_value
    print(f"  ✓ Custom test passed")
```

## See Also

- [README.md](README.md) - Main project documentation
- [README_SDL_DEV.md](README_SDL_DEV.md) - SDL development setup
- [test_apps_sdl.py](test_apps_sdl.py) - Simple import tester
- [test_logic_sdl.py](test_logic_sdl.py) - Logic test suite
- [main_sdl.py](main_sdl.py) - SDL launcher for visual testing
