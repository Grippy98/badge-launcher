"""Translate the Debian release version into the launcher's PEP 440 version."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import stat
import tomllib

try:
    from packaging.version import InvalidVersion, Version
except ImportError:  # pragma: no cover - setuptools normally supplies this fallback.
    from setuptools._vendor.packaging.version import InvalidVersion, Version


class VersionSyncError(ValueError):
    """Raised when release metadata cannot be represented safely."""


_DEBIAN_VERSION = re.compile(r"^[0-9][0-9A-Za-z.+_~-]*$")
_DEBIAN_PRERELEASE = re.compile(
    r"^(?P<release>.+)~(?P<label>experimental|dev|alpha|a|beta|b|rc)(?P<number>[0-9]*)$",
    re.IGNORECASE,
)
_PROJECT_HEADER = re.compile(r"(?m)^\[project\][ \t]*$")
_NEXT_TABLE = re.compile(r"(?m)^\[")
_STATIC_VERSION = re.compile(r"(?m)^(?P<indent>[ \t]*)version[ \t]*=.*$")


def pep440_from_release(release: str) -> str:
    """Return the canonical PEP 440 equivalent of a Debian package version."""

    if not isinstance(release, str) or release != release.strip() or not release:
        raise VersionSyncError("release version must be a non-empty value without whitespace")
    if not _DEBIAN_VERSION.fullmatch(release):
        raise VersionSyncError(f"unsupported Debian release version: {release!r}")

    candidate = release
    prerelease = _DEBIAN_PRERELEASE.fullmatch(release)
    if prerelease:
        label = prerelease.group("label").lower()
        number = prerelease.group("number") or "0"
        suffix = {
            "experimental": f".dev{number}",
            "dev": f".dev{number}",
            "alpha": f"a{number}",
            "a": f"a{number}",
            "beta": f"b{number}",
            "b": f"b{number}",
            "rc": f"rc{number}",
        }[label]
        candidate = prerelease.group("release") + suffix
    elif "~" in release:
        raise VersionSyncError(
            "unsupported Debian prerelease; use ~experimentalN, ~devN, ~alphaN, ~betaN, or ~rcN"
        )

    try:
        return str(Version(candidate))
    except InvalidVersion as error:
        raise VersionSyncError(
            f"release version {release!r} cannot be represented as PEP 440"
        ) from error


def _project_section(text: str) -> tuple[int, int, str]:
    header = _PROJECT_HEADER.search(text)
    if header is None:
        raise VersionSyncError("pyproject.toml has no [project] table")
    next_table = _NEXT_TABLE.search(text, header.end())
    end = next_table.start() if next_table else len(text)
    return header.start(), end, text[header.start() : end]


def read_pyproject_version(path: str | Path) -> str:
    source = Path(path)
    try:
        data = tomllib.loads(source.read_text(encoding="utf-8"))
        value = data["project"]["version"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise VersionSyncError(f"could not read project.version from {source}") from error
    if not isinstance(value, str) or not value:
        raise VersionSyncError("project.version must be a non-empty string")
    try:
        Version(value)
    except InvalidVersion as error:
        raise VersionSyncError(f"project.version is not valid PEP 440: {value!r}") from error
    return value


def check_pyproject_version(path: str | Path, release: str) -> str:
    expected = pep440_from_release(release)
    actual = read_pyproject_version(path)
    if actual != expected:
        raise VersionSyncError(
            f"project.version is {actual!r}; expected {expected!r} from VERSION {release!r}"
        )
    return expected


def update_pyproject_version(path: str | Path, release: str) -> str:
    """Atomically synchronize a static ``project.version`` assignment."""

    source = Path(path)
    expected = pep440_from_release(release)
    try:
        original = source.read_text(encoding="utf-8")
    except OSError as error:
        raise VersionSyncError(f"could not read {source}") from error
    start, end, section = _project_section(original)
    assignments = list(_STATIC_VERSION.finditer(section))
    if len(assignments) != 1:
        raise VersionSyncError("[project] must contain exactly one static version assignment")
    match = assignments[0]
    replacement = f'{match.group("indent")}version = "{expected}"'
    updated_section = section[: match.start()] + replacement + section[match.end() :]
    updated = original[:start] + updated_section + original[end:]

    temporary = source.with_name(f".{source.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(updated, encoding="utf-8")
        temporary.chmod(stat.S_IMODE(source.stat().st_mode))
        os.replace(temporary, source)
    except OSError as error:
        raise VersionSyncError(f"could not update {source}") from error
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    check_pyproject_version(source, release)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", help="Debian release value stored in VERSION")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-pyproject", type=Path)
    action.add_argument("--update-pyproject", type=Path)
    args = parser.parse_args()
    try:
        if args.check_pyproject:
            result = check_pyproject_version(args.check_pyproject, args.release)
        elif args.update_pyproject:
            result = update_pyproject_version(args.update_pyproject, args.release)
        else:
            result = pep440_from_release(args.release)
    except VersionSyncError as error:
        parser.error(str(error))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
