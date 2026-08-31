"""Portable Badge SDK user interface for the community app store."""

from __future__ import annotations

from concurrent.futures import Future
from typing import Any

from badge_platform.app_store import (
    AppStore,
    CatalogApp,
    DependencyResolutionRequired,
    InstalledApp,
    LegacyPortRequired,
    StoreError,
)
from badge_sdk import (
    Action,
    App,
    Button,
    Column,
    InputEvent,
    Menu,
    MenuItem,
    QRCode,
    Row,
    Screen,
    Text,
)


class AppStoreApp(App):
    app_id = "app-store"
    name = "App Store"
    category = "tools"
    description = "Browse and manage community applications"

    CATEGORIES = (
        (None, "All Apps"),
        ("demo", "Demos"),
        ("tools", "Tools"),
        ("media", "Media"),
        ("games", "Games"),
    )
    SORTS = ("name", "stars", "recent")
    SORT_LABELS = {"name": "A-Z", "stars": "Stars", "recent": "Recent"}

    def __init__(self, store: AppStore | None = None) -> None:
        super().__init__()
        self.store = store or AppStore()
        self.page = "loading"
        self.category: str | None = None
        self.category_index = 0
        self.sort_index = 0
        self.selected_index = 0
        self.selected_id = ""
        self.message = "Fetching app list..."
        self.busy = False

    def on_start(self) -> None:
        self._refresh_catalog()

    def _refresh_catalog(self) -> None:
        self.page = "loading"
        self.message = "Fetching app list..."
        self.busy = True
        self.invalidate()
        if self.context:
            self.context.run_background(self.store.refresh, done=self._catalog_loaded)
        else:  # Useful for small host-side tests and direct construction.
            try:
                self.store.refresh()
                self.page = "categories"
                self.message = ""
            except Exception as exc:
                self.page = "status"
                self.message = f"Could not load app store: {exc}"
            finally:
                self.busy = False

    def _catalog_loaded(self, future: Future[Any]) -> None:
        try:
            future.result()
            self.page = "categories"
            self.message = ""
        except Exception as exc:
            self.page = "status"
            self.message = f"Could not load app store: {exc}"
        self.busy = False
        self.invalidate()

    def _apps(self) -> list[CatalogApp]:
        return self.store.browse(
            category=self.category,
            sort=self.SORTS[self.sort_index],
        )

    def _selected(self) -> CatalogApp | None:
        apps = self._apps()
        if not apps:
            return None
        self.selected_index = max(0, min(self.selected_index, len(apps) - 1))
        return apps[self.selected_index]

    def _choose_category(self, index: int, category: str | None) -> None:
        self.category_index = index
        self.category = category
        self.selected_index = 0
        self.page = "apps"
        self.invalidate()

    def _category_view(self) -> Screen:
        items = [
            MenuItem(
                label,
                lambda index=index, category=category: self._choose_category(index, category),
                key=f"category-{category or 'all'}",
            )
            for index, (category, label) in enumerate(self.CATEGORIES)
        ]
        return Screen(
            Column(
                Text("Choose a category", size=16, bold=True, align="center"),
                Menu(items, selected=self.category_index, rows=5),
                Button("Refresh Store", self._refresh_catalog, key="refresh-store"),
                gap=6,
                padding=8,
            ),
            title=self.name,
            footer="UP/DN: Category  RIGHT: Refresh  BACK: Exit",
        )

    def _select_app(self, index: int) -> None:
        self.selected_index = index
        selected = self._selected()
        self.selected_id = selected.id if selected else ""
        self.invalidate()

    def _open_actions(self, app_id: str) -> None:
        self.selected_id = app_id
        self.page = "actions"
        self.invalidate()

    def _app_list_view(self) -> Screen:
        apps = self._apps()
        if apps:
            self.selected_index = max(0, min(self.selected_index, len(apps) - 1))
        else:
            self.selected_index = 0
        items = [
            MenuItem(
                (
                    "[PORT] "
                    if item.manifest.legacy
                    else ("[*] " if self.store.is_installed(item.id) else "")
                )
                + item.name,
                lambda app_id=item.id: self._open_actions(app_id),
                detail=f"v{item.version}",
                key=f"app-{item.id}",
            )
            for item in apps
        ]
        selected = apps[self.selected_index] if apps else None
        if selected:
            installed = self.store.installed_manifest(selected.id)
            status = "Not installed"
            if selected.manifest.legacy:
                status = "Legacy MicroPython/LVGL - port required"
            elif installed:
                status = f"Installed v{installed.version}"
                if installed.version != selected.version:
                    status += f"; update to v{selected.version}"
            dependency_text = (
                "Dependencies: " + ", ".join(selected.dependencies)
                if selected.dependencies
                else "Dependencies: none"
            )
            detail = Column(
                Text(selected.name, size=18, bold=True),
                Text(f"v{selected.version} - {selected.category}"),
                Text(f"by {selected.author}" if selected.author else ""),
                Text(selected.description or "No description available", flex=1),
                Text(dependency_text, size=11),
                Text(status, size=12, bold=True),
                gap=4,
                padding=5,
                flex=1,
            )
        else:
            detail = Column(Text("No apps in this category", align="center"), padding=8, flex=1)
        menu = Menu(
            items,
            selected=self.selected_index,
            on_change=self._select_app,
            rows=5,
            width=180,
            empty_text="No apps",
        )
        return Screen(
            Row(menu, detail, gap=7, padding=5),
            title=f"App Store - {self.SORT_LABELS[self.SORTS[self.sort_index]]}",
            footer="UP/DN: Select  L/R: Sort  SELECT: Menu  BACK: Categories",
        )

    def _catalog_app(self) -> CatalogApp | None:
        return self.store.find(self.selected_id) if self.selected_id else None

    def _action_view(self) -> Screen:
        app = self._catalog_app()
        if app is None:
            return self._status_view("App is no longer in the catalog")
        installed = self.store.is_installed(app.id)
        items: list[MenuItem] = []
        if app.manifest.legacy:
            items.append(
                MenuItem(
                    "Port Required",
                    lambda: None,
                    detail="Legacy MicroPython/LVGL",
                    enabled=False,
                    key="legacy-port-required",
                )
            )
        elif installed:
            items.extend(
                [
                    MenuItem("Launch", self._launch_selected, key="launch"),
                    MenuItem("Update", self._install_selected, key="update"),
                ]
            )
            if self.store.rollback_available(app.id):
                items.append(MenuItem("Roll Back", self._rollback_selected, key="rollback"))
            items.append(MenuItem("Delete", self._confirm_delete, key="delete"))
        else:
            items.append(MenuItem("Install", self._install_selected, key="install"))
        items.extend(
            [
                MenuItem("Project Page", self._project_selected, enabled=bool(app.project_url), key="project"),
                MenuItem("Cancel", self._back_to_apps, key="cancel"),
            ]
        )
        dependency = ""
        if app.dependencies:
            dependency = "Requires: " + ", ".join(app.dependencies)
        return Screen(
            Column(
                Text(app.name, size=18, bold=True, align="center"),
                Text(dependency, size=11, align="center"),
                Menu(items, rows=5),
                padding=8,
                gap=5,
            ),
            title="App Options",
            footer="SELECT: Choose   BACK: Cancel",
        )

    def _back_to_apps(self) -> None:
        self.page = "apps"
        self.invalidate()

    def _install_selected(self) -> None:
        app = self._catalog_app()
        if app is None or self.busy:
            return
        updating = self.store.is_installed(app.id)
        self.busy = True
        self.page = "status"
        self.message = f"{'Updating' if updating else 'Installing'} {app.name}..."
        self.invalidate()
        if self.context:
            self.context.run_background(self.store.install, app, done=self._install_done)
        else:
            try:
                result = self.store.install(app)
                self._finish_install(result)
            except Exception as exc:
                self._operation_failed(exc)

    def _finish_install(self, result: InstalledApp) -> None:
        self.busy = False
        self.page = "status"
        verb = "updated" if result.updated else "installed"
        self.message = f"{result.manifest.name} {verb} successfully."
        self.invalidate()

    def _install_done(self, future: Future[Any]) -> None:
        try:
            self._finish_install(future.result())
        except Exception as exc:
            self._operation_failed(exc)

    def _operation_failed(self, exc: Exception) -> None:
        self.busy = False
        self.page = "status"
        if isinstance(exc, DependencyResolutionRequired):
            self.message = "Dependency setup required:\n" + "\n".join(exc.dependencies)
        elif isinstance(exc, LegacyPortRequired):
            self.message = (
                "Legacy app: port required.\n"
                "This MicroPython/LVGL app cannot run in the CPython launcher yet."
            )
        else:
            self.message = f"Operation failed: {exc}"
        self.invalidate()

    def _confirm_delete(self) -> None:
        self.page = "confirm-delete"
        self.invalidate()

    def _confirm_delete_view(self) -> Screen:
        app = self._catalog_app()
        name = app.name if app else self.selected_id
        return Screen(
            Column(
                Text(f"Delete {name}?", size=18, bold=True, align="center"),
                Text("Application data is preserved.", align="center"),
                Button("Cancel", lambda: self._set_page("actions"), key="cancel-delete"),
                Button("Delete", self._delete_selected, key="confirm-delete"),
                padding=12,
                gap=8,
            ),
            title="Confirm Delete",
            footer="Cancel is selected first  |  BACK: Cancel",
        )

    def _delete_selected(self) -> None:
        app = self._catalog_app()
        if app is None or self.busy:
            return
        self.busy = True
        self.page = "status"
        self.message = f"Deleting {app.name}..."
        self.invalidate()
        if self.context:
            self.context.run_background(self.store.uninstall, app.id, done=self._delete_done)
        else:
            try:
                self.store.uninstall(app.id)
                self._delete_success()
            except Exception as exc:
                self._operation_failed(exc)

    def _delete_success(self) -> None:
        app = self._catalog_app()
        self.busy = False
        self.page = "status"
        self.message = f"{app.name if app else self.selected_id} deleted. App data was preserved."
        self.invalidate()

    def _delete_done(self, future: Future[Any]) -> None:
        try:
            future.result()
            self._delete_success()
        except Exception as exc:
            self._operation_failed(exc)

    def _rollback_selected(self) -> None:
        app = self._catalog_app()
        if app is None or self.busy:
            return
        self.busy = True
        self.page = "status"
        self.message = f"Rolling back {app.name}..."
        self.invalidate()
        if self.context:
            self.context.run_background(self.store.rollback, app.id, done=self._rollback_done)
        else:
            try:
                self._finish_rollback(self.store.rollback(app.id))
            except Exception as exc:
                self._operation_failed(exc)

    def _finish_rollback(self, result: InstalledApp) -> None:
        self.busy = False
        self.page = "status"
        self.message = f"{result.manifest.name} rolled back to v{result.manifest.version}."
        self.invalidate()

    def _rollback_done(self, future: Future[Any]) -> None:
        try:
            self._finish_rollback(future.result())
        except Exception as exc:
            self._operation_failed(exc)

    def _launch_selected(self) -> None:
        app = self._catalog_app()
        if app is None:
            return
        try:
            launched = self.store.launch(app.id)
            if not isinstance(launched, App):
                raise StoreError("application did not return a badge_sdk.App")
            if not self.context:
                raise StoreError("application runtime is unavailable")
            self.context.open(launched)
        except Exception as exc:
            self._operation_failed(exc)

    def _project_selected(self) -> None:
        self.page = "project"
        self.invalidate()

    def _project_view(self) -> Screen:
        app = self._catalog_app()
        url = app.project_url if app else ""
        body = (
            Column(
                Text(app.name if app else "Project", size=18, bold=True, align="center"),
                QRCode(url, size=150),
                Text(url, size=10, align="center", wrap=True),
                align="center",
                padding=8,
                gap=5,
            )
            if url
            else Column(Text("No project URL is available", align="center"), padding=10)
        )
        return Screen(body, title="Project Page", footer="BACK: App Options")

    def _status_view(self, message: str | None = None) -> Screen:
        return Screen(
            Column(
                Text(message if message is not None else self.message, size=16, align="center", flex=1),
                Button("Back", self._status_back, enabled=not self.busy, key="status-back"),
                align="center",
                padding=12,
                gap=8,
            ),
            title=self.name,
            footer="Please wait" if self.busy else "BACK: Return",
        )

    def _status_back(self) -> None:
        if not self.busy:
            self.page = "apps" if self.category is not None or self.store.catalog else "categories"
            self.invalidate()

    def _set_page(self, page: str) -> None:
        self.page = page
        self.invalidate()

    def handle(self, event: InputEvent) -> bool:
        if event.action == Action.BACK:
            if self.busy:
                return True
            if self.page == "apps":
                self.page = "categories"
            elif self.page in {"actions", "project", "confirm-delete"}:
                self.page = "apps" if self.page == "actions" else "actions"
            elif self.page == "status":
                self._status_back()
                return True
            else:
                return False
            self.invalidate()
            return True
        if self.page == "apps" and event.action in {Action.LEFT, Action.RIGHT}:
            delta = -1 if event.action == Action.LEFT else 1
            self.sort_index = (self.sort_index + delta) % len(self.SORTS)
            self.selected_index = 0
            self.invalidate()
            return True
        return False

    def view(self) -> Screen:
        if self.page == "categories":
            return self._category_view()
        if self.page == "apps":
            return self._app_list_view()
        if self.page == "actions":
            return self._action_view()
        if self.page == "project":
            return self._project_view()
        if self.page == "confirm-delete":
            return self._confirm_delete_view()
        return self._status_view()


__all__ = ["AppStoreApp"]
