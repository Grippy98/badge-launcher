"""Safe application metadata parsing and lazy entry-point loading.

Discovery in this module deliberately reads manifests only.  Application code
is imported only by :func:`load_app_entrypoint`, after the user has selected an
application to launch.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, replace
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import types
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse
import uuid
import weakref

try:
    import tomllib
except ImportError:  # pragma: no cover - CPython 3.11+ always has tomllib.
    tomllib = None  # type: ignore[assignment]


APP_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+!-]{0,63}$")
MODULE_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
OBJECT_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")
MANIFEST_FILENAMES = ("pyproject.toml", "badge-app.json", "app.json", "metadata.json")


class ManifestError(ValueError):
    """Raised when app metadata is malformed or unsafe."""


def validate_app_id(value: object) -> str:
    """Return a validated app ID suitable for use as one path component."""

    if not isinstance(value, str) or not APP_ID_RE.fullmatch(value):
        raise ManifestError(
            "app id must be 1-64 lowercase ASCII letters, digits, or hyphens "
            "and may not start or end with a hyphen"
        )
    return value


def contained_path(root: str | os.PathLike[str], *parts: str, allow_root: bool = False) -> Path:
    """Resolve *parts* beneath *root* and reject traversal and symlink escapes."""

    base = Path(root).expanduser().resolve()
    candidate = base.joinpath(*parts).resolve(strict=False)
    try:
        relative = candidate.relative_to(base)
    except ValueError as exc:
        raise ManifestError(f"path escapes managed root: {candidate}") from exc
    if not allow_root and relative == Path("."):
        raise ManifestError("operation may not target the managed root itself")
    return candidate


def _required_string(data: Mapping[str, Any], key: str, *, maximum: int = 1024) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{key} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum or any(ord(character) < 32 for character in value):
        raise ManifestError(f"{key} contains invalid characters or is too long")
    return value


def _optional_string(
    data: Mapping[str, Any], key: str, default: str = "", *, maximum: int = 1024
) -> str:
    value = data.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ManifestError(f"{key} must be a string")
    value = value.strip()
    if len(value) > maximum or any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ManifestError(f"{key} contains invalid characters or is too long")
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ManifestError(f"{field} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ManifestError(f"{field} must contain only non-empty strings")
        item = item.strip()
        if len(item) > 256 or any(ord(character) < 32 for character in item):
            raise ManifestError(f"invalid value in {field}")
        if item not in result:
            result.append(item)
    return tuple(result)


def _safe_url(value: object, field: str) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str) or len(value) > 2048:
        raise ManifestError(f"{field} must be a URL string")
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ManifestError(f"{field} must use an http or https URL")
    if parsed.username or parsed.password or any(ord(character) < 32 for character in value):
        raise ManifestError(f"{field} contains unsafe URL components")
    return value


def _entry_point(value: object) -> str:
    if not isinstance(value, str) or value.count(":") != 1:
        raise ManifestError("entry_point must use the form 'module:object'")
    module_name, object_name = value.split(":", 1)
    if not MODULE_RE.fullmatch(module_name) or not OBJECT_RE.fullmatch(object_name):
        raise ManifestError("entry_point contains an invalid module or object name")
    return value


def _safe_version(value: object) -> str:
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise ManifestError("version contains unsupported characters")
    return value


def _safe_category(value: object) -> str:
    if not isinstance(value, str):
        raise ManifestError("category must be a string")
    value = value.strip().lower()
    if not APP_ID_RE.fullmatch(value):
        raise ManifestError("category must be a lowercase identifier")
    return value


def _author_from_project(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, list):
        raise ManifestError("project.authors must be a list")
    names: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ManifestError("project.authors entries must be tables")
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return ", ".join(names)


def _license_from_project(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        candidate = value.get("text") or value.get("file") or ""
        if isinstance(candidate, str):
            return candidate.strip()
    raise ManifestError("project.license must be a string or table")


@dataclass(frozen=True, slots=True)
class AppManifest:
    """Normalized metadata for both native CPython and legacy applications."""

    schema_version: int
    app_id: str
    name: str
    version: str
    category: str
    entry_point: str
    description: str = ""
    author: str = ""
    license: str = ""
    project_url: str = ""
    repository_url: str = ""
    dependencies: tuple[str, ...] = ()
    system_dependencies: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    requires_python: str = ""
    requires_sdk: str = ""
    minimum_launcher: str = ""
    ui: str = "portable-v1"
    execution: str = "in-process"
    legacy_main_file: str = ""
    source_file: Path | None = None

    @property
    def id(self) -> str:
        """Compatibility alias matching catalog JSON field names."""

        return self.app_id

    @property
    def legacy(self) -> bool:
        return self.schema_version == 1

    @property
    def all_dependencies(self) -> tuple[str, ...]:
        return self.dependencies + self.system_dependencies

    @property
    def app_root(self) -> Path | None:
        return self.source_file.parent if self.source_file else None

    def with_source(self, source_file: str | os.PathLike[str]) -> "AppManifest":
        return replace(self, source_file=Path(source_file).resolve())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.app_id,
            "name": self.name,
            "version": self.version,
            "category": self.category,
            "entry_point": self.entry_point,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "homepage": self.project_url,
            "repo": self.repository_url,
            "dependencies": list(self.dependencies),
            "system_dependencies": list(self.system_dependencies),
            "permissions": list(self.permissions),
            "requires_python": self.requires_python,
            "requires_sdk": self.requires_sdk,
            "min_badge_version": self.minimum_launcher,
            "ui": self.ui,
            "execution": self.execution,
            "main_file": self.legacy_main_file,
        }


def adapt_v1_metadata(data: Mapping[str, Any], *, source_file: Path | None = None) -> AppManifest:
    """Normalize the original badge-app-store ``metadata.json`` contract."""

    app_id = validate_app_id(data.get("id"))
    main_file = _optional_string(data, "main_file", f"{app_id.replace('-', '_')}_app.py", maximum=128)
    if Path(main_file).name != main_file or not main_file.endswith(".py"):
        raise ManifestError("legacy main_file must be a Python filename without directories")
    module_name = main_file[:-3]
    if not MODULE_RE.fullmatch(module_name):
        raise ManifestError("legacy main_file is not importable")
    system_dependencies = list(_string_list(data.get("system_dependencies"), "system_dependencies"))
    requires_img2bin = data.get("requires_img2bin", False)
    if not isinstance(requires_img2bin, bool):
        raise ManifestError("requires_img2bin must be a boolean")
    if requires_img2bin and "img2bin" not in system_dependencies:
        system_dependencies.append("img2bin")
    project_url = _safe_url(data.get("homepage") or data.get("project_url") or data.get("repo"), "homepage")
    repository_url = _safe_url(data.get("repo"), "repo")
    return AppManifest(
        schema_version=1,
        app_id=app_id,
        name=_required_string(data, "name", maximum=80),
        version=_safe_version(data.get("version", "0")),
        category=_safe_category(data.get("category", "apps")),
        entry_point=f"{module_name}:legacy",
        description=_optional_string(data, "description", maximum=1024),
        author=_optional_string(data, "author", maximum=160),
        license=_optional_string(data, "license", maximum=128),
        project_url=project_url,
        repository_url=repository_url,
        dependencies=_string_list(data.get("dependencies"), "dependencies"),
        system_dependencies=tuple(system_dependencies),
        permissions=_string_list(data.get("permissions"), "permissions"),
        minimum_launcher=_optional_string(data, "min_badge_version", maximum=64),
        ui="legacy-lvgl",
        execution="legacy-in-process",
        legacy_main_file=main_file,
        source_file=source_file.resolve() if source_file else None,
    )


def parse_v2_json(data: Mapping[str, Any], *, source_file: Path | None = None) -> AppManifest:
    """Parse a standalone v2 JSON application manifest."""

    runtime = data.get("runtime", {})
    if runtime is None:
        runtime = {}
    if not isinstance(runtime, Mapping):
        raise ManifestError("runtime must be an object")
    schema = data.get("schema_version", data.get("manifest_version"))
    if schema not in (2, "2", "2.0"):
        raise ManifestError("unsupported JSON manifest schema_version")
    app_id = validate_app_id(data.get("id"))
    entry = data.get("entry_point", data.get("entrypoint", runtime.get("entry_point")))
    project_url = _safe_url(data.get("homepage") or data.get("project_url") or data.get("repo"), "homepage")
    return AppManifest(
        schema_version=2,
        app_id=app_id,
        name=_required_string(data, "name", maximum=80),
        version=_safe_version(data.get("version")),
        category=_safe_category(data.get("category", "apps")),
        entry_point=_entry_point(entry),
        description=_optional_string(data, "description", maximum=1024),
        author=_optional_string(data, "author", maximum=160),
        license=_optional_string(data, "license", maximum=128),
        project_url=project_url,
        repository_url=_safe_url(data.get("repo") or data.get("repository_url"), "repo"),
        dependencies=_string_list(data.get("dependencies"), "dependencies"),
        system_dependencies=_string_list(data.get("system_dependencies"), "system_dependencies"),
        permissions=_string_list(data.get("permissions", runtime.get("permissions")), "permissions"),
        requires_python=_optional_string(
            {"requires_python": data.get("requires_python", runtime.get("python", ""))},
            "requires_python",
            maximum=128,
        ),
        requires_sdk=_optional_string(
            {"requires_sdk": data.get("requires_sdk", runtime.get("sdk", runtime.get("api", "")))},
            "requires_sdk",
            maximum=128,
        ),
        minimum_launcher=_optional_string(data, "min_badge_version", maximum=64),
        ui=_optional_string({"ui": data.get("ui", runtime.get("ui", "portable-v1"))}, "ui", maximum=64),
        execution=_optional_string(
            {"execution": data.get("execution", runtime.get("execution", "in-process"))},
            "execution",
            maximum=64,
        ),
        source_file=source_file.resolve() if source_file else None,
    )


def parse_pyproject(data: Mapping[str, Any], *, source_file: Path | None = None) -> AppManifest:
    """Parse the standard-Python ``pyproject.toml`` badge extension."""

    project = data.get("project")
    tools = data.get("tool")
    if not isinstance(project, Mapping) or not isinstance(tools, Mapping):
        raise ManifestError("pyproject must contain [project] and [tool.beaglebadge]")
    badge = tools.get("beaglebadge")
    if not isinstance(badge, Mapping):
        raise ManifestError("pyproject is not a badge app: missing [tool.beaglebadge]")
    schema = badge.get("schema_version", badge.get("schema"))
    if schema not in (2, "2", "2.0"):
        raise ManifestError("unsupported [tool.beaglebadge] schema_version")
    app_id = validate_app_id(badge.get("id"))

    groups = project.get("entry-points", {})
    group = groups.get("beaglebadge.apps", {}) if isinstance(groups, Mapping) else {}
    entry: object = badge.get("entry_point")
    if entry is None and isinstance(group, Mapping):
        entry = group.get(app_id)
        if entry is None and len(group) == 1:
            entry = next(iter(group.values()))

    urls = project.get("urls", {})
    if not isinstance(urls, Mapping):
        raise ManifestError("project.urls must be a table")
    homepage = urls.get("Homepage") or urls.get("homepage") or urls.get("Repository") or urls.get("repository")
    repository = urls.get("Repository") or urls.get("repository") or homepage
    project_name = project.get("name")
    display_name = badge.get("display_name", project_name)
    if not isinstance(display_name, str):
        raise ManifestError("display_name must be a string")
    description = project.get("description", "")
    if not isinstance(description, str):
        raise ManifestError("project.description must be a string")
    dependencies = project.get("dependencies", [])

    return AppManifest(
        schema_version=2,
        app_id=app_id,
        name=_required_string({"name": display_name}, "name", maximum=80),
        version=_safe_version(project.get("version")),
        category=_safe_category(badge.get("category", "apps")),
        entry_point=_entry_point(entry),
        description=_optional_string({"description": description}, "description", maximum=1024),
        author=_author_from_project(project.get("authors")),
        license=_license_from_project(project.get("license")),
        project_url=_safe_url(homepage, "project.urls.Homepage"),
        repository_url=_safe_url(repository, "project.urls.Repository"),
        dependencies=_string_list(dependencies, "project.dependencies"),
        system_dependencies=_string_list(badge.get("system_dependencies"), "system_dependencies"),
        permissions=_string_list(badge.get("permissions"), "permissions"),
        requires_python=_optional_string(
            {"requires_python": project.get("requires-python", "")}, "requires_python", maximum=128
        ),
        requires_sdk=_optional_string(
            {"requires_sdk": badge.get("sdk", "")}, "requires_sdk", maximum=128
        ),
        minimum_launcher=_optional_string(
            {"minimum_launcher": badge.get("minimum_launcher", "")}, "minimum_launcher", maximum=64
        ),
        ui=_optional_string({"ui": badge.get("ui", "portable-v1")}, "ui", maximum=64),
        execution=_optional_string(
            {"execution": badge.get("execution", "in-process")}, "execution", maximum=64
        ),
        source_file=source_file.resolve() if source_file else None,
    )


def load_manifest(path: str | os.PathLike[str]) -> AppManifest:
    """Load a v2 JSON/pyproject manifest or adapt an explicit v1 metadata file."""

    source = Path(path).expanduser().resolve()
    try:
        if source.name == "pyproject.toml":
            if tomllib is None:  # pragma: no cover
                raise ManifestError("pyproject manifests require Python 3.11 or tomli")
            with source.open("rb") as stream:
                data = tomllib.load(stream)
            return parse_pyproject(data, source_file=source)
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"cannot read manifest {source}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ManifestError("manifest root must be an object")
    schema = data.get("schema_version", data.get("manifest_version"))
    if schema in (2, "2", "2.0"):
        return parse_v2_json(data, source_file=source)
    if source.name != "metadata.json" and schema not in (1, "1", "1.0", None):
        raise ManifestError("unsupported manifest schema")
    return adapt_v1_metadata(data, source_file=source)


def _pyproject_is_badge_app(path: Path) -> bool:
    if tomllib is None:  # pragma: no cover
        return False
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
        return isinstance(data.get("tool", {}).get("beaglebadge"), Mapping)
    except (OSError, ValueError, AttributeError):
        return False


def discover_manifests(root: str | os.PathLike[str]) -> list[AppManifest]:
    """Discover apps beneath *root* without importing any application code."""

    base = Path(root).expanduser().resolve()
    if not base.exists():
        return []
    found: list[AppManifest] = []
    by_id: dict[str, Path] = {}
    ignored_directories = {".git", ".venv", "venv", "__pycache__", "node_modules"}
    for directory, names, files in os.walk(base, followlinks=False):
        names[:] = [name for name in names if name not in ignored_directories and not name.startswith(".")]
        directory_path = Path(directory)
        candidates: list[Path] = []
        if "pyproject.toml" in files:
            candidate = directory_path / "pyproject.toml"
            if _pyproject_is_badge_app(candidate):
                candidates.append(candidate)
        for filename in ("badge-app.json", "app.json", "metadata.json"):
            if filename in files:
                candidates.append(directory_path / filename)
        if not candidates:
            continue
        # The first supported v2 manifest is canonical; metadata.json is only
        # the fallback for legacy packages in the same directory.
        manifest = load_manifest(candidates[0])
        previous = by_id.get(manifest.app_id)
        if previous is not None:
            raise ManifestError(
                f"duplicate app id {manifest.app_id!r} in {previous} and {candidates[0]}"
            )
        by_id[manifest.app_id] = candidates[0]
        found.append(manifest)
        names[:] = []
    return sorted(found, key=lambda item: (item.category, item.name.casefold(), item.app_id))


def _ensure_namespace(name: str, search_paths: Iterable[Path] = ()) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__package__ = name
        module.__path__ = [str(path) for path in search_paths]  # type: ignore[attr-defined]
        sys.modules[name] = module
    return module


def _module_root(app_root: Path, module_name: str) -> Path:
    relative = Path(*module_name.split("."))
    for candidate_root in (app_root / "src", app_root):
        root = candidate_root.resolve(strict=False)
        file_candidate = contained_path(root, str(relative) + ".py")
        package_candidate = contained_path(root, str(relative), "__init__.py")
        if file_candidate.is_file() or package_candidate.is_file():
            # Resolve the actual file as well, catching a leaf symlink escape.
            chosen = file_candidate if file_candidate.is_file() else package_candidate
            try:
                chosen.resolve().relative_to(app_root.resolve())
            except ValueError as exc:
                raise ManifestError("entry point resolves outside the application") from exc
            return root
    raise ManifestError(f"entry-point module {module_name!r} was not found in {app_root}")


@dataclass(frozen=True, slots=True)
class _DynamicImportScope:
    search_root: Path
    canonical_root: str


_DYNAMIC_IMPORT_SCOPES: dict[str, _DynamicImportScope] = {}
_DYNAMIC_IMPORT_LOCK = threading.RLock()


def _scoped_importer(unique_root: str, canonical_root: str):
    """Return an import function that keeps one app's absolute imports private."""

    original_import = builtins.__import__
    private_canonical = f"{unique_root}.{canonical_root}"

    def scoped_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and (name == canonical_root or name.startswith(canonical_root + ".")):
            private_name = f"{unique_root}.{name}"
            imported = original_import(private_name, globals, locals, fromlist, 0)
            if fromlist:
                return imported
            # ``import package.helper`` must bind ``package``, not the shared
            # ``badge_dynamic`` namespace returned by the original importer.
            return sys.modules[private_canonical]
        return original_import(name, globals, locals, fromlist, level)

    return scoped_import


class _DynamicAppLoader(importlib.machinery.SourceFileLoader):
    """Source loader that gives every app module its scope-aware importer."""

    def __init__(
        self,
        fullname: str,
        path: str,
        unique_root: str,
        canonical_root: str,
    ) -> None:
        super().__init__(fullname, path)
        self.unique_root = unique_root
        self.canonical_root = canonical_root

    def exec_module(self, module) -> None:
        app_builtins = dict(vars(builtins))
        app_builtins["__import__"] = _scoped_importer(
            self.unique_root,
            self.canonical_root,
        )
        module.__dict__["__builtins__"] = app_builtins
        super().exec_module(module)


class _DynamicAppFinder(importlib.abc.MetaPathFinder):
    """Resolve UUID-namespaced app modules without global package aliases."""

    def find_spec(self, fullname: str, path=None, target=None):
        with _DYNAMIC_IMPORT_LOCK:
            match = next(
                (
                    (unique_root, scope)
                    for unique_root, scope in _DYNAMIC_IMPORT_SCOPES.items()
                    if fullname.startswith(unique_root + ".")
                ),
                None,
            )
        if match is None:
            return None
        unique_root, scope = match
        relative_name = fullname[len(unique_root) + 1 :]
        parts = relative_name.split(".")
        if not relative_name or any(not part.isidentifier() for part in parts):
            return None

        try:
            package_init = contained_path(scope.search_root, *parts, "__init__.py")
            module_file = contained_path(scope.search_root, *parts[:-1], parts[-1] + ".py")
            namespace_dir = contained_path(scope.search_root, *parts)
        except ManifestError as exc:
            raise ImportError(f"dynamic app module escapes its package root: {fullname}") from exc

        source: Path | None = None
        is_package = False
        if package_init.is_file():
            source = package_init
            is_package = True
        elif module_file.is_file():
            source = module_file
        elif namespace_dir.is_dir():
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [str(namespace_dir)]
            return spec
        else:
            return None

        loader = _DynamicAppLoader(
            fullname,
            str(source),
            unique_root,
            scope.canonical_root,
        )
        return importlib.util.spec_from_file_location(
            fullname,
            source,
            loader=loader,
            submodule_search_locations=[str(source.parent)] if is_package else None,
        )


_DYNAMIC_APP_FINDER = _DynamicAppFinder()


def _register_dynamic_scope(
    unique_root: str,
    search_root: Path,
    canonical_root: str,
) -> None:
    with _DYNAMIC_IMPORT_LOCK:
        if _DYNAMIC_APP_FINDER not in sys.meta_path:
            sys.meta_path.insert(0, _DYNAMIC_APP_FINDER)
        _DYNAMIC_IMPORT_SCOPES[unique_root] = _DynamicImportScope(
            search_root.resolve(),
            canonical_root,
        )


def _remove_dynamic_namespace(unique_root: str) -> None:
    """Drop one app's private import namespace and every child module."""

    with _DYNAMIC_IMPORT_LOCK:
        _DYNAMIC_IMPORT_SCOPES.pop(unique_root, None)
        if not _DYNAMIC_IMPORT_SCOPES:
            while _DYNAMIC_APP_FINDER in sys.meta_path:
                sys.meta_path.remove(_DYNAMIC_APP_FINDER)
    prefix = unique_root + "."
    for name in tuple(sys.modules):
        if name == unique_root or name.startswith(prefix):
            sys.modules.pop(name, None)


def _import_unique(module_name: str, search_root: Path, app_id: str) -> tuple[Any, str]:
    _ensure_namespace("badge_dynamic")
    safe_id = app_id.replace("-", "_")
    unique_root = f"badge_dynamic.{safe_id}_{uuid.uuid4().hex}"
    canonical_root = module_name.split(".", 1)[0]
    _ensure_namespace(unique_root)
    _register_dynamic_scope(unique_root, search_root, canonical_root)
    try:
        module = importlib.import_module(f"{unique_root}.{module_name}")
    except BaseException:
        _remove_dynamic_namespace(unique_root)
        raise
    return module, unique_root


def load_app_entrypoint(
    manifest: AppManifest, app_root: str | os.PathLike[str] | None = None
) -> object:
    """Import and instantiate one app under a collision-free module namespace."""

    if manifest.legacy:
        raise ManifestError(
            f"{manifest.app_id} uses the legacy MicroPython/LVGL v1 contract; "
            "port it to a v2 badge_sdk entry point before running it under CPython"
        )
    root_value = app_root or manifest.app_root
    if root_value is None:
        raise ManifestError("an application root is required to load an entry point")
    root = Path(root_value).expanduser().resolve()

    module_name, object_name = manifest.entry_point.split(":", 1)
    search_root = _module_root(root, module_name)
    module, unique_root = _import_unique(module_name, search_root, manifest.app_id)
    try:
        target: Any = module
        for component in object_name.split("."):
            if not hasattr(target, component):
                raise ManifestError(f"entry-point object {object_name!r} was not found")
            target = getattr(target, component)
        instance = target() if callable(target) else target
        from badge_sdk import App

        if not isinstance(instance, App):
            raise ManifestError("v2 entry point must create a badge_sdk.App instance")
    except BaseException:
        _remove_dynamic_namespace(unique_root)
        raise
    # Keep relative/lazy imports working for the lifetime of the instance, but
    # do not retain application modules forever after the runtime releases it.
    weakref.finalize(instance, _remove_dynamic_namespace, unique_root)
    # The signed/validated manifest, rather than executable code, is the source
    # of catalog metadata.
    instance.app_id = manifest.app_id
    instance.name = manifest.name
    instance.category = manifest.category
    instance.description = manifest.description
    return instance


__all__ = [
    "APP_ID_RE",
    "AppManifest",
    "ManifestError",
    "adapt_v1_metadata",
    "contained_path",
    "discover_manifests",
    "load_app_entrypoint",
    "load_manifest",
    "parse_pyproject",
    "parse_v2_json",
    "validate_app_id",
]
