# Badge Launcher - Build Tools
# Simple makefile for building conversion tools

.PHONY: all clean img2bin help

# Default target
all: img2bin

# Image conversion tool (required for Photos app)
img2bin: tools/img2bin.c tools/stb_image.h tools/stb_image_resize2.h
	@echo "Building img2bin..."
	gcc -o img2bin tools/img2bin.c -lm -O2
	@echo "✓ img2bin built successfully"

# Clean built binaries
clean:
	@echo "Cleaning built binaries..."
	rm -f img2bin
	@echo "✓ Clean complete"

# Help target
help:
	@echo "Badge Launcher Build Targets:"
	@echo ""
	@echo "  make img2bin    Build image conversion tool (default)"
	@echo "  make clean      Remove built binaries"
	@echo "  make help       Show this help message"
	@echo ""
	@echo "The img2bin tool is required for the Photos app to convert"
	@echo "JPEG/PNG images to binary format for the E-Ink display."
