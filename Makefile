PYTHON ?= python3
RELEASE_VERSION := $(shell tr -d '\r\n' < VERSION)
PYTHON_SOURCES := main.py main_sdl.py badge_sdk badge_ui badge_platform builtin_apps scripts examples tests

.PHONY: test version-check check desktop screenshot package clean

test:
	$(PYTHON) -m pytest -q

version-check:
	$(PYTHON) scripts/versioning.py "$(RELEASE_VERSION)" --check-pyproject pyproject.toml

check: test version-check
	$(PYTHON) -m compileall -q $(PYTHON_SOURCES)

desktop:
	$(PYTHON) main.py --backend desktop --no-hardware --skip-onboarding

screenshot:
	mkdir -p build/dev-data
	$(PYTHON) main.py --backend headless --no-hardware --skip-onboarding \
		--frames 1 --data-dir build/dev-data --screenshot build/launcher.png

package:
	./scripts/build_deb.sh

clean:
	rm -rf build dist
