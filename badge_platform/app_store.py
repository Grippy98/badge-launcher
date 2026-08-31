"""Transactional app-store catalog and installation services.

This layer contains no UI code.  It treats catalog fields, application IDs,
repository URLs, and package contents as untrusted input and never invokes a
shell.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile
import threading
import tomllib
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse
import uuid

from .app_manifest import (
    AppManifest,
    ManifestError,
    adapt_v1_metadata,
    contained_path,
    load_app_entrypoint,
    load_manifest,
    parse_v2_json,
    validate_app_id,
)
from .command import CommandResult, CommandRunner


DEFAULT_STORE_URL = "https://github.com/Grippy98/badge-app-store.git"
INSTALL_DESCRIPTOR = ".badge-installed.json"
SUPPORTED_UI = "portable-v1"
SUPPORTED_EXECUTION = "in-process"
UNSAFE_ROOT_APPS_ENV = "BADGE_ALLOW_ROOT_APPS"

_SOURCE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_RESOLVED_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
_VERSION_RE = re.compile(
    r"^[vV]?(?P<release>\d+(?:\.\d+)*)"
    r"(?:(?:[-_.]?)(?P<label>dev|a|alpha|b|beta|rc|pre|preview|post|rev|r)"
    r"(?P<number>\d*))?$",
    re.IGNORECASE,
)
_SPECIFIER_RE = re.compile(r"^(~=|==|!=|>=|<=|>|<)\s*(\S+)$")


class StoreError(RuntimeError):
    """Base class for catalog, transport, and installation errors."""


class CatalogError(StoreError):
    """The remote or cached catalog is invalid."""


class CompatibilityError(StoreError):
    """An application declares a runtime contract this launcher cannot meet."""

    def __init__(self, app_id: str, field: str, required: str, current: str) -> None:
        self.app_id = app_id
        self.field = field
        self.required = required
        self.current = current
        super().__init__(
            f"{app_id} is incompatible: {field} requires {required!r}, current value is "
            f"{current!r}"
        )


class UnsafeExecutionError(StoreError):
    """Third-party in-process execution was refused in a privileged launcher."""

    def __init__(self, app_id: str) -> None:
        self.app_id = app_id
        super().__init__(
            f"refusing to launch third-party app {app_id!r} as root; run the launcher "
            f"unprivileged or explicitly set {UNSAFE_ROOT_APPS_ENV}=1 to accept unrestricted "
            "root code execution"
        )


class DependencyResolutionRequired(StoreError):
    """Installation requires a dependency provider that was not configured."""

    def __init__(self, app_id: str, dependencies: Iterable[str]) -> None:
        self.app_id = app_id
        self.dependencies = tuple(dependencies)
        super().__init__(
            f"{app_id} requires dependencies that are not installed automatically: "
            + ", ".join(self.dependencies)
        )


class LegacyPortRequired(StoreError):
    """A MicroPython/LVGL v1 application must be ported before CPython use."""

    def __init__(self, app_id: str) -> None:
        self.app_id = app_id
        super().__init__(
            f"{app_id} is a legacy MicroPython/LVGL app and must be ported to "
            "the v2 badge_sdk contract before it can run under CPython"
        )


@dataclass(frozen=True, slots=True)
class CatalogApp:
    manifest: AppManifest
    source_dir: Path | None = None
    source_ref: str = ""
    stars: int = 0
    updated_at: str = ""

    @property
    def id(self) -> str:
        return self.manifest.app_id

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def category(self) -> str:
        return self.manifest.category

    @property
    def description(self) -> str:
        return self.manifest.description

    @property
    def author(self) -> str:
        return self.manifest.author

    @property
    def project_url(self) -> str:
        return self.manifest.project_url or self.manifest.repository_url

    @property
    def repository_url(self) -> str:
        return self.manifest.repository_url

    @property
    def dependencies(self) -> tuple[str, ...]:
        return self.manifest.all_dependencies


@dataclass(frozen=True, slots=True)
class InstalledApp:
    manifest: AppManifest
    path: Path
    updated: bool = False
    previous_version: str = ""

    @property
    def id(self) -> str:
        return self.manifest.app_id


DependencyInstaller = Callable[[AppManifest, Path], None]


def _validated_remote(url: str, field: str = "repository URL") -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise StoreError(f"invalid {field}")
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise StoreError(f"{field} must use http or https")
    if parsed.username or parsed.password or any(ord(character) < 32 for character in url):
        raise StoreError(f"unsafe {field}")
    return url


def _validated_source_ref(value: object) -> str:
    """Validate a revision without interpreting it as a git option/refspec."""

    if value in (None, ""):
        return ""
    if not isinstance(value, str) or not _SOURCE_REF_RE.fullmatch(value):
        raise StoreError("source ref contains unsupported characters")
    if (
        value in {".", "..", "@"}
        or ".." in value
        or "//" in value
        or "@{" in value
        or value.endswith(("/", "."))
        or any(
            not component
            or component.startswith(".")
            or component.endswith(".lock")
            for component in value.split("/")
        )
    ):
        raise StoreError("source ref is not a safe git revision name")
    return value


def _parse_version(value: str) -> tuple[tuple[int, ...], tuple[int, int]]:
    match = _VERSION_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"unsupported version {value!r}")
    release = tuple(int(part) for part in match.group("release").split("."))
    label = (match.group("label") or "").lower()
    aliases = {
        "alpha": "a",
        "beta": "b",
        "pre": "rc",
        "preview": "rc",
        "rev": "post",
        "r": "post",
    }
    label = aliases.get(label, label)
    rank = {"dev": 0, "a": 1, "b": 2, "rc": 3, "": 4, "post": 5}[label]
    number = int(match.group("number") or 0)
    return release, (rank, number)


def _compare_versions(left: str, right: str) -> int:
    left_release, left_phase = _parse_version(left)
    right_release, right_phase = _parse_version(right)
    width = max(len(left_release), len(right_release))
    left_key = left_release + (0,) * (width - len(left_release))
    right_key = right_release + (0,) * (width - len(right_release))
    if left_key != right_key:
        return -1 if left_key < right_key else 1
    if left_phase == right_phase:
        return 0
    return -1 if left_phase < right_phase else 1


def _compatible_upper_bound(version: str) -> str:
    release, _phase = _parse_version(version)
    if len(release) == 1:
        return str(release[0] + 1)
    prefix = list(release[:-1])
    prefix[-1] += 1
    return ".".join(str(part) for part in prefix)


def _version_satisfies(current: str, requirement: str, *, bare_minimum: bool = False) -> bool:
    """Evaluate the common PEP 440 comparison subset used by badge manifests."""

    _parse_version(current)
    clauses = [clause.strip() for clause in requirement.split(",")]
    if not clauses or any(not clause for clause in clauses):
        raise ValueError("empty version constraint")
    for clause in clauses:
        match = _SPECIFIER_RE.fullmatch(clause)
        if match is None:
            if bare_minimum and len(clauses) == 1:
                operator, wanted = ">=", clause
            else:
                raise ValueError(f"unsupported version constraint {clause!r}")
        else:
            operator, wanted = match.groups()
        comparison = _compare_versions(current, wanted)
        accepted = {
            "==": comparison == 0,
            "!=": comparison != 0,
            ">=": comparison >= 0,
            "<=": comparison <= 0,
            ">": comparison > 0,
            "<": comparison < 0,
        }
        if operator == "~=":
            accepted[operator] = comparison >= 0 and _compare_versions(
                current, _compatible_upper_bound(wanted)
            ) < 0
        if not accepted[operator]:
            return False
    return True


def _installed_launcher_version() -> str:
    try:
        return metadata.version("beaglebadge-launcher")
    except metadata.PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        try:
            with pyproject.open("rb") as stream:
                project = tomllib.load(stream).get("project", {})
            version = project.get("version", "")
            if isinstance(version, str):
                _parse_version(version)
                return version
        except (OSError, ValueError, AttributeError):
            pass
        # An unpackaged embedding without version metadata is intentionally
        # older than every released launcher.
        return "0"


def _root_apps_explicitly_allowed() -> bool:
    return os.environ.get(UNSAFE_ROOT_APPS_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _command_message(result: CommandResult) -> str:
    return (result.stderr or result.stdout or f"command exited {result.returncode}").strip()


class AppStore:
    """Browse, install, update, roll back, and remove Badge applications."""

    def __init__(
        self,
        store_url: str = DEFAULT_STORE_URL,
        *,
        cache_dir: str | os.PathLike[str] | None = None,
        install_root: str | os.PathLike[str] | None = None,
        runner: CommandRunner | None = None,
        dependency_installer: DependencyInstaller | None = None,
        python_version: str | None = None,
        sdk_version: str | None = None,
        launcher_version: str | None = None,
    ) -> None:
        data_root = Path(
            os.environ.get("BADGE_DATA_DIR", Path.home() / ".local" / "share" / "beaglebadge")
        ).expanduser()
        self.store_url = _validated_remote(store_url, "store URL")
        self.cache_dir = Path(cache_dir or data_root / "store-cache").expanduser().resolve()
        self.install_root = Path(install_root or data_root / "installed-apps").expanduser().resolve()
        self.runner = runner or CommandRunner()
        self.dependency_installer = dependency_installer
        self.python_version = python_version or platform.python_version()
        if sdk_version is None:
            from badge_sdk import SDK_API

            sdk_version = SDK_API
        self.sdk_version = sdk_version
        self.launcher_version = launcher_version or _installed_launcher_version()
        self._catalog: tuple[CatalogApp, ...] = ()
        self._lock = threading.RLock()

    @property
    def catalog(self) -> tuple[CatalogApp, ...]:
        return self._catalog

    def _git(self, args: list[str], *, timeout: float = 60) -> CommandResult:
        return self.runner.run(["git", *args], timeout=timeout)

    def check_compatibility(self, manifest: AppManifest) -> None:
        """Raise when a v2 manifest cannot run in this launcher process."""

        if manifest.legacy:
            raise LegacyPortRequired(manifest.app_id)
        exact_contracts = (
            ("ui", manifest.ui, SUPPORTED_UI),
            ("execution", manifest.execution, SUPPORTED_EXECUTION),
        )
        for field, required, current in exact_contracts:
            if required != current:
                raise CompatibilityError(manifest.app_id, field, required, current)
        version_contracts = (
            ("requires_python", manifest.requires_python, self.python_version, False),
            ("requires_sdk", manifest.requires_sdk, self.sdk_version, False),
            (
                "min_badge_version",
                manifest.minimum_launcher,
                self.launcher_version,
                True,
            ),
        )
        for field, required, current, bare_minimum in version_contracts:
            if not required:
                continue
            try:
                compatible = _version_satisfies(
                    current, required, bare_minimum=bare_minimum
                )
            except ValueError as exc:
                raise CompatibilityError(
                    manifest.app_id, field, required, f"{current} ({exc})"
                ) from exc
            if not compatible:
                raise CompatibilityError(manifest.app_id, field, required, current)

    def refresh(self, *, update: bool = True) -> tuple[CatalogApp, ...]:
        """Clone/update the catalog and return validated entries.

        If an update fails but a complete cached catalog exists, the cache is
        still loaded so the badge remains useful offline.
        """

        with self._lock:
            self.cache_dir.parent.mkdir(parents=True, exist_ok=True)
            update_error = ""
            if not self.cache_dir.exists():
                temporary = self.cache_dir.parent / f".store-clone-{uuid.uuid4().hex}"
                result = self._git(
                    ["clone", "--depth", "1", "--", self.store_url, str(temporary)],
                    timeout=120,
                )
                if not result.ok:
                    self._remove_managed(self.cache_dir.parent, temporary)
                    raise StoreError(f"could not clone app store: {_command_message(result)}")
                try:
                    os.replace(temporary, self.cache_dir)
                except OSError:
                    self._remove_managed(self.cache_dir.parent, temporary)
                    raise
            elif update and (self.cache_dir / ".git").exists():
                result = self._git(
                    ["-C", str(self.cache_dir), "pull", "--ff-only"], timeout=60
                )
                if not result.ok:
                    update_error = _command_message(result)
            try:
                self._catalog = tuple(self._load_catalog())
            except Exception as exc:
                if update_error:
                    raise CatalogError(
                        f"catalog update failed ({update_error}) and cached catalog is invalid: {exc}"
                    ) from exc
                raise
            return self._catalog

    def _load_catalog(self) -> list[CatalogApp]:
        manifest_path = self.cache_dir / "manifest.json"
        entries: list[CatalogApp] = []
        if manifest_path.is_file():
            try:
                catalog = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CatalogError(f"cannot read catalog manifest: {exc}") from exc
            if not isinstance(catalog, Mapping) or not isinstance(catalog.get("apps"), list):
                raise CatalogError("catalog manifest must contain an apps list")
            v2_catalog = catalog.get("schema_version") in (2, "2", "2.0")
            default_updated = catalog.get("last_updated", "")
            for raw in catalog["apps"]:
                if not isinstance(raw, Mapping):
                    raise CatalogError("catalog app entries must be objects")
                try:
                    if v2_catalog or raw.get("schema_version") in (2, "2", "2.0"):
                        normalized = dict(raw)
                        normalized.setdefault("schema_version", 2)
                        app_manifest = parse_v2_json(normalized, source_file=manifest_path)
                    else:
                        app_manifest = adapt_v1_metadata(raw, source_file=manifest_path)
                except ManifestError as exc:
                    raise CatalogError(f"invalid catalog app entry: {exc}") from exc
                source_dir = contained_path(
                    self.cache_dir, "apps", app_manifest.app_id, "app"
                )
                stars = raw.get("stars", 0)
                if not isinstance(stars, int) or isinstance(stars, bool) or stars < 0:
                    raise CatalogError(f"invalid star count for {app_manifest.app_id}")
                updated = raw.get("updated_at", raw.get("last_updated", default_updated))
                if not isinstance(updated, str):
                    raise CatalogError(f"invalid update timestamp for {app_manifest.app_id}")
                try:
                    source_ref = _validated_source_ref(
                        raw.get("commit", raw.get("source_ref", ""))
                    )
                except StoreError as exc:
                    raise CatalogError(
                        f"invalid source ref for {app_manifest.app_id}: {exc}"
                    ) from exc
                entries.append(
                    CatalogApp(app_manifest, source_dir, source_ref, stars, updated)
                )
        else:
            # Explicit compatibility with the original store layout.
            apps_root = self.cache_dir / "apps"
            if not apps_root.is_dir():
                raise CatalogError("catalog contains neither manifest.json nor apps/")
            for metadata in sorted(apps_root.glob("*/metadata.json")):
                try:
                    manifest = load_manifest(metadata)
                except ManifestError as exc:
                    raise CatalogError(f"invalid {metadata}: {exc}") from exc
                source_dir = contained_path(self.cache_dir, "apps", manifest.app_id, "app")
                entries.append(CatalogApp(manifest, source_dir))

        seen: set[str] = set()
        for entry in entries:
            if entry.id in seen:
                raise CatalogError(f"duplicate catalog app id: {entry.id}")
            seen.add(entry.id)
        return sorted(entries, key=lambda item: (item.name.casefold(), item.id))

    def browse(self, *, category: str | None = None, sort: str = "name") -> list[CatalogApp]:
        apps = list(self._catalog)
        if category:
            requested = category.lower()
            if requested in {"demo", "demos"}:
                apps = [app for app in apps if app.category in {"demo", "demos"}]
            else:
                apps = [app for app in apps if app.category == requested]
        if sort == "stars":
            apps.sort(key=lambda app: (-app.stars, app.name.casefold(), app.id))
        elif sort == "recent":
            apps.sort(key=lambda app: (app.updated_at, app.name.casefold()), reverse=True)
        elif sort == "name":
            apps.sort(key=lambda app: (app.name.casefold(), app.id))
        else:
            raise ValueError("sort must be 'name', 'stars', or 'recent'")
        return apps

    def find(self, app_id: str) -> CatalogApp | None:
        app_id = validate_app_id(app_id)
        return next((app for app in self._catalog if app.id == app_id), None)

    def _app_path(self, app_id: str) -> Path:
        return contained_path(self.install_root, validate_app_id(app_id))

    def _rollback_path(self, app_id: str) -> Path:
        return contained_path(self.install_root, ".rollback", validate_app_id(app_id))

    def _descriptor(self, app_id: str) -> Path:
        return contained_path(self._app_path(app_id), INSTALL_DESCRIPTOR)

    def is_installed(self, app_id: str) -> bool:
        try:
            return self._descriptor(app_id).is_file()
        except ManifestError:
            return False

    def rollback_available(self, app_id: str) -> bool:
        """Return whether a validated previous version is ready to swap in."""

        with self._lock:
            try:
                rollback = self._rollback_path(app_id)
                descriptor = contained_path(rollback, INSTALL_DESCRIPTOR)
            except ManifestError:
                return False
            if rollback.is_symlink() or not rollback.is_dir() or descriptor.is_symlink():
                return False
            try:
                load_manifest(descriptor)
            except (OSError, ManifestError):
                return False
            return True

    def installed_manifest(self, app_id: str) -> AppManifest | None:
        descriptor = self._descriptor(app_id)
        if not descriptor.is_file():
            return None
        try:
            return load_manifest(descriptor)
        except ManifestError as exc:
            raise StoreError(f"installed metadata for {app_id} is invalid: {exc}") from exc

    def installed(self) -> list[InstalledApp]:
        if not self.install_root.is_dir():
            return []
        result: list[InstalledApp] = []
        for candidate in self.install_root.iterdir():
            if not candidate.is_dir() or candidate.name.startswith("."):
                continue
            try:
                manifest = self.installed_manifest(candidate.name)
            except (ManifestError, StoreError):
                continue
            if manifest:
                result.append(InstalledApp(manifest, candidate))
        return sorted(result, key=lambda item: item.manifest.name.casefold())

    def _resolved_commit(self, repository: Path, expression: str) -> str:
        result = self._git(
            ["-C", str(repository), "rev-parse", "--verify", f"{expression}^{{commit}}"]
        )
        commit = result.stdout.strip()
        if not result.ok or not _RESOLVED_COMMIT_RE.fullmatch(commit):
            detail = _command_message(result) if not result.ok else "git returned an invalid hash"
            raise StoreError(f"could not resolve source revision: {detail}")
        return commit.lower()

    def _catalog_submodule(self, source: Path) -> tuple[bool, str]:
        try:
            relative = source.resolve(strict=False).relative_to(self.cache_dir.resolve())
        except ValueError:
            return False, ""
        relative_text = relative.as_posix()
        if not (self.cache_dir / ".git").exists():
            return False, relative_text
        result = self._git(
            ["-C", str(self.cache_dir), "ls-files", "--stage", "--", relative_text]
        )
        is_submodule = result.ok and any(
            line.startswith("160000 ") for line in result.stdout.splitlines()
        )
        return is_submodule, relative_text

    def _source_matches_ref(self, source: Path, source_ref: str) -> bool:
        if not (source / ".git").exists():
            return False
        try:
            selected = self._resolved_commit(source, source_ref)
            current = self._resolved_commit(source, "HEAD")
        except StoreError:
            return False
        return selected == current

    def _prepare_source(self, app: CatalogApp, destination: Path) -> None:
        source_ref = _validated_source_ref(app.source_ref)
        source = app.source_dir
        source_error = ""
        if source is not None:
            is_submodule, relative = self._catalog_submodule(source)
            if not relative or relative == ".":
                source_error = "catalog source escapes the managed store cache"
            elif is_submodule:
                # Run this even for a populated directory: refresh() may have
                # advanced the catalog's gitlink while leaving the old checkout.
                result = self._git(
                    [
                        "-C",
                        str(self.cache_dir),
                        "submodule",
                        "update",
                        "--init",
                        "--recursive",
                        "--",
                        relative,
                    ],
                    timeout=180,
                )
                if not result.ok:
                    source_error = _command_message(result)

            source_ready = bool(
                not source_error and source.is_dir() and any(source.iterdir())
            )
            if source_ready and (
                not source_ref or self._source_matches_ref(source, source_ref)
            ):
                self._copy_tree_contents(source, destination)
                return
            if source_ready and source_ref and not source_error:
                source_error = f"cached source is not revision {source_ref}"

        repository = app.repository_url
        if not repository:
            detail = f": {source_error}" if source_error else ""
            raise StoreError(f"{app.id} has no usable install source{detail}")
        repository = _validated_remote(repository)
        clone_path = destination.parent / "source-clone"
        result = self._git(
            ["clone", "--depth", "1", "--", repository, str(clone_path)], timeout=180
        )
        if not result.ok:
            detail = _command_message(result)
            if source_error:
                detail = f"catalog source failed ({source_error}); repository clone failed ({detail})"
            raise StoreError(f"could not fetch {app.name}: {detail}")
        if source_ref:
            # A shallow default-branch clone need not contain a requested tag
            # or commit. Fetch the validated ref, resolve it to an object ID,
            # then checkout only that hash so no catalog text becomes an option.
            result = self._git(
                ["-C", str(clone_path), "fetch", "--depth", "1", "origin", source_ref],
                timeout=180,
            )
            if not result.ok:
                raise StoreError(
                    f"could not fetch source revision {source_ref}: {_command_message(result)}"
                )
            commit = self._resolved_commit(clone_path, "FETCH_HEAD")
            result = self._git(
                ["-C", str(clone_path), "checkout", "--detach", commit, "--"], timeout=60
            )
            if not result.ok:
                raise StoreError(f"could not select {commit}: {_command_message(result)}")
        self._copy_tree_contents(clone_path, destination)

    def _copy_tree_contents(self, source: Path, destination: Path) -> None:
        source = source.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        for directory, names, files in os.walk(source, followlinks=False):
            directory_path = Path(directory)
            relative = directory_path.relative_to(source)
            if any((directory_path / name).is_symlink() for name in names):
                raise StoreError("application packages may not contain directory symlinks")
            names[:] = [
                name
                for name in names
                if name not in {".git", "__pycache__", ".pytest_cache", ".mypy_cache"}
            ]
            target_directory = destination if relative == Path(".") else contained_path(
                destination, str(relative)
            )
            target_directory.mkdir(parents=True, exist_ok=True)
            for filename in files:
                if filename == ".git" or filename.endswith((".pyc", ".pyo")):
                    continue
                source_file = directory_path / filename
                if source_file.is_symlink() or not source_file.is_file():
                    raise StoreError("application packages may contain only regular files")
                target_file = contained_path(target_directory, filename)
                shutil.copy2(source_file, target_file)

    def _validate_staged(self, app: CatalogApp, payload: Path) -> None:
        manifest = app.manifest
        if manifest.legacy:
            candidate = contained_path(payload, manifest.legacy_main_file)
            if not candidate.is_file():
                raise StoreError(
                    f"package for {manifest.app_id} does not contain {manifest.legacy_main_file}"
                )
            return

        package_manifest: AppManifest | None = None
        for filename in ("pyproject.toml", "badge-app.json", "app.json"):
            candidate = payload / filename
            if candidate.is_file():
                try:
                    package_manifest = load_manifest(candidate)
                except ManifestError as exc:
                    raise StoreError(f"invalid package manifest: {exc}") from exc
                break
        if package_manifest is None:
            raise StoreError("v2 package does not contain pyproject.toml or badge-app.json")
        expected = (manifest.app_id, manifest.version, manifest.entry_point)
        actual = (
            package_manifest.app_id,
            package_manifest.version,
            package_manifest.entry_point,
        )
        if expected != actual:
            raise StoreError("catalog and package metadata do not match")
        module_name = manifest.entry_point.split(":", 1)[0]
        relative = Path(*module_name.split("."))
        candidates = (
            payload / "src" / (str(relative) + ".py"),
            payload / "src" / relative / "__init__.py",
            payload / (str(relative) + ".py"),
            payload / relative / "__init__.py",
        )
        if not any(candidate.is_file() for candidate in candidates):
            raise StoreError(f"entry-point module {module_name!r} is absent from package")

    def _write_descriptor(self, payload: Path, manifest: AppManifest) -> Path:
        descriptor = contained_path(payload, INSTALL_DESCRIPTOR)
        temporary = contained_path(payload, f"{INSTALL_DESCRIPTOR}.{uuid.uuid4().hex}.tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(manifest.as_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, descriptor)
        return descriptor

    def install(self, app: CatalogApp | str) -> InstalledApp:
        """Stage and atomically install/update one catalog application."""

        with self._lock:
            if isinstance(app, str):
                found = self.find(app)
                if found is None:
                    raise StoreError(f"app not found in catalog: {app}")
                app = found
            validate_app_id(app.id)
            if app.manifest.legacy:
                raise LegacyPortRequired(app.id)
            self.check_compatibility(app.manifest)
            dependencies = app.dependencies
            self.install_root.mkdir(parents=True, exist_ok=True)
            staging_root = contained_path(self.install_root, ".staging")
            staging_root.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix=f"{app.id}-", dir=staging_root)).resolve()
            payload = contained_path(stage, "payload")
            payload.mkdir()
            destination = self._app_path(app.id)
            previous = self.installed_manifest(app.id)
            transaction_backup = contained_path(
                self.install_root, ".rollback", f".{app.id}-{uuid.uuid4().hex}"
            )
            transaction_backup.parent.mkdir(parents=True, exist_ok=True)
            moved_previous = False
            try:
                self._prepare_source(app, payload)
                self._validate_staged(app, payload)
                if dependencies:
                    if self.dependency_installer is None:
                        raise DependencyResolutionRequired(app.id, dependencies)
                    self.dependency_installer(app.manifest, payload)
                descriptor = self._write_descriptor(payload, app.manifest)
                # Re-parse what will be used after installation before swapping.
                load_manifest(descriptor)

                rollback = self._rollback_path(app.id)
                if rollback.is_symlink() or (rollback.exists() and not rollback.is_dir()):
                    raise StoreError(f"rollback path for {app.id} is not a regular directory")
                if destination.exists() or destination.is_symlink():
                    if destination.is_symlink() or not destination.is_dir():
                        raise StoreError(f"installed path for {app.id} is not a regular directory")
                    os.replace(destination, transaction_backup)
                    moved_previous = True
                try:
                    os.replace(payload, destination)
                except Exception:
                    if moved_previous and transaction_backup.exists():
                        os.replace(transaction_backup, destination)
                    raise

                if moved_previous:
                    older_rollback = contained_path(stage, "older-rollback")
                    try:
                        if rollback.exists():
                            os.replace(rollback, older_rollback)
                        os.replace(transaction_backup, rollback)
                    except Exception:
                        failed_payload = contained_path(stage, "failed-payload")
                        if destination.exists():
                            os.replace(destination, failed_payload)
                        if transaction_backup.exists():
                            os.replace(transaction_backup, destination)
                        if older_rollback.exists() and not rollback.exists():
                            os.replace(older_rollback, rollback)
                        raise
                return InstalledApp(
                    app.manifest.with_source(destination / INSTALL_DESCRIPTOR),
                    destination,
                    updated=previous is not None,
                    previous_version=previous.version if previous else "",
                )
            except Exception:
                if moved_previous and not destination.exists() and transaction_backup.exists():
                    os.replace(transaction_backup, destination)
                raise
            finally:
                if stage.exists():
                    self._remove_managed(self.install_root, stage)

    def rollback(self, app_id: str) -> InstalledApp:
        """Atomically swap the current and previous installed versions."""

        with self._lock:
            app_id = validate_app_id(app_id)
            current = self._app_path(app_id)
            rollback = self._rollback_path(app_id)
            if not current.is_dir() or not rollback.is_dir():
                raise StoreError(f"no rollback is available for {app_id}")
            temporary = contained_path(
                self.install_root, ".rollback", f".{app_id}-swap-{uuid.uuid4().hex}"
            )
            os.replace(current, temporary)
            try:
                os.replace(rollback, current)
                os.replace(temporary, rollback)
            except Exception:
                if not current.exists() and temporary.exists():
                    os.replace(temporary, current)
                raise
            manifest = self.installed_manifest(app_id)
            if manifest is None:  # pragma: no cover - guarded by validated descriptors.
                raise StoreError(f"rollback metadata disappeared for {app_id}")
            return InstalledApp(manifest, current, updated=True)

    def uninstall(self, app_id: str) -> bool:
        """Remove application code while leaving external app data untouched."""

        with self._lock:
            app_id = validate_app_id(app_id)
            destination = self._app_path(app_id)
            if not destination.exists() and not destination.is_symlink():
                return False
            trash = contained_path(
                self.install_root, ".trash", f"{app_id}-{uuid.uuid4().hex}"
            )
            trash.parent.mkdir(parents=True, exist_ok=True)
            os.replace(destination, trash)
            self._remove_managed(self.install_root, trash)
            rollback = self._rollback_path(app_id)
            if rollback.exists() or rollback.is_symlink():
                self._remove_managed(self.install_root, rollback)
            return True

    # Friendly alias used by the original UI terminology.
    delete = uninstall

    def launch(self, app_id: str) -> object:
        """Lazily load an installed app only when launch is requested."""

        app_id = validate_app_id(app_id)
        manifest = self.installed_manifest(app_id)
        if manifest is None:
            raise StoreError(f"app is not installed: {app_id}")
        if manifest.legacy:
            raise LegacyPortRequired(app_id)
        self.check_compatibility(manifest)
        get_effective_uid = getattr(os, "geteuid", None)
        if (
            callable(get_effective_uid)
            and get_effective_uid() == 0
            and not _root_apps_explicitly_allowed()
        ):
            raise UnsafeExecutionError(app_id)
        try:
            return load_app_entrypoint(manifest, self._app_path(app_id))
        except (ManifestError, ImportError, AttributeError, TypeError) as exc:
            raise StoreError(f"could not launch {app_id}: {exc}") from exc

    def project_url(self, app_id: str) -> str:
        app = self.find(app_id)
        return app.project_url if app else ""

    @staticmethod
    def _remove_managed(root: Path, target: Path) -> None:
        """Remove one verified child without invoking a shell."""

        try:
            relative = target.resolve(strict=False).relative_to(root.resolve())
        except ValueError as exc:
            raise StoreError(f"refusing to remove path outside managed root: {target}") from exc
        if relative == Path("."):
            raise StoreError("refusing to remove managed root")
        if target.is_symlink() or target.is_file():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            shutil.rmtree(target)


__all__ = [
    "AppStore",
    "CatalogApp",
    "CatalogError",
    "CompatibilityError",
    "DEFAULT_STORE_URL",
    "DependencyResolutionRequired",
    "InstalledApp",
    "LegacyPortRequired",
    "StoreError",
    "UnsafeExecutionError",
]
