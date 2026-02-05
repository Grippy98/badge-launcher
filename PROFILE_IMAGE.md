# Adding a Profile Image to Badge Mode

The Badge Mode app can display a custom profile image instead of the default logos (Beagle/TI).

## Quick Start

1. **Simply copy your image(s) to the profile_img directory:**
   ```bash
   # Copy one or more image files (jpg, png, bmp)
   cp your_photo.jpg profile_img/
   cp another_photo.png profile_img/
   ```

2. **Launch Badge Mode**
   - Your profile images will automatically be converted and displayed
   - Use LEFT/RIGHT arrow keys to cycle through multiple images
   - Converted images are cached in /tmp for faster loading
   - Profile images replace the logo selection

That's it! No manual conversion needed - Badge Mode handles everything automatically.

## How It Works

Badge Mode automatically handles image conversion:

1. **Scans profile_img/ directory** for ALL image files on startup
2. **Loads all images** (alphabetically sorted)
3. **Converts automatically** using img2bin if they're not already .bin files
4. **Caches in /tmp** for faster subsequent loads
5. **Displays the images** alongside the QR code
6. **LEFT/RIGHT keys** cycle through multiple images if available

## Supported Image Formats

- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **BMP** (.bmp)
- **Pre-converted** (.bin)

All images are automatically converted to:
- **Size:** 128x128 pixels
- **Format:** 8-bit grayscale (L8)
- **Mode:** Cover (cropped to fill, maintaining aspect ratio)

## Manual Conversion (Optional)

If you prefer to pre-convert images or img2bin isn't available:

**Syntax:**
```bash
./img2bin <input> <output> <width> <height> <mode>
```

**Example:**
```bash
# Pre-convert for faster loading
./img2bin my_photo.jpg profile_img/profile.bin 128 128 cover
```

**Building img2bin:**
```bash
gcc -o img2bin tools/img2bin.c -lm
```

## Tips for Best Results

1. **Portrait Photos:**
   - Use square or nearly-square images for best results
   - Center the face/subject in the frame
   - Images are automatically cropped to fill the space

2. **Logos/Graphics:**
   - Simple, high-contrast images work best on E-Ink displays
   - Avoid very detailed or low-contrast images

3. **Multiple Images:**
   - Add multiple images to profile_img/ and cycle through them with LEFT/RIGHT arrow keys
   - Images are loaded alphabetically
   - To reorder, rename files (e.g., 01_photo.jpg, 02_photo.jpg, etc.)
   - Badge Mode shows "Profile 1/3" indicator when multiple images are present

## Changing or Removing Profile Image

**To change your profile image:**
```bash
# Remove old image and add new one
rm profile_img/*
cp new_photo.jpg profile_img/
```

**To go back to default logos:**
```bash
# Remove all images from profile_img
rm profile_img/*

# Or remove the directory entirely
rm -rf profile_img
```

Then restart Badge Mode - logo cycling will be re-enabled.

## File Locations

- **Profile images:** `profile_img/` (any .jpg, .png, .bmp, or .bin file)
- **Cached conversions:** `/tmp/badge_profile_*.bin` (auto-generated)
- **Default logos:** `assets/ti_logo.bin`, `assets/beagle_logo.bin`
- **img2bin tool:** `./img2bin` (root of badge-slop directory)
- **img2bin source:** `tools/img2bin.c`

## Technical Details

The profile image system:
- Scans `profile_img/` for ALL image files (.jpg, .jpeg, .png, .bmp, .bin) on startup
- Loads all files found (alphabetically sorted)
- Automatically converts non-.bin files using img2bin if available
- Caches converted images in `/tmp/` for faster subsequent loads
- Images are converted to 128×128 pixels, 8-bit grayscale (L8 format)
- Uses "cover" mode (crops to fill) for optimal badge display
- Profile images take priority over logo selection
- LEFT/RIGHT keys cycle through multiple profile images
- If img2bin is not available, only pre-converted .bin files will work
- Current image index is tracked but not persisted (resets to first image on restart)

## Caching System

- Converted images are cached as `/tmp/badge_profile_<filename>.bin`
- Cache is created on first run, used on subsequent runs
- Cache persists across app restarts (until system reboot)
- To force reconversion, delete the cache file: `rm /tmp/badge_profile_*.bin`
