# ChipTunez Music Player

A chiptune music player that plays melodies using the system beeper. Play classic songs like Imperial March, Super Mario, Doom, and more!

## Features

- 🎵 Built-in song library
- 📝 JSON-based song format
- ➕ Easy to add custom songs
- 🎨 Clean split-screen UI with song details
- 🔊 Beeper-based playback

## Directory Structure

```
chiptunez/
├── chiptunez_app.py          # Main application
├── songs/                    # Song library
│   ├── README.md             # Song format documentation
│   ├── imperial_march.json
│   ├── super_mario.json
│   ├── doom.json
│   └── ...
└── README.md                 # This file
```

## Adding Custom Songs

All songs are JSON files in the `songs/` directory. See [songs/README.md](songs/README.md) for:
- Complete song format specification
- Note frequency reference
- Examples
- Tips for creating melodies

Simply add a `.json` file to the songs directory and it will appear in the app!

## Development

This app demonstrates the folder-based app structure, where all app resources are self-contained in a single directory. This makes it:
- Easy to distribute
- Simple to modify
- Git submodule friendly
- Ready for an app store

## License

Feel free to use, modify, and distribute this app. Add your own songs and share them!
