"""Portable CPython launcher shell for BeagleBadge.

The shell deliberately consumes only :mod:`badge_sdk` components.  Discovery
and installation live outside this module; callers provide a catalog or a
catalog callback, which also makes the launcher straightforward to exercise in
the desktop simulator and unit tests.
"""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeAlias

from badge_sdk import (
    Action,
    App,
    Box,
    Column,
    InputEvent,
    Menu,
    MenuItem,
    RefreshMode,
    Row,
    Rule,
    Screen,
    Spacer,
    Text,
)


AppFactory = Callable[[], App]


@dataclass(frozen=True, slots=True)
class LauncherEntry:
    """Metadata and a factory for one launchable application."""

    app_id: str
    name: str
    category: str
    factory: AppFactory
    description: str = ""

    @classmethod
    def from_app(cls, app: App) -> "LauncherEntry":
        return cls(
            app_id=app.app_id,
            name=app.name,
            category=app.category,
            factory=lambda app=app: app,
            description=app.description,
        )

    @classmethod
    def from_type(cls, app_type: type[App]) -> "LauncherEntry":
        if not issubclass(app_type, App):
            raise TypeError("launcher entries must be Badge SDK applications")
        return cls(
            app_id=app_type.app_id,
            name=app_type.name,
            category=app_type.category,
            factory=app_type,
            description=app_type.description,
        )


CatalogItem: TypeAlias = LauncherEntry | App | type[App]
CatalogSource: TypeAlias = Iterable[CatalogItem] | Callable[[], Iterable[CatalogItem]]


def _entry(value: LauncherEntry | App | type[App]) -> LauncherEntry:
    if isinstance(value, LauncherEntry):
        return value
    if isinstance(value, App):
        return LauncherEntry.from_app(value)
    if isinstance(value, type) and issubclass(value, App):
        return LauncherEntry.from_type(value)
    raise TypeError(f"unsupported launcher entry: {value!r}")


def _version() -> str:
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip() or "experimental"
    except OSError:
        return "experimental"


def _category_key(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ") or "apps"


def _category_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split())


class LauncherApp(App):
    """Two-panel launcher with e-ink-conscious asynchronous telemetry."""

    app_id = "system.launcher"
    name = "Launcher"
    category = "system"
    description = "BeagleBadge application launcher"

    def __init__(
        self,
        apps: CatalogSource = (),
        *,
        badge_mode: LauncherEntry | App | type[App] | None = None,
        version: str | None = None,
        telemetry_interval: float = 10.0,
    ) -> None:
        super().__init__()
        self._catalog_source = apps
        self._explicit_badge_mode = _entry(badge_mode) if badge_mode is not None else None
        self.version = version or _version()
        self.telemetry_interval = max(2.0, float(telemetry_interval))

        self._badge_mode: LauncherEntry | None = self._explicit_badge_mode
        self._categories: dict[str, list[LauncherEntry]] = {}
        self._category_order: list[str] = []
        self._catalog_error = ""
        self._message = ""

        self._state = "root"
        self._category: str | None = None
        self._root_selected = 0
        self._app_selected = 0

        self._status = None
        self._telemetry_call = None
        self._telemetry_future: Future | None = None
        self._active = False
        self.refresh_catalog()

    @property
    def categories(self) -> tuple[str, ...]:
        """Visible category labels, primarily useful to shell integrations."""

        return tuple(_category_name(category) for category in self._category_order)

    def refresh_catalog(self) -> None:
        """Reload catalog metadata without importing device or renderer code."""

        self._catalog_error = ""
        try:
            values = self._catalog_source() if callable(self._catalog_source) else self._catalog_source
            entries = [_entry(value) for value in values]
        except Exception as error:
            entries = []
            self._catalog_error = f"Could not load apps: {error}"

        badge_mode = self._explicit_badge_mode
        categories: dict[str, list[LauncherEntry]] = {}
        for candidate in entries:
            if candidate.app_id == self.app_id:
                continue
            if badge_mode is None and (
                candidate.app_id.replace("_", "-").lower() in {"badge-mode", "apps.badge-mode"}
                or candidate.name.strip().lower() == "badge mode"
            ):
                badge_mode = candidate
                continue
            key = _category_key(candidate.category)
            if key in {"system", "hidden"}:
                continue
            categories.setdefault(key, []).append(candidate)

        for values in categories.values():
            values.sort(key=lambda item: item.name.casefold())

        settings = categories.pop("settings", None)
        ordered = sorted(categories, key=lambda item: (_category_name(item).casefold(), item))
        if settings:
            categories["settings"] = settings
            ordered.append("settings")

        self._badge_mode = badge_mode
        self._categories = categories
        self._category_order = ordered
        if self._category not in categories:
            self._state = "root"
            self._category = None
        self._root_selected = min(self._root_selected, max(0, len(self._root_targets()) - 1))
        self._app_selected = min(
            self._app_selected,
            max(0, len(self._categories.get(self._category or "", ())) - 1),
        )

    def on_start(self) -> None:
        self._active = True
        self.refresh_catalog()
        self._request_telemetry()
        if self.context:
            self._telemetry_call = self.context.call_every(
                self.telemetry_interval,
                self._request_telemetry,
            )

    def on_resume(self) -> None:
        self.refresh_catalog()
        self._request_telemetry()
        self.invalidate(RefreshMode.FULL)

    def on_stop(self) -> None:
        self._active = False
        if self._telemetry_call is not None:
            self._telemetry_call.cancel()
            self._telemetry_call = None
        if self._telemetry_future is not None:
            self._telemetry_future.cancel()
            self._telemetry_future = None

    def _request_telemetry(self) -> None:
        if not self.context or not self._active:
            return
        if self._telemetry_future is not None and not self._telemetry_future.done():
            return
        service = getattr(self.context.services, "system", None)
        status = getattr(service, "status", None)
        if not callable(status):
            return
        self._telemetry_future = self.context.run_background(status, done=self._telemetry_ready)

    def _telemetry_ready(self, future: Future) -> None:
        self._telemetry_future = None
        if not self._active:
            return
        try:
            self._status = future.result()
        except Exception as error:
            self._message = f"Status unavailable: {error}"
        self.invalidate(RefreshMode.PARTIAL)

    def _root_targets(self) -> list[tuple[str, str | LauncherEntry | None]]:
        targets: list[tuple[str, str | LauncherEntry | None]] = [
            ("badge", self._badge_mode),
        ]
        targets.extend(("category", category) for category in self._category_order)
        return targets

    def _root_items(self) -> list[MenuItem]:
        result = [
            MenuItem(
                "Badge Mode",
                self._open_badge_mode,
                detail="badge" if self._badge_mode else "unavailable",
                enabled=self._badge_mode is not None,
                key="badge-mode",
            )
        ]
        for category in self._category_order:
            count = len(self._categories[category])
            result.append(
                MenuItem(
                    _category_name(category),
                    lambda category=category: self._enter_category(category),
                    detail=str(count),
                    key=f"category-{category}",
                )
            )
        return result

    def _app_items(self) -> list[MenuItem]:
        apps = self._categories.get(self._category or "", ())
        return [
            MenuItem(
                item.name,
                lambda item=item: self._open(item),
                detail=">",
                key=item.app_id,
            )
            for item in apps
        ]

    def _enter_category(self, category: str) -> None:
        if category not in self._categories:
            return
        self._category = category
        self._state = "apps"
        self._app_selected = 0
        self._message = ""
        self.invalidate(RefreshMode.FULL)

    def _leave_category(self) -> None:
        self._state = "root"
        self._category = None
        self._message = ""
        self.invalidate(RefreshMode.FULL)

    def _open_badge_mode(self) -> None:
        if self._badge_mode is not None:
            self._open(self._badge_mode)

    def _open(self, entry: LauncherEntry) -> None:
        if not self.context:
            return
        try:
            app = entry.factory()
            if not isinstance(app, App):
                raise TypeError("factory did not return a Badge SDK App")
            self._message = ""
            self.context.open(app)
        except Exception as error:
            self._message = f"Could not open {entry.name}: {error}"
            self.invalidate(RefreshMode.FULL)

    @staticmethod
    def _move_enabled(items: Sequence[MenuItem], selected: int, delta: int) -> int:
        enabled = [index for index, item in enumerate(items) if item.enabled]
        if not enabled:
            return selected
        try:
            position = enabled.index(selected)
        except ValueError:
            position = -1 if delta > 0 else 0
        return enabled[(position + delta) % len(enabled)]

    def _move_selection(self, delta: int) -> None:
        if self._state == "root":
            items = self._root_items()
            self._root_selected = self._move_enabled(items, self._root_selected, delta)
        else:
            items = self._app_items()
            self._app_selected = self._move_enabled(items, self._app_selected, delta)
        self.invalidate(RefreshMode.PARTIAL)

    def _activate_selection(self) -> None:
        if self._state == "root":
            items = self._root_items()
            selected = self._root_selected
        else:
            items = self._app_items()
            selected = self._app_selected
        if items and 0 <= selected < len(items) and items[selected].enabled:
            items[selected].on_select()

    def handle(self, event: InputEvent) -> bool:
        # Keep category navigation stable across renderers.  In particular,
        # RIGHT follows the physical badge convention of opening an item.
        if event.action == Action.UP:
            self._move_selection(-1)
            return True
        if event.action == Action.DOWN:
            self._move_selection(1)
            return True
        if event.action in (Action.SELECT, Action.RIGHT):
            self._activate_selection()
            return True
        if event.action in (Action.LEFT, Action.BACK):
            if self._state == "apps":
                self._leave_category()
            return True
        return False

    def _selection_changed(self, selected: int) -> None:
        if self._state == "root":
            self._root_selected = selected
        else:
            self._app_selected = selected
        self.invalidate(RefreshMode.PARTIAL)

    def _telemetry_text(self) -> tuple[str, str]:
        if self._status is None:
            return "CPU --%\nRAM --%\nBAT --", "Network -- | BT -- | USB --"
        battery = getattr(self._status, "battery", None)
        percent = getattr(battery, "percent", None)
        battery_text = "--" if percent is None else f"{percent}%"
        battery_state = getattr(battery, "state", "")
        if battery_state and battery_state != "Unknown":
            battery_text += f" {battery_state}"
        status = (
            f"CPU {getattr(self._status, 'cpu_percent', 0)}%\n"
            f"RAM {getattr(self._status, 'memory_percent', 0)}%\n"
            f"BAT {battery_text}"
        )
        interface = getattr(self._status, "interface", "")
        address = getattr(self._status, "ip_address", "")
        network = " ".join(part for part in (interface, address) if part) or "Offline"
        bluetooth = "BT+" if getattr(self._status, "bluetooth_connected", False) else "BT-"
        usb = getattr(self._status, "usb_devices", 0)
        return status, f"{network} | {bluetooth} | USB {usb}"

    def _selected_description(self) -> str:
        if self._state == "root":
            targets = self._root_targets()
            if not targets:
                return ""
            kind, value = targets[min(self._root_selected, len(targets) - 1)]
            if kind == "badge":
                return self._badge_mode.description if self._badge_mode else "Badge Mode is unavailable"
            return f"{len(self._categories[str(value)])} applications"
        apps = self._categories.get(self._category or "", ())
        if not apps:
            return "No applications"
        return apps[min(self._app_selected, len(apps) - 1)].description

    def view(self) -> Screen:
        telemetry, footer = self._telemetry_text()
        category_name = _category_name(self._category) if self._category else "Applications"
        shown_version = self.version.replace("~", "\n", 1)
        if self._state == "root":
            items = self._root_items()
            selected = self._root_selected
        else:
            items = self._app_items()
            selected = self._app_selected

        left = Column(
            Text("Beagle\nBadge", size=24, align="center", bold=True, height=64),
            Rule(),
            Text(f"Launcher\nv{shown_version}", size=10, align="center", height=47),
            Spacer(3),
            Box(Text(telemetry, size=11, align="left"), padding=5, height=67),
            Spacer(3),
            Text(self._selected_description(), size=10, align="center", flex=1),
            width=145,
            padding=5,
            gap=3,
        )
        right = Column(
            Text(category_name, size=17, bold=True, align="center", height=25),
            Menu(
                items,
                selected=selected,
                on_change=self._selection_changed,
                rows=5,
                row_height=38,
                empty_text="No applications",
                key="launcher-menu",
            ),
            padding=5,
            gap=4,
            flex=1,
        )
        return Screen(
            Row(left, Rule(vertical=True, thickness=2), right, gap=2, padding=0),
            title="BeagleBadge",
            footer=footer,
            status=self._message or self._catalog_error,
        )
