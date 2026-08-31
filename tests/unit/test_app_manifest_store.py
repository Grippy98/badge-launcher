from __future__ import annotations

import gc
import json
from pathlib import Path
import shutil
import sys
import textwrap
import weakref

import pytest

from badge_platform.app_manifest import (
    ManifestError,
    adapt_v1_metadata,
    contained_path,
    discover_manifests,
    load_app_entrypoint,
    load_manifest,
    validate_app_id,
)
from badge_platform.app_store import (
    AppStore,
    CatalogApp,
    CatalogError,
    CompatibilityError,
    DependencyResolutionRequired,
    LegacyPortRequired,
    StoreError,
    UnsafeExecutionError,
)
from badge_platform.command import CommandResult
from badge_sdk import App, Button, Column, Menu, Row, Text
from builtin_apps.tools.app_store import AppStoreApp


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _v2_data(
    app_id: str = "hello",
    version: str = "1.0.0",
    *,
    dependencies: list[str] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "id": app_id,
        "name": app_id.replace("-", " ").title(),
        "version": version,
        "category": "tools",
        "entry_point": "hello_app:create_app",
        "description": "Portable test app",
        "author": "Badge Developer",
        "license": "MIT",
        "homepage": f"https://example.invalid/{app_id}",
        "repo": f"https://example.invalid/{app_id}.git",
        "dependencies": dependencies or [],
        "permissions": ["storage.app"],
        "requires_python": ">=3.11",
        "requires_sdk": ">=1,<2",
        "ui": "portable-v1",
        "execution": "in-process",
    }


def _write_v2_app(
    root: Path,
    *,
    app_id: str = "hello",
    version: str = "1.0.0",
    dependencies: list[str] | None = None,
    body: str | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "badge-app.json", _v2_data(app_id, version, dependencies=dependencies))
    (root / "hello_app.py").write_text(
        textwrap.dedent(
            body
            or """
            from badge_sdk import App, Screen, Text

            class HelloApp(App):
                def view(self):
                    return Screen(Text("hello"))

            def create_app():
                return HelloApp()
            """
        ),
        encoding="utf-8",
    )


def _catalog_store(tmp_path: Path, app_data: dict[str, object], source: Path) -> AppStore:
    cache = tmp_path / "cache"
    app_id = str(app_data["id"])
    _write_json(
        cache / "manifest.json",
        {"schema_version": 2, "apps": [app_data]},
    )
    target = cache / "apps" / app_id / "app"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    store = AppStore(cache_dir=cache, install_root=tmp_path / "installed")
    store.refresh(update=False)
    return store


def test_loads_v2_pyproject_contract(tmp_path: Path) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text(
        textwrap.dedent(
            """
            [project]
            name = "beaglebadge-weather"
            version = "1.2.3"
            description = "Weather on the badge"
            requires-python = ">=3.11"
            dependencies = ["httpx>=0.27,<1"]
            authors = [{name = "A Developer"}]
            license = {text = "MIT"}

            [project.urls]
            Homepage = "https://example.invalid/weather"
            Repository = "https://example.invalid/weather.git"

            [project.entry-points."beaglebadge.apps"]
            weather = "weather_app:create_app"

            [tool.beaglebadge]
            schema_version = 2
            id = "weather"
            display_name = "Weather"
            category = "tools"
            sdk = ">=1,<2"
            ui = "portable-v1"
            permissions = ["network.https", "storage.app"]
            """
        ),
        encoding="utf-8",
    )

    manifest = load_manifest(project)

    assert manifest.schema_version == 2
    assert manifest.app_id == "weather"
    assert manifest.entry_point == "weather_app:create_app"
    assert manifest.dependencies == ("httpx>=0.27,<1",)
    assert manifest.permissions == ("network.https", "storage.app")
    assert manifest.requires_python == ">=3.11"


def test_loads_v2_json_and_explicit_v1_adapter(tmp_path: Path) -> None:
    v2_path = tmp_path / "badge-app.json"
    _write_json(v2_path, _v2_data("weather"))
    v2 = load_manifest(v2_path)
    assert not v2.legacy
    assert v2.entry_point == "hello_app:create_app"

    v1_path = tmp_path / "legacy" / "metadata.json"
    _write_json(
        v1_path,
        {
            "id": "photos",
            "name": "Photos",
            "version": "1.0.0",
            "category": "media",
            "main_file": "photos_app.py",
            "repo": "https://example.invalid/photos.git",
            "dependencies": [],
            "requires_img2bin": True,
        },
    )
    v1 = load_manifest(v1_path)
    assert v1.legacy
    assert v1.ui == "legacy-lvgl"
    assert v1.legacy_main_file == "photos_app.py"
    assert v1.system_dependencies == ("img2bin",)


@pytest.mark.parametrize(
    "app_id",
    ["../escape", "two/slashes", "Upper", "-leading", "trailing-", "a" * 65, "", "a b"],
)
def test_strict_app_ids(app_id: str) -> None:
    with pytest.raises(ManifestError):
        validate_app_id(app_id)


def test_contained_paths_reject_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    assert contained_path(root, "safe") == root / "safe"
    with pytest.raises(ManifestError):
        contained_path(root, "..", "outside")
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ManifestError):
        contained_path(root, "link", "payload")


def test_discovery_reads_manifests_without_importing_and_launch_is_namespaced(tmp_path: Path) -> None:
    app_root = tmp_path / "apps" / "hello"
    marker = app_root / "imported"
    _write_v2_app(
        app_root,
        body=f"""
        from pathlib import Path
        from badge_sdk import App, Screen, Text
        Path({str(marker)!r}).write_text("imported")

        class HelloApp(App):
            def view(self):
                return Screen(Text("hello"))

        def create_app():
            return HelloApp()
        """,
    )

    manifests = discover_manifests(tmp_path / "apps")
    assert [manifest.app_id for manifest in manifests] == ["hello"]
    assert not marker.exists(), "discovery imported executable application code"

    first = load_app_entrypoint(manifests[0], app_root)
    second = load_app_entrypoint(manifests[0], app_root)
    assert isinstance(first, App)
    assert marker.exists()
    assert type(first).__module__ != type(second).__module__
    assert type(first).__module__.startswith("badge_dynamic.hello_")

    dynamic_roots = {
        ".".join(type(instance).__module__.split(".")[:2]) for instance in (first, second)
    }
    instance_refs = (weakref.ref(first), weakref.ref(second))
    del first, second
    gc.collect()
    assert all(reference() is None for reference in instance_refs)
    assert not any(
        name == root or name.startswith(root + ".")
        for root in dynamic_roots
        for name in sys.modules
    )


def test_namespaced_packages_support_absolute_and_relative_imports(tmp_path: Path) -> None:
    canonical = "portable_test_package"
    previous_canonical = {
        name: module
        for name, module in sys.modules.items()
        if name == canonical or name.startswith(canonical + ".")
    }

    def write_package(root: Path, value: str) -> object:
        package = root / canonical
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            "from .factory import create_app\n",
            encoding="utf-8",
        )
        (package / "factory.py").write_text(
            textwrap.dedent(
                f"""
                import {canonical}.helper

                from badge_sdk import App, Screen, Text
                from .relative_value import SUFFIX

                class PortableApp(App):
                    def __init__(self):
                        super().__init__()
                        self.value = {canonical}.helper.VALUE + SUFFIX

                    def lazy_value(self):
                        from {canonical}.lazy_value import VALUE
                        return VALUE

                    def view(self):
                        return Screen(Text(self.value))

                def create_app():
                    return PortableApp()
                """
            ),
            encoding="utf-8",
        )
        (package / "helper.py").write_text(f"VALUE = {value!r}\n", encoding="utf-8")
        (package / "relative_value.py").write_text("SUFFIX = '-relative'\n", encoding="utf-8")
        (package / "lazy_value.py").write_text(
            f"VALUE = {f'{value}-lazy'!r}\n",
            encoding="utf-8",
        )
        manifest_data = _v2_data(root.name)
        manifest_data["entry_point"] = f"{canonical}:create_app"
        _write_json(root / "badge-app.json", manifest_data)
        return load_app_entrypoint(load_manifest(root / "badge-app.json"), root)

    first = write_package(tmp_path / "first", "first")
    second = write_package(tmp_path / "second", "second")

    assert first.value == "first-relative"
    assert second.value == "second-relative"
    assert first.lazy_value() == "first-lazy"
    assert second.lazy_value() == "second-lazy"
    assert type(first).__module__ != type(second).__module__
    assert {
        name: module
        for name, module in sys.modules.items()
        if name == canonical or name.startswith(canonical + ".")
    } == previous_canonical

    dynamic_roots = {
        ".".join(type(instance).__module__.split(".")[:2]) for instance in (first, second)
    }
    references = (weakref.ref(first), weakref.ref(second))
    del first, second
    gc.collect()

    assert all(reference() is None for reference in references)
    assert not any(
        name == root or name.startswith(root + ".")
        for root in dynamic_roots
        for name in sys.modules
    )


def test_failed_absolute_package_import_cleans_private_modules(tmp_path: Path) -> None:
    app_root = tmp_path / "broken-package"
    package = app_root / "broken_test_package"
    package.mkdir(parents=True)
    (package / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from broken_test_package.helper import VALUE\nraise RuntimeError('package failed')\n",
        encoding="utf-8",
    )
    manifest_data = _v2_data("broken-package")
    manifest_data["entry_point"] = "broken_test_package:create_app"
    _write_json(app_root / "badge-app.json", manifest_data)
    manifest = load_manifest(app_root / "badge-app.json")
    before = {name for name in sys.modules if name.startswith("badge_dynamic.broken_package_")}

    with pytest.raises(RuntimeError, match="package failed"):
        load_app_entrypoint(manifest, app_root)

    after = {name for name in sys.modules if name.startswith("badge_dynamic.broken_package_")}
    assert after == before
    assert "broken_test_package" not in sys.modules
    assert "broken_test_package.helper" not in sys.modules


def test_duplicate_discovered_ids_are_rejected(tmp_path: Path) -> None:
    _write_v2_app(tmp_path / "one")
    _write_v2_app(tmp_path / "two")
    with pytest.raises(ManifestError, match="duplicate app id"):
        discover_manifests(tmp_path)


def test_failed_entrypoint_does_not_leak_dynamic_modules(tmp_path: Path) -> None:
    app_root = tmp_path / "broken"
    _write_v2_app(
        app_root,
        body="""
        from badge_sdk import App

        def create_app():
            raise RuntimeError("startup failed")
        """,
    )
    manifest = load_manifest(app_root / "badge-app.json")
    before = {name for name in sys.modules if name.startswith("badge_dynamic.hello_")}

    with pytest.raises(RuntimeError, match="startup failed"):
        load_app_entrypoint(manifest, app_root)

    after = {name for name in sys.modules if name.startswith("badge_dynamic.hello_")}
    assert after == before


def test_legacy_main_file_cannot_escape_package() -> None:
    with pytest.raises(ManifestError, match="main_file"):
        adapt_v1_metadata(
            {
                "id": "bad",
                "name": "Bad",
                "version": "1.0.0",
                "main_file": "../../outside.py",
            }
        )


def test_catalog_browsing_categories_and_sorting(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    apps = [
        {**_v2_data("zebra"), "stars": 2, "updated_at": "2026-01-01"},
        {
            **_v2_data("alpha"),
            "category": "games",
            "stars": 12,
            "updated_at": "2026-08-01",
        },
    ]
    _write_json(cache / "manifest.json", {"schema_version": 2, "apps": apps})
    store = AppStore(cache_dir=cache, install_root=tmp_path / "installed")
    store.refresh(update=False)

    assert [app.id for app in store.browse()] == ["alpha", "zebra"]
    assert [app.id for app in store.browse(sort="stars")] == ["alpha", "zebra"]
    assert [app.id for app in store.browse(category="games")] == ["alpha"]
    assert store.project_url("alpha") == "https://example.invalid/alpha"


@pytest.mark.parametrize(
    ("field", "required"),
    [
        ("requires_python", ">=99"),
        ("requires_sdk", ">=2,<3"),
        ("min_badge_version", "9999"),
        ("ui", "future-ui"),
        ("execution", "subprocess"),
        ("requires_sdk", "not-a-constraint"),
    ],
)
def test_install_enforces_declared_runtime_contracts(
    tmp_path: Path, field: str, required: str
) -> None:
    manifest_data = _v2_data()
    manifest_data[field] = required
    manifest_path = tmp_path / f"{field}.json"
    _write_json(manifest_path, manifest_data)
    manifest = load_manifest(manifest_path)
    store = AppStore(
        cache_dir=tmp_path / "cache",
        install_root=tmp_path / "installed",
        python_version="3.11.9",
        sdk_version="1.0",
        launcher_version="2026.8.30.dev1",
    )
    store._catalog = (CatalogApp(manifest, tmp_path / "unused"),)

    with pytest.raises(CompatibilityError, match=field):
        store.install("hello")


def test_common_version_ranges_and_bare_launcher_minimum_are_supported(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    data = _v2_data()
    data.update(
        {
            "requires_python": ">=3.11,<4",
            "requires_sdk": "~=1.0",
            "min_badge_version": "2026.8.1",
        }
    )
    _write_v2_app(source)
    store = _catalog_store(tmp_path, data, source)
    store.python_version = "3.12.4"
    store.sdk_version = "1.9"
    store.launcher_version = "2026.8.30.dev1"

    assert store.install("hello").id == "hello"


def test_dependencies_are_surfaced_and_never_silently_ignored(tmp_path: Path) -> None:
    source = tmp_path / "source"
    data = _v2_data("weather", dependencies=["httpx>=0.27,<1"])
    _write_v2_app(source, app_id="weather", dependencies=["httpx>=0.27,<1"])
    store = _catalog_store(tmp_path, data, source)

    assert store.catalog[0].dependencies == ("httpx>=0.27,<1",)
    with pytest.raises(DependencyResolutionRequired) as error:
        store.install("weather")
    assert error.value.dependencies == ("httpx>=0.27,<1",)
    assert not store.is_installed("weather")


def test_staged_install_update_and_rollback(tmp_path: Path) -> None:
    source_v1 = tmp_path / "source-v1"
    _write_v2_app(source_v1, version="1.0.0")
    store = _catalog_store(tmp_path, _v2_data(version="1.0.0"), source_v1)

    installed = store.install("hello")
    assert installed.manifest.version == "1.0.0"
    assert not installed.updated
    assert store.is_installed("hello")

    source_in_cache = store.cache_dir / "apps" / "hello" / "app"
    shutil.rmtree(source_in_cache)
    _write_v2_app(source_in_cache, version="2.0.0")
    _write_json(
        store.cache_dir / "manifest.json",
        {"schema_version": 2, "apps": [_v2_data(version="2.0.0")]},
    )
    store.refresh(update=False)
    updated = store.install("hello")
    assert updated.updated
    assert updated.previous_version == "1.0.0"
    assert store.installed_manifest("hello").version == "2.0.0"
    assert store.rollback_available("hello")

    store_app = AppStoreApp(store)
    store_app.selected_id = "hello"
    action_menu = store_app._action_view().body.children[2]
    assert isinstance(action_menu, Menu)
    assert "Roll Back" in [item.label for item in action_menu.items]

    store_app._rollback_selected()
    assert "rolled back to v1.0.0" in store_app.message
    rolled_back = store.installed_manifest("hello")
    assert rolled_back is not None
    assert rolled_back.version == "1.0.0"
    assert store.installed_manifest("hello").version == "1.0.0"


def test_third_party_launch_is_blocked_as_root_unless_explicitly_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    marker = tmp_path / "imported-as-root"
    _write_v2_app(
        source,
        body=f"""
        from pathlib import Path
        from badge_sdk import App, Screen, Text
        Path({str(marker)!r}).write_text("imported")

        class HelloApp(App):
            def view(self):
                return Screen(Text("hello"))

        def create_app():
            return HelloApp()
        """,
    )
    store = _catalog_store(tmp_path, _v2_data(), source)
    store.install("hello")
    monkeypatch.setattr("badge_platform.app_store.os.geteuid", lambda: 0, raising=False)
    monkeypatch.delenv("BADGE_ALLOW_ROOT_APPS", raising=False)

    with pytest.raises(UnsafeExecutionError, match="BADGE_ALLOW_ROOT_APPS=1"):
        store.launch("hello")
    assert not marker.exists(), "privileged launch imported untrusted code before refusing it"

    monkeypatch.setenv("BADGE_ALLOW_ROOT_APPS", "1")
    launched = store.launch("hello")
    assert isinstance(launched, App)
    assert marker.read_text(encoding="utf-8") == "imported"


def test_launch_rechecks_compatibility_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    marker = tmp_path / "launched"
    _write_v2_app(
        source,
        body=f"""
        from pathlib import Path
        from badge_sdk import App, Screen, Text
        Path({str(marker)!r}).write_text("yes")

        class HelloApp(App):
            def view(self):
                return Screen(Text("hello"))

        def create_app():
            return HelloApp()
        """,
    )
    store = _catalog_store(tmp_path, _v2_data(), source)
    store.install("hello")
    store.sdk_version = "2.0"
    monkeypatch.setattr("badge_platform.app_store.os.geteuid", lambda: 1000, raising=False)

    with pytest.raises(CompatibilityError, match="requires_sdk"):
        store.launch("hello")
    assert not marker.exists()


def test_failed_update_keeps_previous_install(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_v2_app(source, version="1.0.0")
    store = _catalog_store(tmp_path, _v2_data(version="1.0.0"), source)
    store.install("hello")

    cache_source = store.cache_dir / "apps" / "hello" / "app"
    shutil.rmtree(cache_source)
    cache_source.mkdir(parents=True)
    _write_json(cache_source / "badge-app.json", _v2_data(version="2.0.0"))
    _write_json(
        store.cache_dir / "manifest.json",
        {"schema_version": 2, "apps": [_v2_data(version="2.0.0")]},
    )
    store.refresh(update=False)

    with pytest.raises(StoreError, match="entry-point module"):
        store.install("hello")
    assert store.installed_manifest("hello").version == "1.0.0"


def test_uninstall_preserves_external_data_and_rejects_bad_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_v2_app(source)
    store = _catalog_store(tmp_path, _v2_data(), source)
    store.install("hello")
    data_file = tmp_path / "data" / "hello" / "save.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text("saved", encoding="utf-8")

    assert store.uninstall("hello")
    assert data_file.read_text(encoding="utf-8") == "saved"
    assert not store.is_installed("hello")
    with pytest.raises(ManifestError):
        store.uninstall("../../outside")


def test_v1_apps_are_visible_but_cannot_install_or_execute(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "legacy_app.py").write_text("raise AssertionError('must not import')\n", encoding="utf-8")
    manifest = adapt_v1_metadata(
        {
            "id": "legacy",
            "name": "Legacy",
            "version": "1.0.0",
            "category": "apps",
            "main_file": "legacy_app.py",
            "repo": "https://example.invalid/legacy.git",
            "dependencies": [],
        }
    )
    store = AppStore(cache_dir=tmp_path / "cache", install_root=tmp_path / "installed")
    store._catalog = (CatalogApp(manifest, source),)

    with pytest.raises(LegacyPortRequired, match="must be ported"):
        store.install("legacy")
    assert not store.is_installed("legacy")
    with pytest.raises(ManifestError, match="legacy MicroPython/LVGL"):
        load_app_entrypoint(manifest, source)
    assert not (source / "imported").exists()


class _CloneRunner:
    def __init__(self, fixture: Path) -> None:
        self.fixture = fixture
        self.calls: list[tuple[str, ...]] = []

    def run(self, args, *, timeout=20, cwd=None, env=None):
        clean = tuple(str(arg) for arg in args)
        self.calls.append(clean)
        if clean[1] == "clone":
            shutil.copytree(self.fixture, Path(clean[-1]))
        return CommandResult(clean, 0, "", "")


class _SubmoduleRunner:
    def __init__(self, fixture: Path, *, update_ok: bool) -> None:
        self.fixture = fixture
        self.update_ok = update_ok
        self.calls: list[tuple[str, ...]] = []

    def run(self, args, *, timeout=20, cwd=None, env=None):
        clean = tuple(str(arg) for arg in args)
        self.calls.append(clean)
        if "ls-files" in clean:
            return CommandResult(
                clean,
                0,
                "160000 " + "0" * 40 + " 0\tapps/hello/app\n",
                "",
            )
        if "submodule" in clean:
            if self.update_ok:
                return CommandResult(clean, 0, "", "")
            return CommandResult(clean, 1, "", "submodule transport unavailable")
        if len(clean) > 1 and clean[1] == "clone":
            shutil.copytree(self.fixture, Path(clean[-1]))
            return CommandResult(clean, 0, "", "")
        return CommandResult(clean, 0, "", "")


class _RefRunner(_CloneRunner):
    commit = "a" * 40

    def run(self, args, *, timeout=20, cwd=None, env=None):
        clean = tuple(str(arg) for arg in args)
        self.calls.append(clean)
        if len(clean) > 1 and clean[1] == "clone":
            shutil.copytree(self.fixture, Path(clean[-1]))
            return CommandResult(clean, 0, "", "")
        if "rev-parse" in clean:
            return CommandResult(clean, 0, self.commit + "\n", "")
        return CommandResult(clean, 0, "", "")


def test_git_transport_uses_an_argument_vector_not_shell_text(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    _write_json(fixture / "manifest.json", {"schema_version": 2, "apps": []})
    runner = _CloneRunner(fixture)
    cache = tmp_path / "cache"
    store = AppStore(
        "https://example.invalid/store.git;touch-pwned",
        cache_dir=cache,
        install_root=tmp_path / "installed",
        runner=runner,  # type: ignore[arg-type]
    )

    store.refresh()

    assert len(runner.calls) == 1
    args = runner.calls[0]
    assert args[:4] == ("git", "clone", "--depth", "1")
    assert args[4] == "--"
    assert args[5] == "https://example.invalid/store.git;touch-pwned"
    assert not (tmp_path / "pwned").exists()


def test_populated_submodule_is_updated_before_it_is_copied(tmp_path: Path) -> None:
    fixture = tmp_path / "repository"
    _write_v2_app(fixture)
    cache = tmp_path / "cache"
    (cache / ".git").mkdir(parents=True)
    _write_json(cache / "manifest.json", {"schema_version": 2, "apps": [_v2_data()]})
    source = cache / "apps" / "hello" / "app"
    _write_v2_app(source)
    runner = _SubmoduleRunner(fixture, update_ok=True)
    store = AppStore(
        cache_dir=cache,
        install_root=tmp_path / "installed",
        runner=runner,  # type: ignore[arg-type]
    )
    store.refresh(update=False)

    store.install("hello")

    submodule_calls = [call for call in runner.calls if "submodule" in call]
    assert len(submodule_calls) == 1
    assert submodule_calls[0][-2:] == ("--", "apps/hello/app")
    assert not any(len(call) > 1 and call[1] == "clone" for call in runner.calls)


def test_failed_submodule_transport_falls_back_to_app_repository(tmp_path: Path) -> None:
    fixture = tmp_path / "repository"
    _write_v2_app(fixture)
    (fixture / "origin.txt").write_text("repository", encoding="utf-8")
    cache = tmp_path / "cache"
    (cache / ".git").mkdir(parents=True)
    _write_json(cache / "manifest.json", {"schema_version": 2, "apps": [_v2_data()]})
    stale_source = cache / "apps" / "hello" / "app"
    _write_v2_app(stale_source)
    (stale_source / "origin.txt").write_text("stale-submodule", encoding="utf-8")
    runner = _SubmoduleRunner(fixture, update_ok=False)
    store = AppStore(
        cache_dir=cache,
        install_root=tmp_path / "installed",
        runner=runner,  # type: ignore[arg-type]
    )
    store.refresh(update=False)

    installed = store.install("hello")

    assert (installed.path / "origin.txt").read_text(encoding="utf-8") == "repository"
    assert any("submodule" in call for call in runner.calls)
    assert any(len(call) > 1 and call[1] == "clone" for call in runner.calls)


def test_catalog_source_symlink_escape_is_never_copied(tmp_path: Path) -> None:
    fixture = tmp_path / "repository"
    _write_v2_app(fixture)
    (fixture / "origin.txt").write_text("repository", encoding="utf-8")
    outside = tmp_path / "outside"
    _write_v2_app(outside)
    (outside / "origin.txt").write_text("escaped", encoding="utf-8")
    cache = tmp_path / "cache"
    _write_json(cache / "manifest.json", {"schema_version": 2, "apps": [_v2_data()]})
    runner = _CloneRunner(fixture)
    store = AppStore(
        cache_dir=cache,
        install_root=tmp_path / "installed",
        runner=runner,  # type: ignore[arg-type]
    )
    store.refresh(update=False)
    source = cache / "apps" / "hello" / "app"
    source.parent.mkdir(parents=True)
    try:
        source.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    installed = store.install("hello")

    assert (installed.path / "origin.txt").read_text(encoding="utf-8") == "repository"


def test_source_ref_is_fetched_then_resolved_to_hash_before_checkout(tmp_path: Path) -> None:
    fixture = tmp_path / "repository"
    _write_v2_app(fixture)
    cache = tmp_path / "cache"
    data = {**_v2_data(), "source_ref": "release/v1.0"}
    _write_json(cache / "manifest.json", {"schema_version": 2, "apps": [data]})
    runner = _RefRunner(fixture)
    store = AppStore(
        cache_dir=cache,
        install_root=tmp_path / "installed",
        runner=runner,  # type: ignore[arg-type]
    )
    store.refresh(update=False)

    store.install("hello")

    fetch = next(call for call in runner.calls if "fetch" in call)
    checkout = next(call for call in runner.calls if "checkout" in call)
    assert fetch[-1] == "release/v1.0"
    assert checkout[-2:] == (_RefRunner.commit, "--")
    assert "release/v1.0" not in checkout


@pytest.mark.parametrize(
    "source_ref",
    ["--upload-pack=evil", "../main", "main^{tree}", "refs//heads/main", "x.lock"],
)
def test_catalog_rejects_unsafe_git_source_refs(tmp_path: Path, source_ref: str) -> None:
    cache = tmp_path / "cache"
    _write_json(
        cache / "manifest.json",
        {"schema_version": 2, "apps": [{**_v2_data(), "source_ref": source_ref}]},
    )
    store = AppStore(cache_dir=cache, install_root=tmp_path / "installed")

    with pytest.raises(CatalogError, match="invalid source ref"):
        store.refresh(update=False)


def _texts(component) -> list[str]:
    values: list[str] = []
    if isinstance(component, Text):
        values.append(component.text)
    if isinstance(component, (Column, Row)):
        for child in component.children:
            values.extend(_texts(child))
    if isinstance(component, Menu):
        for item in component.items:
            values.append(item.label)
            values.append(item.detail)
    return values


def test_portable_store_ui_surfaces_dependencies_and_install_state(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ui-badge-app.json"
    _write_json(manifest_path, _v2_data("weather", dependencies=["httpx>=0.27,<1"]))
    manifest = load_manifest(manifest_path)
    store = AppStore(cache_dir=tmp_path / "cache", install_root=tmp_path / "installed")
    store._catalog = (CatalogApp(manifest),)
    ui = AppStoreApp(store)
    ui.page = "apps"

    text = "\n".join(_texts(ui.view().body))
    assert "Weather" in text
    assert "Dependencies: httpx>=0.27,<1" in text


def test_delete_confirmation_focuses_cancel_before_destructive_action(tmp_path: Path) -> None:
    manifest_path = tmp_path / "ui-badge-app.json"
    _write_json(manifest_path, _v2_data("weather"))
    store = AppStore(cache_dir=tmp_path / "cache", install_root=tmp_path / "installed")
    store._catalog = (CatalogApp(load_manifest(manifest_path)),)
    ui = AppStoreApp(store)
    ui.selected_id = "weather"

    buttons = [child for child in ui._confirm_delete_view().body.children if isinstance(child, Button)]
    assert [button.label for button in buttons] == ["Cancel", "Delete"]
