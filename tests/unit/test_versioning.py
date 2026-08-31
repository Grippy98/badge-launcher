from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.versioning import (
    VersionSyncError,
    check_pyproject_version,
    pep440_from_release,
    read_pyproject_version,
    update_pyproject_version,
)


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        ("2026.08.30~experimental1", "2026.8.30.dev1"),
        ("1.02.0~dev4", "1.2.0.dev4"),
        ("2.0~alpha2", "2.0a2"),
        ("2.0~beta3", "2.0b3"),
        ("2.0~rc1", "2.0rc1"),
        ("3.1.4", "3.1.4"),
    ],
)
def test_debian_release_converts_to_canonical_pep440(release: str, expected: str) -> None:
    assert pep440_from_release(release) == expected


@pytest.mark.parametrize(
    "release",
    ("", " 1.0", "v1.0", "1:2.0", "1.0~preview1", "1.0/unsafe"),
)
def test_invalid_or_unsupported_release_is_rejected(release: str) -> None:
    with pytest.raises(VersionSyncError):
        pep440_from_release(release)


def test_pyproject_version_update_is_scoped_and_checkable(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[build-system]
requires = ["setuptools>=77"]

[project]
name = "badge-test"
version = "1.0.0"

[tool.example]
version = "must-stay"
""",
        encoding="utf-8",
    )

    expected = update_pyproject_version(pyproject, "2027.01.02~experimental3")
    assert expected == "2027.1.2.dev3"
    assert read_pyproject_version(pyproject) == expected
    assert check_pyproject_version(pyproject, "2027.01.02~experimental3") == expected
    assert 'version = "must-stay"' in pyproject.read_text(encoding="utf-8")
    with pytest.raises(VersionSyncError, match="expected"):
        check_pyproject_version(pyproject, "2027.01.02~experimental4")


def test_update_version_script_synchronizes_all_release_metadata(tmp_path: Path) -> None:
    source_root = Path(__file__).parents[2]
    root = tmp_path / "release-tree"
    (root / "scripts").mkdir(parents=True)
    (root / "debian").mkdir()
    shutil.copy2(source_root / "scripts" / "update_version.sh", root / "scripts")
    shutil.copy2(source_root / "scripts" / "versioning.py", root / "scripts")
    (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "badge-test"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (root / "debian" / "changelog").write_text(
        "badge-launcher (1.0.0) unstable; urgency=medium\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHON"] = sys.executable

    result = subprocess.run(
        ["bash", str(root / "scripts" / "update_version.sh"), "2027.01.02~experimental3"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert (root / "VERSION").read_text(encoding="utf-8") == "2027.01.02~experimental3\n"
    assert read_pyproject_version(root / "pyproject.toml") == "2027.1.2.dev3"
    assert (root / "debian" / "changelog").read_text(encoding="utf-8").startswith(
        "badge-launcher (2027.01.02~experimental3)"
    )
