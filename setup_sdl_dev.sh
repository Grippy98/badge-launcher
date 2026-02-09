#!/bin/bash
# Setup script for Badge Launcher SDL development on Linux/macOS
# Builds LVGL Python bindings from source with SDL support

set -e  # Exit on error

echo "====================================="
echo "Badge Launcher - SDL Development Setup"
echo "====================================="
echo ""
echo "This will:"
echo "  - Install build dependencies (SDL2, cmake, etc.)"
echo "  - Build LVGL Python bindings from source"
echo "  - Set up SDL display backend"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

OS_TYPE="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
fi

echo "Detected OS: $OS_TYPE"

if [ "$OS_TYPE" == "macos" ]; then
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Please install from https://brew.sh"
        exit 1
    fi
    echo "✓ Homebrew found"
    
    echo ""
    echo "📦 Installing dependencies..."
    brew install sdl2 cmake python3 pkg-config libffi
elif [ "$OS_TYPE" == "linux" ]; then
    echo ""
    echo "📦 Installing dependencies (requires sudo)..."
    # User should have already installed these via the plan, but good to ensure
    sudo apt-get update
    sudo apt-get install -y libsdl2-dev cmake build-essential python3-dev python3-pip python3-venv libffi-dev pkg-config
else
    echo "⚠️  Unsupported OS: $OSTYPE"
    echo "Please install SDL2, CMake, and build tools manually."
fi


# Create build directory
BUILD_DIR="$HOME/.lvgl_build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Create virtual environment for build dependencies
echo ""
echo "📦 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Using existing virtual environment"
fi

# Activate virtual environment
source venv/bin/activate

# Install build dependencies in venv
echo ""
echo "📦 Installing Python build dependencies in venv..."
# Use --no-index to skip PyPI checks if packages already exist
pip install --upgrade pip setuptools wheel 2>/dev/null || {
    echo "⚠️  Network timeout, using existing packages"
    pip list | grep -E "pip|setuptools|wheel"
}

echo ""
echo "🔨 Building LVGL Python bindings with SDL support..."
echo "   (This may take 5-10 minutes)"
echo ""

# Clone LVGL Python bindings if not already cloned
if [ ! -d "lv_binding_micropython" ]; then
    echo "📥 Cloning lv_binding_micropython..."
    git clone --recursive https://github.com/lvgl/lv_binding_micropython.git
else
    echo "📥 Updating lv_binding_micropython..."
    cd lv_binding_micropython
    git pull
    git submodule update --init --recursive
    cd ..
fi

cd lv_binding_micropython

# Build with SDL support
echo ""
echo "🔨 Building LVGL module..."

# Create build script
cat > build_sdl.py << 'BUILDSCRIPT'
import os
import sys
import subprocess

# Set environment for SDL
if sys.platform == 'darwin':
    os.environ['SDL_CONFIG'] = '/opt/homebrew/bin/sdl2-config'
else:
    # Linux usually has sdl2-config in path or via pkg-config
    try:
        sdl_config = subprocess.check_output(['which', 'sdl2-config']).decode().strip()
        os.environ['SDL_CONFIG'] = sdl_config
    except:
        pass # Hope it's in path or pkg-config works

# Build command (adjusting for user_c_modules path relative to ports/unix)
build_cmd = """
make -C ports/unix VARIANT=dev \\
    USER_C_MODULES=../../lv_binding_micropython/lvgl/micropython.cmake \\
    SDL=1
"""

print("Building MicroPython with LVGL and SDL...")
os.system(build_cmd)
BUILDSCRIPT

# Alternative: Build Python module directly
echo "🔨 Building standalone Python module..."

cat > setup_sdl.py << 'SETUPSCRIPT'
#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import subprocess

# Try to build using the lib/lv_bindings approach
lv_bindings = Path(__file__).parent / "lib" / "lv_bindings"

if lv_bindings.exists():
    os.chdir(lv_bindings)

    # Set SDL environment
    os.environ['LV_CONF_INCLUDE_SIMPLE'] = '1'
    if sys.platform == 'darwin':
        os.environ['SDL_CONFIG'] = '/opt/homebrew/bin/sdl2-config'
    
    # Run build
    build_cmd = f"{sys.executable} -m pip install . --use-pep517"
    print(f"Running: {build_cmd}")
    result = os.system(build_cmd)

    if result != 0:
        print("Build failed!")
        sys.exit(1)
else:
    print("lv_bindings not found, trying alternative method...")

    # Try building via setup.py in root
    os.chdir(Path(__file__).parent)
    result = os.system(f"{sys.executable} setup.py build_ext --inplace --enable-sdl")

    if result != 0:
        print("Build failed!")
        sys.exit(1)

print("Build successful!")
SETUPSCRIPT

chmod +x setup_sdl.py

# Check if lib/lv_bindings exists
if [ -d "lib/lv_bindings" ]; then
    echo "Found lib/lv_bindings, building Python module..."
    cd lib/lv_bindings

    # Set up environment for SDL
    export LV_CONF_INCLUDE_SIMPLE=1
    if [ "$OS_TYPE" == "macos" ]; then
        export SDL_CONFIG=/opt/homebrew/bin/sdl2-config
    fi
    
    # Build and install (using venv pip)
    pip install . --use-pep517 || {
        echo "⚠️  Standard build failed, trying with --no-build-isolation..."
        pip install --no-build-isolation .
    }
else
    echo "⚠️  Expected build structure not found"
    echo "Trying alternative MicroPython Unix port build..."

    # Build MicroPython Unix port with LVGL using lv_micropython fork
    cd "$BUILD_DIR"

    # Clone lv_micropython (MicroPython fork with LVGL integrated)
    if [ ! -d "lv_micropython" ]; then
        echo "📥 Cloning lv_micropython (MicroPython + LVGL)..."
        git clone --recursive https://github.com/lvgl/lv_micropython.git
        cd lv_micropython
    else
        echo "📥 Updating lv_micropython..."
        cd lv_micropython
        git pull
        git submodule update --init --recursive
    fi

    # Build mpy-cross first
    make -C mpy-cross

    # Build unix port with SDL
    cd ports/unix

    # Set up PKG_CONFIG_PATH for libffi (macOS specific)
    if [ "$OS_TYPE" == "macos" ]; then
        export PKG_CONFIG_PATH="/opt/homebrew/opt/libffi/lib/pkgconfig:$PKG_CONFIG_PATH"
    fi

    # Build with LVGL variant (includes LVGL module)
    make VARIANT=lvgl

    # Link micropython binary to PATH
    INSTALL_DIR="/usr/local/bin"
    if [ -f "$(pwd)/build-lvgl/micropython" ]; then
        sudo ln -sf "$(pwd)/build-lvgl/micropython" "$INSTALL_DIR/micropython-lvgl"
    elif [ -f "$(pwd)/build-standard/micropython" ]; then
        sudo ln -sf "$(pwd)/build-standard/micropython" "$INSTALL_DIR/micropython-lvgl"
    elif [ -f "$(pwd)/build/micropython" ]; then
        sudo ln -sf "$(pwd)/build/micropython" "$INSTALL_DIR/micropython-lvgl"
    fi

    echo ""
    echo "✓ MicroPython with LVGL built successfully"
    echo "  Installed to: $INSTALL_DIR/micropython-lvgl"
fi

cd "$BUILD_DIR/.."

echo ""
echo "====================================="
echo "✓ Build complete!"
echo "====================================="
echo ""

# Test the installation (venv should still be active)
echo "🧪 Testing LVGL import..."
if python -c "import lvgl; print(f'LVGL version: {lvgl.version_info()}');" 2>/dev/null; then
    echo "✓ LVGL Python module installed successfully in venv"
    PYTHON_CMD="python"
    USE_VENV=true
elif micropython-lvgl -c "import lvgl; print('LVGL loaded')" 2>/dev/null; then
    echo "✓ MicroPython with LVGL installed successfully"
    PYTHON_CMD="micropython-lvgl"
    USE_VENV=false
else
    echo "⚠️  Could not verify LVGL installation"
    echo ""
    echo "You may need to:"
    echo "  1. Activate venv: source $BUILD_DIR/venv/bin/activate"
    echo "  2. Or use: micropython-lvgl main_sdl.py"
    PYTHON_CMD="python"
    USE_VENV=true
fi

echo ""
if [ "$USE_VENV" = true ]; then
    echo "To run the Badge Launcher in SDL mode:"
    echo "  # Activate the virtual environment first"
    echo "  source $BUILD_DIR/venv/bin/activate"
    echo ""
    echo "  # Then run the launcher"
    echo "  cd $(pwd)"
    echo "  $PYTHON_CMD main_sdl.py"
else
    echo "To run the Badge Launcher in SDL mode:"
    echo "  $PYTHON_CMD main_sdl.py"
fi
echo ""
echo "Controls:"
echo "  Arrow Keys    - Navigate menu/games"
echo "  Enter         - Select/Confirm"
echo "  Escape        - Back/Exit"
echo "  Mouse         - Click to interact"
echo ""
