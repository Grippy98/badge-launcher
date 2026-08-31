# App development

A portable BeagleBadge app needs two files. The generator creates both:

```bash
badge-app new /tmp/my-badge-app --name "My Badge App"
badge-app run /tmp/my-badge-app
```

```text
my-app/
├── badge-app.json
└── my_app.py
```

You can also start by copying the working example:

```bash
cp -R examples/hello_badge /tmp/my-badge-app
python examples/preview_app.py /tmp/my-badge-app
```

Edit the manifest, change the class, and use the arrow keys and Enter in the preview window. No cross-compiler, generated C asset, or badge deployment is required for normal UI iteration.

## The smallest useful app

```python
from badge_sdk import App, Button, Column, Screen, Text


class HelloBadge(App):
    app_id = "hello-badge"
    name = "Hello Badge"
    category = "apps"

    def __init__(self):
        super().__init__()
        self.message = "Hello, badge!"

    def change_message(self):
        self.message = "You pressed the button."
        self.invalidate()

    def view(self):
        return Screen(
            Column(
                Text(self.message, size=22, align="center", flex=1),
                Button("Say hello", self.change_message),
                padding=12,
            ),
            title=self.name,
            footer="ENTER: greet  BACK: exit",
        )
```

An app owns ordinary Python state. `view()` describes what should be on screen for the current state. Callbacks update the state; `view()` is called again when the runtime redraws.

The matching `badge-app.json` is:

```json
{
  "schema_version": 2,
  "id": "hello-badge",
  "name": "Hello Badge",
  "version": "1.0.0",
  "category": "apps",
  "entry_point": "hello_badge:HelloBadge",
  "description": "A minimal portable BeagleBadge app",
  "author": "Your Name",
  "license": "MIT",
  "requires_python": ">=3.11",
  "requires_sdk": ">=1.0,<2",
  "permissions": []
}
```

The entry point is `module:object`. The object may be an `App` class or a no-argument factory, but calling it must return a `badge_sdk.App`.

## Preview and validate

Install the repository's development dependencies once:

```bash
python3 -m venv .venv-cpython
source .venv-cpython/bin/activate
python -m pip install -e '.[desktop,test]'
```

Open an app in the desktop simulator without installing it:

```bash
badge-app run path/to/my-app
```

Render one frame without opening a window:

```bash
badge-app screenshot path/to/my-app /tmp/my-app.png
```

`examples/preview_app.py` provides the same preview flow when working directly
from a source checkout without installing the `badge-app` command.

The preview uses the same manifest loader, app loader, runtime, and Pillow renderer as the launcher. It does not enable the main evdev, serial, or tone-output paths and gives the app a temporary data directory. Other host capabilities are not simulated. A successful preview proves that the manifest and entry point load and that the first screen renders; it does not replace testing hardware-oriented behavior on a badge.

## Test an app without hardware

`AppHarness` uses the real renderer, focus logic, and in-memory backend. This
keeps an interaction test small and makes its final screen available as an
ordinary Pillow image:

```python
from badge_sdk import Action
from badge_sdk.testing import AppHarness
from hello_badge import HelloBadge


def test_greeting(tmp_path):
    with AppHarness(HelloBadge()) as badge:
        badge.press(Action.SELECT)
        assert badge.app.message == "You pressed the button."
        badge.screenshot(tmp_path / "greeting.png")
```

Use `press()` with an `Action` or its lowercase name, `type()` for desktop text
input, `events()` for explicit `InputEvent` sequences, and `step()` for timer or
background-work tests. The harness creates isolated temporary app data unless
you pass `data_root=`.

## Components

Import components from `badge_sdk`, never from `badge_ui` or a backend.

| Component | Use |
| --- | --- |
| `Screen` | Top-level body, optional title, footer, status overlay, and full-refresh request |
| `Column`, `Row` | Layout with `gap`, `padding`, fixed dimensions, or `flex` |
| `Text`, `Spacer`, `Rule`, `Box` | Basic content and grouping |
| `Button` | One focusable action |
| `Menu`, `MenuItem` | Scrollable choices with label, detail, enabled state, and callback |
| `TextInput` | Physical-keyboard text entry |
| `Keyboard` | Joystick-driven on-screen keys |
| `Image` | PNG, JPEG, BMP, GIF, Pillow image, or explicitly described raw bytes |
| `QRCode` | QR image from a string |
| `Progress` | Value from `0.0` to `1.0` with an optional label |
| `Canvas` | Advanced custom drawing callback |

Most components accept `width`, `height`, `flex`, `visible`, and an optional `key`. Give interactive components stable, unique keys when a screen has several of them; the runtime uses keys to preserve focus while `view()` creates a new tree.

`Canvas` receives the current Pillow `ImageDraw` object and `(x0, y0, x1, y1)` bounds. It is useful for games and specialized graphics, but it couples that drawing callback to the current renderer. Prefer the standard components for the easiest future portability.

## Menus and navigation

```python
from badge_sdk import Menu, MenuItem

menu = Menu(
    [
        MenuItem("First choice", self.choose_first),
        MenuItem("Unavailable", lambda: None, enabled=False),
    ],
    selected=self.selected,
    on_change=lambda value: setattr(self, "selected", value),
)
```

The runtime handles focus, Up/Down movement, Select activation, and Back navigation. In a `Menu`, Up/Down changes the selected row and Left/Right moves to a sibling control. An on-screen `Keyboard` uses all four directions inside its grid; moving above its first row or below its final row yields focus to the neighboring control. Physical typing targets the screen's `TextInput` even while the on-screen keyboard is focused.

Override `handle(event)` only for app-level controls such as a game's direction keys:

```python
from badge_sdk import Action

def handle(self, event):
    if event.action == Action.LEFT:
        self.move_left()
        return True
    return False
```

Return `True` when the app consumed the event. App-facing actions are `UP`,
`DOWN`, `LEFT`, `RIGHT`, `SELECT`, `BACK`, `TEXT`, and `DELETE`. `QUIT` is a
backend/runtime action used when a desktop window closes; apps normally should
not intercept it.

## Lifecycle and context

`App` provides five hooks:

- `on_start()` — the context is attached and the app just became active.
- `view()` — return the current `Screen`; keep it quick and free of blocking I/O.
- `handle(event)` — optionally intercept input before focused-component handling.
- `on_resume()` — a child app closed and this app is visible again.
- `on_stop()` — cancel app-owned work and release resources.

Navigate without importing launcher internals:

```python
self.context.open(AnotherApp())
self.context.replace(AnotherApp())
self.context.exit()
```

The convenience method `self.close()` also exits the current app.

## Files and resources

Use `self.context.data_dir` for writable state. It is created automatically and remains separate from installed code:

```python
import json

path = self.context.data_dir / "state.json"
path.write_text(json.dumps({"score": self.score}) + "\n", encoding="utf-8")
```

Use `self.context.resources` for read-only files shipped beside the module:

```python
from badge_sdk import Image

logo = Image(self.context.resources / "logo.png", width=96, height=96)
```

Do not write beside the app module or assume the process working directory. For app-specific preferences, keep a file in `data_dir`; `context.services.settings` contains the launcher's fixed settings keys and is not a general third-party settings database.

## Timers and slow work

Do not run network scans, subprocesses, or slow hardware I/O in `view()` or directly in an input callback.

```python
def on_start(self):
    self.status = "Loading…"
    self.context.run_background(self.load_data, done=self.loaded)

def loaded(self, future):
    try:
        self.items = future.result()
        self.status = ""
    except Exception as error:
        self.status = str(error)
    self.invalidate()
```

`run_background()` uses the launcher's worker pool. Its `done` callback is delivered back on the UI loop. For scheduled UI work, use `call_later(seconds, callback)` or `call_every(seconds, callback)`. The context cancels outstanding timers automatically when an app exits; retain the returned handle when you need to cancel one earlier.

## Hardware services

Hardware belongs behind `self.context.services` so an app can report a missing capability instead of failing during import. Current services include:

| Service | Representative operations |
| --- | --- |
| `system` | `status()`, `about()`, `reboot()`, `poweroff()` |
| `network` | `wifi_devices()`, `scan()`, `connect()`, `disconnect()` |
| `bluetooth` | `scan()`, `connect()` |
| `i2c` | `buses()`, `scan(bus)` |
| `led` | `available`, `set()`, `rainbow()`, `off()` |
| `sound` | `enabled`, `beep()`, `start()`, `stop()` |
| `serial` | `available`, `read()` when hardware mode is active |

These are launcher implementation APIs rather than the portable UI contract. Check availability, catch operational errors, and keep device access in background work where it may block. If a reusable capability is missing, add it to `badge_platform` instead of hard-coding a device path in each app.

## E-paper-friendly updates

Normal input handling redraws after a callback. Call `self.invalidate()` when state changes from a timer or completed background task. Leave the default `RefreshMode.AUTO` for most changes:

```python
from badge_sdk import RefreshMode

self.invalidate(RefreshMode.PARTIAL)  # a known small status change
self.invalidate(RefreshMode.FULL)     # a major screen or artwork change
```

The runtime also chooses a full refresh for large changes and periodically after partial refreshes. Avoid rapid screen animations: animate an LED or internal state at the required cadence, but update e-paper status much less often.

## Manifest reference

A standalone JSON app uses `badge-app.json` (recommended) or `app.json`. Required fields are:

| Field | Meaning |
| --- | --- |
| `schema_version` | Must be `2` |
| `id` | 1–64 lowercase letters, digits, or hyphens; no leading/trailing hyphen |
| `name` | Display name |
| `version` | App version using letters, digits, and supported `._+!-` punctuation |
| `category` | Lowercase launcher category identifier |
| `entry_point` | Importable `module:object` |

Optional fields include `description`, `author`, `license`, `homepage`, `repo`, `dependencies`, `system_dependencies`, `permissions`, `requires_python`, `requires_sdk`, `min_badge_version`, `ui`, and `execution`.

Keep `dependencies`, `system_dependencies`, and `permissions` empty unless they are genuinely required. The current launcher records permissions but does not enforce them, and it intentionally refuses to install declared dependencies without a configured dependency provider.

`requires_python`, `requires_sdk`, and `min_badge_version` accept comma-separated
comparisons such as `>=3.11,<3.14` or `>=1,<2`. The store enforces these fields,
plus `ui = "portable-v1"` and `execution = "in-process"`, both when installing
and immediately before importing an installed app. Unsupported version syntax
is rejected rather than guessed. Apps should still report unavailable optional
hardware capabilities clearly.

A project that already uses standard Python packaging may put the same metadata in `pyproject.toml`:

```toml
[project]
name = "hello-badge"
version = "1.0.0"
description = "A minimal portable BeagleBadge app"
requires-python = ">=3.11"
dependencies = []

[project.entry-points."beaglebadge.apps"]
hello-badge = "hello_badge:HelloBadge"

[tool.beaglebadge]
schema_version = 2
id = "hello-badge"
display_name = "Hello Badge"
category = "apps"
sdk = ">=1.0,<2"
permissions = []
```

The store accepts a module or package either at the repository root or under `src/`. Packages may use ordinary absolute imports (`from my_package.helper import value`) or relative imports (`from .helper import value`); the launcher keeps each installed app in a private import namespace so equal package names from different apps cannot collide. A published v2 repository must contain its own `pyproject.toml`, `badge-app.json`, or `app.json`. Its ID, version, and entry point must match the catalog entry.

## Publishing to the app store

The store catalog's `manifest.json` uses `schema_version: 2` and an `apps` array. Each entry contains the same v2 metadata as the package plus a `repo` URL when source is not embedded at `apps/<id>/app` in the catalog repository. The launcher validates catalog values, downloads source with Git argument vectors, stages the package, checks its manifest and entry-point module, and then moves it into place.

That workflow is transactional, not a trust guarantee. Apps run in-process and
are not sandboxed. The packaged root service refuses third-party launch by
default; `BADGE_ALLOW_ROOT_APPS=1` is an unsafe opt-in for code the device owner
has reviewed. Keep declared access minimal and never describe manifest
validation as code signing.

## Porting a v1 app

There is no automatic compatibility shim. Port each old app explicitly:

1. Run it with Python 3.11 and replace MicroPython-only modules and APIs with standard Python.
2. Replace direct LVGL object construction with a `badge_sdk.App` whose `view()` returns components.
3. Move device access behind `context.services`; add a narrow platform service when needed.
4. Replace converted UI assets with ordinary images where possible and load them through `Image` and `context.resources`.
5. Move writable state to `context.data_dir`.
6. Add a schema-v2 manifest and a `module:object` entry point.
7. Preview on desktop and headless, add unit tests, then validate the real framebuffer, controls, and hardware on a badge.

Keeping the port explicit makes failures visible and leaves every maintained app on the same small public API.
