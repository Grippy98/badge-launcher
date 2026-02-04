#!/bin/bash
# Validate an app repository structure before adding to store

set -e

APP_DIR=$1

if [ -z "$APP_DIR" ]; then
    echo "Usage: $0 <app-directory>"
    echo ""
    echo "Example: $0 ../my-app-repo"
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    echo "Error: Directory not found: $APP_DIR"
    exit 1
fi

echo "Validating app structure: $APP_DIR"
echo ""

ERRORS=0
WARNINGS=0

# Check for git repository
if [ ! -d "$APP_DIR/.git" ]; then
    echo "❌ ERROR: Not a git repository"
    ERRORS=$((ERRORS + 1))
else
    echo "✓ Git repository found"
fi

# Check for README
if [ ! -f "$APP_DIR/README.md" ]; then
    echo "⚠️  WARNING: No README.md found"
    WARNINGS=$((WARNINGS + 1))
else
    echo "✓ README.md found"
fi

# Check for LICENSE
if [ ! -f "$APP_DIR/LICENSE" ] && [ ! -f "$APP_DIR/LICENSE.txt" ]; then
    echo "⚠️  WARNING: No LICENSE file found"
    WARNINGS=$((WARNINGS + 1))
else
    echo "✓ LICENSE file found"
fi

# Check for Python files
PY_FILES=$(find "$APP_DIR" -maxdepth 1 -name "*_app.py" | wc -l)
if [ "$PY_FILES" -eq 0 ]; then
    echo "❌ ERROR: No *_app.py file found in root directory"
    ERRORS=$((ERRORS + 1))
elif [ "$PY_FILES" -gt 1 ]; then
    echo "⚠️  WARNING: Multiple *_app.py files found:"
    find "$APP_DIR" -maxdepth 1 -name "*_app.py"
    WARNINGS=$((WARNINGS + 1))
else
    MAIN_FILE=$(find "$APP_DIR" -maxdepth 1 -name "*_app.py")
    echo "✓ Main file found: $(basename $MAIN_FILE)"

    # Basic syntax check
    python3 -m py_compile "$MAIN_FILE" 2>/dev/null && echo "✓ Python syntax valid" || {
        echo "❌ ERROR: Python syntax error in main file"
        ERRORS=$((ERRORS + 1))
    }

    # Check for required imports
    if ! grep -q "from core import app" "$MAIN_FILE"; then
        echo "⚠️  WARNING: Main file doesn't import 'app' from core"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Check for App class
    if ! grep -q "class.*App(app.App)" "$MAIN_FILE"; then
        echo "❌ ERROR: Main file doesn't define an App class extending app.App"
        ERRORS=$((ERRORS + 1))
    else
        echo "✓ App class found"
    fi
fi

# Check directory structure
echo ""
echo "Directory contents:"
ls -lh "$APP_DIR" | grep -v "^total" | awk '{print "  " $9 " (" $5 ")"}'

# Check file sizes (warn about large files)
LARGE_FILES=$(find "$APP_DIR" -type f -size +1M)
if [ ! -z "$LARGE_FILES" ]; then
    echo ""
    echo "⚠️  WARNING: Large files detected (>1MB):"
    find "$APP_DIR" -type f -size +1M -exec ls -lh {} \; | awk '{print "  " $9 " (" $5 ")"}'
    WARNINGS=$((WARNINGS + 1))
fi

# Summary
echo ""
echo "================================"
echo "Validation Summary"
echo "================================"
echo "Errors: $ERRORS"
echo "Warnings: $WARNINGS"
echo ""

if [ "$ERRORS" -gt 0 ]; then
    echo "❌ Validation FAILED - Fix errors before submitting to store"
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo "⚠️  Validation PASSED with warnings - Consider fixing warnings"
    exit 0
else
    echo "✓ Validation PASSED - App is ready for the store!"
    exit 0
fi
