# Profile Image Directory

This directory is used to store custom profile images for Badge Mode.

## Quick Setup

Simply copy one or more image files here:

```bash
# Just copy your images - Badge Mode handles the rest!
cp /path/to/your/photo.jpg .
cp /path/to/another_photo.png .
```

That's it! Badge Mode will automatically:
- Find all your images on startup
- Convert them to the correct format using img2bin
- Cache the converted versions in /tmp
- Display them in place of the default logos
- Let you cycle through multiple images with LEFT/RIGHT arrow keys

## Supported Formats

Drop any of these image types here:
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **BMP** (.bmp)
- **Pre-converted** (.bin)

## How It Works

1. Badge Mode scans this directory for ALL image files
2. All images are loaded (alphabetically sorted)
3. Images are automatically converted to 128×128 grayscale
4. Converted images are cached for faster loading
5. Profile images take priority over default Beagle/TI logos
6. Use LEFT/RIGHT arrow keys to cycle through multiple images
7. Top indicator shows "Profile 1/3" when multiple images are present

## Helper Script (Optional)

For convenience, you can use the helper script:

```bash
# From the badge-slop root directory
./scripts/set_profile_image.sh /path/to/your/photo.jpg
```

## Changing Images

To use a different image:

```bash
# Remove old images
rm *

# Add new image
cp /path/to/new_photo.jpg .
```

## Removing Profile Image

To go back to default logos:

```bash
# Remove all images from this directory
rm *
```

For more information, see: [PROFILE_IMAGE.md](../PROFILE_IMAGE.md)
