from pathlib import Path
import keyword

from badge_platform.app_manifest import load_manifest
from badge_sdk.cli import main


def test_new_validate_and_screenshot(tmp_path: Path) -> None:
    app_root = tmp_path / "hello-app"
    assert main(["new", str(app_root), "--name", 'Hello "Badge"']) == 0

    manifest = load_manifest(app_root / "badge-app.json")
    assert manifest.app_id == "hello-app"
    assert manifest.name == 'Hello "Badge"'
    assert not (app_root / "pyproject.toml").exists()
    assert main(["validate", str(app_root)]) == 0

    screenshot = tmp_path / "hello.png"
    assert main(["screenshot", str(app_root), str(screenshot)]) == 0
    assert screenshot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_new_refuses_non_empty_directory(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "keep.txt").write_text("user data")

    assert main(["new", str(destination)]) == 1
    assert (destination / "keep.txt").read_text() == "user data"


def test_new_makes_safe_python_names_for_digit_leading_id(tmp_path: Path) -> None:
    app_root = tmp_path / "numeric-app"
    assert main(["new", str(app_root), "--id", "123-tools"]) == 0

    manifest = load_manifest(app_root / "badge-app.json")
    module, app_class = manifest.entry_point.split(":", 1)
    assert manifest.app_id == "123-tools"
    assert module.isidentifier() and not keyword.iskeyword(module)
    assert app_class.isidentifier() and not keyword.iskeyword(app_class)
    assert (app_root / f"{module}.py").is_file()
    assert main(["validate", str(app_root)]) == 0


def test_new_makes_safe_module_name_for_keyword_id(tmp_path: Path) -> None:
    app_root = tmp_path / "keyword-app"
    assert main(["new", str(app_root), "--id", "class"]) == 0

    manifest = load_manifest(app_root / "badge-app.json")
    module, app_class = manifest.entry_point.split(":", 1)
    assert not keyword.iskeyword(module)
    assert not keyword.iskeyword(app_class)
    assert main(["validate", str(app_root)]) == 0


def test_new_rejects_overlong_manifest_id_before_creating_files(tmp_path: Path) -> None:
    app_root = tmp_path / "must-not-exist"
    assert main(["new", str(app_root), "--id", "a" * 65]) == 1
    assert not app_root.exists()
