# Architecture

The experimental launcher separates the app-facing API from rendering and Linux hardware. The intended dependency direction is:

```text
third-party app / builtin app
            │
            ▼
        badge_sdk
            │
            ▼
   badge_ui runtime + renderer
       │                │
       ▼                ▼
display/input       badge_platform
backends            capabilities
```

Apps should import only `badge_sdk`. `badge_ui` and `badge_platform` are launcher implementation packages and can evolve without requiring every app to know which framebuffer or Linux utility is in use.

## Package boundaries

### `badge_sdk`

The public app contract. It contains:

- `App` and its lifecycle hooks
- `AppContext` for navigation, persistent paths, timers, background work, and platform services
- structural service protocols in `badge_sdk.services`, so editors can complete
  optional hardware APIs without apps importing Linux adapters
- normalized `Action` and `InputEvent` values
- `RefreshMode`
- declarative components such as `Screen`, `Column`, `Row`, `Text`, `Menu`, `Button`, `Image`, `QRCode`, `Progress`, `TextInput`, `Keyboard`, and `Canvas`

`badge_sdk.SDK_API` is currently `1.0`. The branch is still experimental, so apps should also declare their expected SDK range in the v2 manifest.

### `badge_ui`

The internal UI implementation:

- `ApplicationRuntime` owns the app stack, focus, events, timers, worker threads, invalidation, and lifecycle calls.
- `Renderer` turns a component tree into a Pillow `L` image.
- `FramebufferBackend` queries fbdev variable/fixed screen information, then writes that image to linear 1-, 8-, 16-, 24-, or 32-bit Linux framebuffers while respecting the reported resolution, depth, memory length, and stride.
- `PygameBackend` provides a desktop window and keyboard events.
- `HeadlessBackend` keeps the last frame in memory and can save a screenshot.

The renderer is monochrome-first even though its canonical frame is 8-bit grayscale. This keeps layout and image handling straightforward while producing a frame that can be packed for the badge display.

The current framebuffer packer assumes the visible page begins at offset zero
and uses conventional packed pixel layouts. It records fbdev offsets and color
bitfields but does not yet apply panning offsets or exotic bitfields. Those
values should be asserted on each target image before describing the backend as
generic fbdev support; the badge remains the supported hardware target.

### `badge_platform`

Narrow adapters for operating-system capabilities:

- atomic JSON settings
- evdev discovery and input normalization
- system, battery, network, Bluetooth, I2C, RGB LED, sound, and serial access
- argument-vector subprocess execution without a command shell
- v1/v2 manifest parsing and safe path validation
- app-store catalog, staging, installation, update, rollback, removal, and lazy loading

An app accesses these through `self.context.services`. Standard UI components remain portable; hardware-oriented apps should handle an unavailable capability as a normal state.

### `builtin_apps`

Trusted first-party apps. `builtin_apps/catalog.py` registers their classes without filesystem scanning. The launcher adds installed schema-v2 apps from the app store, while skipping installed legacy packages.

## Runtime flow

1. `main.py` selects a framebuffer, desktop, or headless backend.
2. It creates `PlatformServices`, the `AppStore`, and the launcher catalog.
3. Armbian onboarding becomes the initial app when its first-login marker is present; otherwise the launcher starts directly.
4. `ApplicationRuntime` attaches an `AppContext`, calls `on_start()`, and asks the active app for a `Screen` via `view()`.
5. The renderer collects focusable components and produces the frame.
6. The runtime compares it with the previous frame, chooses a refresh mode, and presents it through the selected backend.
7. Backend and evdev input are normalized into `InputEvent` objects. The active app sees `handle()` first; unconsumed events go to the focused component or the default Back action.

Opening an app pushes it onto the stack and pauses timers owned by the covered
app. Completed background callbacks wait until their owner is visible again.
Closing an app calls `on_stop()`, resumes the revealed app's timers, and calls
`on_resume()`. Closing the root app ends the loop.

Timers owned by an app context are cancelled automatically on exit, and late
background completion callbacks are discarded. If an app raises during input,
a timer, or rendering, the runtime removes that app and shows an error screen;
the launcher beneath it remains available.

If a child app raises from `on_start()`, the push is rolled back completely,
the parent resumes, and the exception returns to the caller so it can show a
task-specific message. A failure in the initial root app also releases runtime
resources, then propagates because there is no launcher beneath it to recover.

## State and redraws

Apps own plain Python state and rebuild their component tree in `view()`. A callback changes state, then calls `self.invalidate()` when work completed outside the normal input dispatch. The component `key` keeps focus stable across rebuilt trees.

`AppContext` provides:

- `open(app)`, `replace(app)`, and `exit()` for navigation
- `call_later()` and `call_every()` for work on the UI loop
- `run_background()` for blocking work, with completion callbacks returned to the UI loop
- `data_dir` for writable, per-app persistent state
- `resources` for files shipped beside the app module
- `invalidate()` to request a redraw

Normal invalidation is e-paper aware. The runtime computes changed bounds and requests a partial refresh for modest updates, but forces a full refresh after repeated partial updates or when more than 45 percent of the frame changes. A `Screen` may set `full_refresh=True`, and an app can request `RefreshMode.FULL` explicitly. The framebuffer backend currently writes the complete packed frame; refresh mode controls its full black/white clearing cycle and leaves device-specific waveform handling to the kernel driver.

## Installed-app discovery

Discovery reads manifests only; it does not import every installed app during launcher startup. A schema-v2 entry point uses `module:object` syntax. Code is imported into a unique namespace only when the user launches it, and the object must produce a `badge_sdk.App` instance. Validated manifest metadata overrides executable class metadata in the installed instance.

The store stages an install in its managed data tree, validates package metadata and paths, and swaps it into place atomically. Updating retains one rollback version. Removing an app deletes installed code and rollback code, not its separate `app-data` directory.

V1 `metadata.json` files are parsed only to identify old catalog entries and explain that a port is needed. They are never adapted into a hidden compatibility runtime.

## Trust boundary

Manifest validation is an input-safety layer, not a Python sandbox. A launched
v2 app runs in-process and can use normal Python APIs. On the packaged badge
service, the launcher runs as root to access the display and hardware, so
third-party launch is refused before import unless the device owner explicitly
sets `BADGE_ALLOW_ROOT_APPS=1`. The `permissions` manifest field remains
descriptive and is not enforced.

Consequences for maintainers and users:

- Treat app repositories as executable code and review them before publishing or installing.
- Do not present HTTPS transport or manifest parsing as code signing.
- Keep command construction in argument vectors and avoid invoking a shell with catalog or user input.
- Prefer narrow `context.services` capabilities over app-specific device paths, while recognizing that this is an API design boundary rather than an access-control boundary.
- Do not install declared Python or system dependencies automatically without an explicit dependency policy.
- Do not enable `BADGE_ALLOW_ROOT_APPS` globally; it is an explicit trust decision for unrestricted code.

Process isolation, package signatures, and enforced permissions can be added later without changing the declarative screen model, but they are not implemented today.

## Design rules

- App code imports `badge_sdk`, not a display backend.
- Components and app state are the default; `Canvas` is an advanced renderer-specific escape hatch.
- Slow I/O belongs in `run_background()`, not `view()` or `handle()`.
- Device paths belong in `badge_platform` and should be discoverable or configurable.
- Manifests are metadata; importing an app is a separate, explicit action.
- The desktop and headless backends validate UI behavior, but final hardware behavior still needs testing on the badge.
