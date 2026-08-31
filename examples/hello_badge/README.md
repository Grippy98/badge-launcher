# Hello Badge

This is the complete schema-v2 app used by the app-development guide. From the launcher repository root:

```bash
python examples/preview_app.py examples/hello_badge
```

Or produce a headless screenshot:

```bash
python examples/preview_app.py examples/hello_badge --screenshot /tmp/hello-badge.png
```

`badge-app.json` contains catalog metadata and the `hello_badge:HelloBadge` entry point. `hello_badge.py` imports only the public `badge_sdk` package.
