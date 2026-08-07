# Battlesnake

Launcher-native Battlesnake demo for BeagleBadge.

## Controls

- `ENTER`: pause/resume
- `UP`: restart match
- `LEFT`: slower
- `RIGHT`: faster
- `ESC`: exit to launcher

## Current Scope

This app renders a local two-snake Battlesnake-style match directly in the
badge launcher using LVGL. It is intentionally self-contained so it can run
before the external BadgeSnake transport and host runtime are wired in.

By default the launcher backend now pins the simulator to the `demo` matchup:

- `ZEPTO-A`
- `ZEPTO-B`

Override that by setting `BADGESNAKE_MATCHUP` before launching the backend.

## Follow-On

- replace the local snake policies with moves from the BadgeSnake host runtime
- reflect live Zepto registration and health
- map win/loss state to additional badge outputs
