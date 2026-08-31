# BeagleBadge Launcher — CPython experimental

This branch is a standard-Python rewrite of the Linux launcher for the 400 × 300 BeagleBadge. Apps build a small declarative UI with `badge_sdk`; the launcher renders it with Pillow and sends the same frame to the Linux framebuffer, a pygame desktop window, or an in-memory test backend.

The public app API does not expose framebuffer, pygame, or device-specific drawing code. A basic app is one class with a `view()` method:

```python
from badge_sdk import App, Column, Screen, Text


class HelloBadge(App):
    app_id = "hello-badge"
    name = "Hello Badge"

    def view(self):
        return Screen(Column(Text("Hello, badge!", align="center", flex=1)), title=self.name)
```

See [App development](docs/APP_DEVELOPMENT.md) and the complete [Hello Badge example](examples/hello_badge).

## What is included

- Launcher categories, system status, Badge Mode, and Armbian first-boot onboarding
- App Store with schema-v2 manifest validation, staged installs, updates, rollback support, and lazy app imports
- Wi-Fi, Bluetooth, sound, reboot, shutdown, I2C scanner, serial monitor, file manager, RGB LED, and BadgeBeam tools
- Snake and Brick Breaker
- Linux framebuffer and evdev backends for the badge
- pygame-ce desktop simulation and an in-memory headless screenshot backend

The first-party apps under `builtin_apps/` have been rewritten for CPython and the public SDK. Old store entries using the v1 MicroPython/LVGL contract remain identifiable in the catalog, but the CPython launcher marks them **Port Required** and does not install or run them.

## Desktop quick start

Python 3.11 or newer is required.

```bash
python3 -m venv .venv-cpython
source .venv-cpython/bin/activate
python -m pip install -e '.[desktop,test]'
badge-launcher --backend desktop --skip-onboarding
```

Desktop controls:

| Key | Action |
| --- | --- |
| Arrow keys | Navigate |
| Enter | Select |
| Escape | Back |
| Backspace | Delete text |
| Printable keys | Enter text |

Desktop mode does not enable evdev or serial input and disables tone output. Command-backed screens and discoverable sysfs capabilities still reflect the development host and may report that their Linux tools are unavailable; they are not populated with fake device data.

For a non-interactive render suitable for CI:

```bash
badge-launcher --backend headless --frames 1 \
  --screenshot /tmp/beaglebadge-launcher.png \
  --no-hardware --skip-onboarding
```

Run the unit suite with:

```bash
python -m pytest
```

Create and preview a new app without writing a manifest by hand:

```bash
badge-app new /tmp/my-first-badge-app --name "My First App"
badge-app run /tmp/my-first-badge-app
badge-app validate /tmp/my-first-badge-app
```

The generator writes just `badge-app.json` and one ordinary Python module. For
automated UI tests, `badge_sdk.testing.AppHarness` drives the real runtime with
logical button events and exposes the resulting 400 × 300 Pillow image.

## Install on the badge

Build the arm64 Debian package from the repository root:

```bash
./scripts/build_deb.sh
```

Copy the resulting `badge-launcher_<version>_arm64.deb` to the badge, then install and start it:

```bash
sudo apt install ./badge-launcher_<version>_arm64.deb
sudo systemctl enable --now badge-launcher.service
```

The service runs `main.py` with the framebuffer backend from `/usr/lib/badge-launcher`. Persistent state is stored in `/var/lib/badge-launcher`. On an Armbian image, the launcher shows its joystick-driven onboarding only while `/root/.not_logged_in_yet` exists, then delegates account setup to Armbian's first-login tooling.

For a manual hardware run from a checkout:

```bash
sudo BADGE_DATA_DIR=/var/lib/badge-launcher \
  python3 main.py --backend framebuffer
```

Useful runtime options include `--framebuffer`, `--data-dir`, `--no-hardware`, `--frames`, and `--screenshot`; run `badge-launcher --help` for the complete list.

Hardware paths can be overridden with these environment variables:

| Variable | Purpose |
| --- | --- |
| `BADGE_FRAMEBUFFER` | Framebuffer path; default `/dev/fb0` |
| `BADGE_FB_INVERT` | Set to `1` when framebuffer polarity is inverted |
| `BADGE_FULL_REFRESH_CYCLE` | Enable or disable the black/white full-refresh cycle |
| `BADGE_INPUT_DEVICES` | Colon-separated evdev paths |
| `BADGE_SOUND_DEVICE` | Override the discovered Linux EV_SND device |
| `BADGE_SERIAL_DEVICE` | Serial monitor device; default `/dev/ttyS0` |
| `BADGE_RGB_LED` | RGB LED sysfs directory |
| `BADGE_DATA_DIR` | Persistent launcher data root |
| `BADGE_FILES_ROOT` | Optional File Manager root; defaults to its app data directory |
| `BADGE_BATTERY_SUPPLY` | Preferred battery power-supply name; default `bq27541-0` |
| `BADGE_ALLOW_ROOT_APPS` | Unsafe opt-in for reviewed third-party apps in the root service |
| `BADGEBEAM_ADVERTISING` | `auto`, `bluez`, `external`, or experimental `legacy-mgmt` |
| `BADGEBEAM_CONTROLLER` | Controller hint used by BadgeBeam auto mode; package sets `cc33xx` |

BadgeBeam runs as the separate `badgebeam-receiver.service` so a Bluetooth
failure cannot take down the UI. Advertising is deliberately configurable
because the badge's CC33xx controller has a known BlueZ extended-advertising
regression; see `/etc/default/badgebeam-receiver`. The packaged default avoids
that unvalidated path and keeps the GATT receiver available for an external
legacy advertiser. An opt-in `legacy-mgmt` mode is included for device testing,
but is not selected or claimed working until it has been validated on the
shipping Linux image. It owns a reserved advertising instance using argv-only
`btmgmt add-adv`/`rm-adv` calls and deliberately does not request a secondary
PHY; configure the instance in `/etc/default/badgebeam-receiver` before testing.

## Persistent data

Without `BADGE_DATA_DIR`, development runs use `~/.local/share/beaglebadge`:

```text
beaglebadge/
├── settings.json
├── app-data/<app-id>/
├── installed-apps/
└── store-cache/
```

Each app receives its own writable directory as `self.context.data_dir`; bundled resources are available as `self.context.resources`. Uninstalling an app removes its installed code but intentionally leaves its external app data.

Badge Mode loads ordinary PNG, JPEG, BMP, or GIF profile images from `app-data/badge-mode/profile_images/`. On the packaged service that is `/var/lib/badge-launcher/app-data/badge-mode/profile_images/`; for a normal development user it is beneath `~/.local/share/beaglebadge`.

## Project layout

| Path | Responsibility |
| --- | --- |
| `badge_sdk/` | Stable imports used by applications |
| `badge_ui/` | Runtime, Pillow renderer, and display backends |
| `badge_platform/` | Linux capabilities, settings, manifests, and store transactions |
| `builtin_apps/` | Trusted first-party launcher and applications |
| `examples/hello_badge/` | Minimal schema-v2 third-party app |
| `tests/unit/` | SDK, renderer, platform, launcher, and app tests |
| `debian/`, `scripts/` | Device packaging and services |

The design and package boundaries are described in [Architecture](docs/ARCHITECTURE.md).

## App trust and compatibility

Installed schema-v2 apps execute **in the launcher process** and are not
sandboxed. The packaged launcher still needs root for the display and hardware,
so it refuses to launch third-party apps while its effective user is root. This
check happens before app Python is imported. For development, run the launcher
as a normal user. `BADGE_ALLOW_ROOT_APPS=1` is an explicit unsafe escape hatch
for reviewed code; enabling it grants that app unrestricted root execution.

Manifest validation, traversal checks, compatibility checks, shell-free command
invocation, and staged installation reduce accidental and catalog-input risks,
but do not make Python from an untrusted repository safe.

Manifest `permissions` are declarations, not an enforced permission sandbox.
Python, SDK, minimum-launcher, UI, and execution compatibility are enforced at
install and launch. The current launcher does not configure a dependency
installer, so an app that declares extra Python or system dependencies is
stopped with a clear dependency-setup requirement instead of modifying the
system automatically.

This branch is intentionally incompatible with executable v1 apps. Port them to a schema-v2 entry point that returns a `badge_sdk.App`; see [Porting a v1 app](docs/APP_DEVELOPMENT.md#porting-a-v1-app).

## License

Badge Launcher is licensed under GPL-2.0-only. See [LICENSE](LICENSE).
