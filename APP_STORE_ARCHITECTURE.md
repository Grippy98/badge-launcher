# App Store Architecture

Visual guide to understanding how the badge app store works.

## Overview

The app store uses a two-tier architecture with git submodules for version control and on-demand app installation.

```
┌─────────────────────────────────────────────────────┐
│                    Badge Device                     │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │         App Store Application                │  │
│  │      (applications/tools/app_store_app.py)   │  │
│  └──────────────────────────────────────────────┘  │
│                        │                            │
│                        │ 1. Fetch manifest.json     │
│                        ▼                            │
└────────────────────────┼─────────────────────────────┘
                         │
                         │ curl (HTTPS)
                         │
┌────────────────────────▼─────────────────────────────┐
│              GitHub (App Store Repo)                 │
│        https://github.com/ORG/badge-app-store        │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ manifest.json                               │   │
│  │ - List of all available apps                │   │
│  │ - Metadata for each app                     │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  apps/                                               │
│  ├── weather/                                        │
│  │   ├── metadata.json                              │
│  │   └── app/ ──────► Git Submodule ────┐          │
│  ├── calculator/                          │          │
│  │   ├── metadata.json                   │          │
│  │   └── app/ ──────► Git Submodule ────┤          │
│  └── my-game/                             │          │
│      ├── metadata.json                    │          │
│      └── app/ ──────► Git Submodule ─────┤          │
└───────────────────────────────────────────┼──────────┘
                                            │
                          ┌─────────────────┴──────────────────┐
                          │                                    │
                          ▼                                    ▼
         ┌────────────────────────────┐    ┌────────────────────────────┐
         │   Individual App Repos     │    │   Individual App Repos     │
         │  github.com/user/weather   │    │ github.com/user/my-game   │
         │                            │    │                            │
         │  weather_app.py            │    │  my_game_app.py           │
         │  README.md                 │    │  README.md                │
         │  LICENSE                   │    │  LICENSE                  │
         │  assets/                   │    │  assets/                  │
         └────────────────────────────┘    └────────────────────────────┘
```

## Installation Flow

```
User selects app in App Store UI
         │
         ▼
┌─────────────────────────────────────────┐
│ 1. Clone/Update Store Repository       │
│    git clone badge-app-store            │
│    OR git pull (if exists)              │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 2. Initialize App's Submodule           │
│    git submodule update --init          │
│    apps/my-app/app                      │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 3. Copy App to Applications Directory   │
│    cp -r /tmp/store/apps/my-app/app     │
│           applications/apps/my-app/     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ 4. Restart Launcher                     │
│    App appears in menu                  │
└─────────────────────────────────────────┘
```

## Repository Structures

### Store Repository

```
badge-app-store/
├── manifest.json          # Master list (fetched by badge)
├── README.md
└── apps/
    ├── weather/
    │   ├── metadata.json  # App info for store UI
    │   └── app/          # Git submodule → weather-app repo
    ├── calculator/
    │   ├── metadata.json
    │   └── app/          # Git submodule → calculator-app repo
    └── my-game/
        ├── metadata.json
        └── app/          # Git submodule → my-game repo
```

### Individual App Repository

```
weather-app/
├── weather_app.py         # Main file (matches {id}_app.py)
├── README.md              # Usage documentation
├── LICENSE                # License file
├── assets/                # Optional: images, icons
│   └── icon.bin
└── data/                  # Optional: app data
    └── cities.json
```

## Data Flow

### 1. Browsing Apps

```
Badge → GitHub (Raw)
  GET: manifest.json

Response: JSON with app list
{
  "apps": [
    {"id": "weather", "name": "Weather", ...},
    {"id": "calculator", "name": "Calculator", ...}
  ]
}

Badge displays list in UI
```

### 2. Installing App

```
Badge → Shell Commands
  1. git clone store-repo /tmp/badge-app-store
     (or git pull if exists)

  2. cd /tmp/badge-app-store
     git submodule update --init apps/weather/app

  3. cp -r apps/weather/app applications/apps/weather

App is now available in launcher menu
```

## Component Interaction

```
┌──────────────────┐
│  Badge Launcher  │
│    (main.py)     │
└────────┬─────────┘
         │ loads
         ▼
┌──────────────────┐
│   App Loader     │
│ (app_loader.py)  │
└────────┬─────────┘
         │ scans applications/ directory
         │
         ├─► applications/apps/weather/weather_app.py
         ├─► applications/apps/calculator/calculator_app.py
         └─► applications/apps/my-game/my_game_app.py
                        ▲
                        │
                        │ installed by
                        │
                ┌───────┴────────┐
                │   App Store    │
                │ (app_store_app.py)│
                └────────────────┘
```

## Advantages of This Architecture

### 1. **Version Control**
- Each app is a separate git repository
- Store uses submodules for proper version tracking
- Easy to update individual apps
- Full git history for each app

### 2. **Decentralization**
- Apps can be hosted anywhere (any git repo)
- No central code hosting required
- Anyone can create their own store
- Fork-friendly for community versions

### 3. **On-Demand Installation**
- Only downloads apps when needed
- Saves storage space on badge
- Fast browsing (only manifest downloaded)
- Can install/uninstall freely

### 4. **Developer Freedom**
- Developers maintain their own repos
- Independent release cycles
- Can have multiple stores for same app
- Easy to fork and modify

### 5. **Security**
- Apps are reviewed before store inclusion
- Users can audit app code before installing
- Clear separation between store and apps
- Git provides integrity checking

## File Size Considerations

### Manifest Download
- `manifest.json`: ~2-10 KB (depending on number of apps)
- Downloaded every time app store opens
- Lightweight JSON, fast over network

### App Installation
- Typical app: 10-100 KB
- With assets: up to 1 MB recommended
- Downloaded once, cached locally
- Only downloaded when user installs

### Store Repository
- Metadata only: ~5 KB per app
- Submodules are references (not full clones)
- Full store repo: < 1 MB (metadata only)
- Individual apps not included in main clone

## Network Requirements

### Browsing
- **Bandwidth**: Minimal (~10 KB for manifest)
- **Connection**: Brief HTTPS request
- **Frequency**: Each time app store opens

### Installing
- **Bandwidth**: Variable (10 KB - 1 MB per app)
- **Connection**: Git protocol (HTTPS)
- **Frequency**: Only when installing new apps
- **Time**: Few seconds per app on typical connection

## Offline Behavior

### No Network
- App store shows error message
- Previously installed apps continue to work
- Cannot browse or install new apps
- Store repo cached in `/tmp/` if already cloned

### Intermittent Connection
- Manifest fetch may fail (shows error)
- Installation may be interrupted
- Git handles partial downloads
- Can retry installation

## Security Considerations

### Code Review
- Apps reviewed before store inclusion
- Public repositories allow user auditing
- Git history provides transparency
- No binary-only apps (source required)

### Sandboxing
- Apps run in same MicroPython environment
- No system-level sandboxing (by design)
- Trust-based model (like Linux packages)
- Apps can access file system

### Dependencies
- Listed in metadata
- Not automatically installed
- User must install system packages manually
- Prevents surprise installations

## Scalability

### Number of Apps
- Manifest size: ~500 bytes per app
- 100 apps = ~50 KB manifest
- 1000 apps = ~500 KB manifest
- UI can handle hundreds of apps

### Store Size
- Metadata only, no app code
- Submodules are shallow references
- Store repo stays < 10 MB even with many apps
- Fast to clone and update

### Multiple Stores
- Users can configure multiple store URLs
- Easy to have official + community stores
- Simple to switch between stores
- Can merge manifests from multiple sources

## Comparison with Other Approaches

### vs Direct GitHub API
- **Chosen**: Git submodules
- **Alternative**: GitHub API + direct downloads
- **Reason**: Git provides version control, history, and integrity

### vs Package Repository (apt/pip style)
- **Chosen**: Git repos
- **Alternative**: Debian packages or PyPI
- **Reason**: Simpler for developers, no package building required

### vs Bundled Apps
- **Chosen**: On-demand installation
- **Alternative**: All apps pre-installed
- **Reason**: Saves space, user choice, easier updates

## Future Enhancements

Possible improvements to the architecture:

1. **Caching**: Cache manifest locally for offline browsing
2. **Updates**: Check for app updates automatically
3. **Ratings**: Community ratings and reviews
4. **Search**: Full-text search across apps
5. **Categories**: Better category filtering
6. **Dependencies**: Automatic dependency resolution
7. **Signatures**: GPG signatures for app verification
8. **Mirrors**: Multiple mirrors for redundancy

## Technical Limitations

### Current Constraints
- Requires git on the badge (usually available on Linux)
- Network required for browsing and installing
- No automatic updates (user must manually update)
- No dependency resolution
- Single store per configuration

### Design Choices
- Trust-based security model
- No binary verification
- Manual restart required after install
- Apps share Python environment

## Getting Started

To set up your own app store:

1. **Create store repo**: `./scripts/create_app_store_repo.sh`
2. **Add apps**: `./scripts/add_app_to_store.sh`
3. **Configure badge**: Update URLs in `app_store_app.py`
4. **Test**: Install and test each app
5. **Publish**: Push to GitHub, share with community

For detailed instructions, see:
- [APP_STORE_SETUP.md](APP_STORE_SETUP.md) - Complete setup guide
- [APP_SUBMISSION_GUIDE.md](APP_SUBMISSION_GUIDE.md) - Developer guide
