"""Root-confined file browser with text preview and confirmed safe deletion."""

from __future__ import annotations

import os
from pathlib import Path

from badge_sdk import Action, App, Column, InputEvent, Menu, MenuItem, Screen, Text


class FileManagerApp(App):
    app_id = "file-manager"
    name = "File Manager"
    category = "tools"
    description = "Browse files and preview text without escaping the configured root"

    TEXT_SUFFIXES = {".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".log", ".py", ".conf"}

    def __init__(self, root: str | Path | None = None) -> None:
        super().__init__()
        self.configured_root = Path(root) if root else None
        self.root = Path.cwd()
        self.current = self.root
        self.entries: list[Path] = []
        self.selected = 0
        self.preview: tuple[str, str] | None = None
        self.confirm_delete: Path | None = None
        self.status = ""

    def on_start(self) -> None:
        configured = os.environ.get("BADGE_FILES_ROOT")
        requested = self.configured_root or (Path(configured) if configured else self.context.data_dir / "files")
        self.root = requested.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.current = self.root
        self._load()

    def _inside_root(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.root)
            return True
        except (OSError, ValueError):
            return False

    def _load(self) -> None:
        try:
            self.entries = sorted(self.current.iterdir(), key=lambda path: (not path.is_dir(), path.name.lower()))
            self.selected = min(self.selected, max(0, len(self.entries) - 1))
            self.status = ""
        except OSError as exc:
            self.entries = []
            self.status = str(exc)

    def _selected_path(self) -> Path | None:
        return self.entries[self.selected] if self.entries and 0 <= self.selected < len(self.entries) else None

    def _open(self, path: Path) -> None:
        if not self._inside_root(path):
            self.status = "Blocked path outside file root"
        elif path.is_dir():
            self.current = path.resolve()
            self.selected = 0
            self._load()
        elif path.suffix.lower() in self.TEXT_SUFFIXES:
            try:
                text = path.read_text(errors="replace")[:12000]
                self.preview = (path.name, text)
            except OSError as exc:
                self.status = str(exc)
        else:
            self.status = "Preview supports text files only"
        self.invalidate()

    def _delete(self, path: Path) -> None:
        try:
            if not self._inside_root(path) or path == self.root:
                raise OSError("Refusing to delete outside the file root")
            if path.is_dir():
                path.rmdir()  # Empty directories only; never recursive.
            else:
                path.unlink()
            self.status = f"Deleted {path.name}"
        except OSError as exc:
            self.status = str(exc)
        self.confirm_delete = None
        self._load()
        self.invalidate()

    def handle(self, event: InputEvent) -> bool:
        if event.action == Action.BACK:
            if self.preview:
                self.preview = None
            elif self.confirm_delete:
                self.confirm_delete = None
            elif self.current != self.root:
                parent = self.current.parent.resolve()
                self.current = parent if self._inside_root(parent) else self.root
                self.selected = 0
                self._load()
            else:
                return False
            self.invalidate()
            return True
        if event.action == Action.RIGHT and not self.preview and not self.confirm_delete:
            path = self._selected_path()
            if path:
                self.confirm_delete = path
                self.invalidate()
            return True
        return False

    def view(self) -> Screen:
        if self.preview:
            name, text = self.preview
            visible = "\n".join(text.splitlines()[:22])
            return Screen(Column(Text(visible, size=10, flex=1, wrap=True), padding=5), title=name, footer="BACK: files")
        if self.confirm_delete:
            path = self.confirm_delete
            menu = Menu(
                [
                    MenuItem("Cancel", lambda: setattr(self, "confirm_delete", None)),
                    MenuItem("Delete", lambda path=path: self._delete(path)),
                ],
                selected=0,
            )
            return Screen(Column(Text(f"Delete {path.name}?", align="center", bold=True), menu, padding=12), title=self.name, footer="Deletion preserves app data elsewhere")
        items = [
            MenuItem(("[DIR] " if path.is_dir() else "") + path.name, lambda path=path: self._open(path), detail=self._detail(path))
            for path in self.entries
        ]
        relative = "/" if self.current == self.root else "/" + str(self.current.relative_to(self.root))
        return Screen(
            Column(Text(relative, size=11), Menu(items, selected=self.selected, on_change=lambda value: setattr(self, "selected", value), rows=6), padding=6),
            title=self.name,
            footer="ENTER: open  RIGHT: delete  BACK: up",
            status=self.status,
        )

    @staticmethod
    def _detail(path: Path) -> str:
        try:
            if path.is_dir():
                return "dir"
            size = path.stat().st_size
            if size < 1024:
                return f"{size} B"
            if size < 1024 * 1024:
                return f"{size / 1024:.1f} KiB"
            return f"{size / (1024 * 1024):.1f} MiB"
        except OSError:
            return "?"
