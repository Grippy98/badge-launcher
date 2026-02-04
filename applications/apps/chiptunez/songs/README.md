# Custom Songs for ChipTunez

This directory contains custom song files that can be played in the ChipTunez app. Songs are stored as JSON files.

## Song File Format

Each song is a JSON file with the following structure:

```json
{
  "title": "Song Name",
  "desc": "Brief description of the song",
  "icon": "ICON_NAME",
  "notes": [
    [frequency_hz, duration_ms],
    [frequency_hz, duration_ms],
    ...
  ]
}
```

### Fields

- **title** (required): The name of the song that appears in the menu
- **desc** (required): A brief description shown in the info panel
- **icon** (optional): Icon symbol name (see list below). Defaults to "AUDIO"
- **notes** (required): Array of [frequency, duration] pairs
  - frequency: Note frequency in Hertz (use 0 for REST/silence)
  - duration: Note duration in milliseconds

### Available Icons

- AUDIO, VIDEO, LIST, OK, CLOSE, POWER, SETTINGS, HOME
- DOWNLOAD, DRIVE, REFRESH, MUTE, VOLUME_MID, VOLUME_MAX
- IMAGE, EDIT, PREV, PLAY, PAUSE, STOP, NEXT, EJECT
- LEFT, RIGHT, PLUS, MINUS, WARNING, SHUFFLE, UP, DOWN
- LOOP, DIRECTORY, UPLOAD, CALL, CUT, COPY, SAVE
- CHARGE, BLUETOOTH, GPS, USB, SD_CARD, WIFI

## Note Frequencies

Common note frequencies (in Hz):

| Note | Octave 4 | Octave 5 | Octave 6 |
|------|----------|----------|----------|
| C    | 262      | 523      | 1047     |
| D    | 294      | 587      | 1175     |
| E    | 330      | 659      | 1319     |
| F    | 349      | 698      | 1397     |
| G    | 392      | 784      | 1568     |
| A    | 440      | 880      | 1760     |
| B    | 494      | 988      | 1976     |

For sharp notes (C#, D#, etc.), use slightly higher frequencies.
For a complete list, see the note definitions at the top of chiptunez_app.py

## Example

See `example_custom_song.json` in this directory for a working example of "Mary Had a Little Lamb".

## Adding Your Song

1. Create a new `.json` file in this directory
2. Follow the format above
3. Restart the ChipTunez app to see your song in the list

## Tips

- Use 0 for frequency to create rests/pauses
- Typical note durations: 125ms (fast), 250ms (medium), 500ms (slow)
- Keep songs under 100 notes for best performance
- Test your song to make sure the timing sounds right
