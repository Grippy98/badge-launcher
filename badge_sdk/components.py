"""Declarative, monochrome-first components for portable badge apps.

Applications construct these objects in ``App.view``.  They contain no Pillow,
SDL, framebuffer, or device-specific code, which keeps the public app API usable
on both the badge and a developer workstation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

Callback = Callable[[], Any]
ChangeCallback = Callable[[int], Any]
TextCallback = Callable[[str], Any]
KeyboardCallback = Callable[[str], Any]


@dataclass(slots=True, kw_only=True)
class Component:
    key: str | None = None
    width: int | None = None
    height: int | None = None
    flex: int = 0
    visible: bool = True

    @property
    def focusable(self) -> bool:
        return False


@dataclass(slots=True)
class Text(Component):
    text: str = ""
    size: int = 14
    align: str = "left"
    bold: bool = False
    invert: bool = False
    wrap: bool = True

    def __init__(
        self,
        text: object = "",
        *,
        size: int = 14,
        align: str = "left",
        bold: bool = False,
        invert: bool = False,
        wrap: bool = True,
        key: str | None = None,
        width: int | None = None,
        height: int | None = None,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.text = str(text)
        self.size = size
        self.align = align
        self.bold = bold
        self.invert = invert
        self.wrap = wrap


@dataclass(slots=True)
class Spacer(Component):
    size: int = 8

    def __init__(self, size: int = 8, *, flex: int = 0) -> None:
        Component.__init__(self, height=size, flex=flex)
        self.size = size


@dataclass(slots=True)
class Rule(Component):
    thickness: int = 1
    vertical: bool = False

    def __init__(self, thickness: int = 1, *, vertical: bool = False) -> None:
        Component.__init__(self, width=thickness if vertical else None, height=None if vertical else thickness)
        self.thickness = thickness
        self.vertical = vertical


@dataclass(slots=True)
class Column(Component):
    children: list[Component] = field(default_factory=list)
    gap: int = 4
    padding: int = 0
    align: str = "stretch"
    border: int = 0
    invert: bool = False

    def __init__(
        self,
        *children: Component,
        gap: int = 4,
        padding: int = 0,
        align: str = "stretch",
        border: int = 0,
        invert: bool = False,
        key: str | None = None,
        width: int | None = None,
        height: int | None = None,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.children = list(children)
        self.gap = gap
        self.padding = padding
        self.align = align
        self.border = border
        self.invert = invert


@dataclass(slots=True)
class Row(Component):
    children: list[Component] = field(default_factory=list)
    gap: int = 4
    padding: int = 0
    align: str = "stretch"
    border: int = 0
    invert: bool = False

    def __init__(
        self,
        *children: Component,
        gap: int = 4,
        padding: int = 0,
        align: str = "stretch",
        border: int = 0,
        invert: bool = False,
        key: str | None = None,
        width: int | None = None,
        height: int | None = None,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.children = list(children)
        self.gap = gap
        self.padding = padding
        self.align = align
        self.border = border
        self.invert = invert


@dataclass(slots=True)
class Box(Component):
    child: Component | None = None
    padding: int = 4
    border: int = 1
    invert: bool = False
    align: str = "center"

    def __init__(
        self,
        child: Component | None = None,
        *,
        padding: int = 4,
        border: int = 1,
        invert: bool = False,
        align: str = "center",
        key: str | None = None,
        width: int | None = None,
        height: int | None = None,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.child = child
        self.padding = padding
        self.border = border
        self.invert = invert
        self.align = align


@dataclass(slots=True)
class Button(Component):
    label: str = ""
    on_press: Callback | None = None
    enabled: bool = True
    hint: str = ""

    def __init__(
        self,
        label: object,
        on_press: Callback | None = None,
        *,
        enabled: bool = True,
        hint: str = "",
        key: str | None = None,
        width: int | None = None,
        height: int | None = 34,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.label = str(label)
        self.on_press = on_press
        self.enabled = enabled
        self.hint = hint

    @property
    def focusable(self) -> bool:
        return self.enabled and self.visible


@dataclass(slots=True)
class MenuItem:
    label: str
    on_select: Callback
    detail: str = ""
    enabled: bool = True
    key: str | None = None


@dataclass(slots=True)
class Menu(Component):
    items: list[MenuItem] = field(default_factory=list)
    selected: int = 0
    on_change: ChangeCallback | None = None
    rows: int = 5
    row_height: int = 34
    empty_text: str = "No items"

    def __init__(
        self,
        items: Sequence[MenuItem] | None = None,
        *,
        selected: int = 0,
        on_change: ChangeCallback | None = None,
        rows: int = 5,
        row_height: int = 34,
        empty_text: str = "No items",
        key: str | None = "menu",
        width: int | None = None,
        height: int | None = None,
        flex: int = 1,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.items = list(items or [])
        self.selected = selected
        self.on_change = on_change
        self.rows = rows
        self.row_height = row_height
        self.empty_text = empty_text

    @property
    def focusable(self) -> bool:
        return bool(self.items) and self.visible

    def move(self, delta: int) -> None:
        if not self.items:
            return
        enabled = [index for index, item in enumerate(self.items) if item.enabled]
        if not enabled:
            return
        try:
            position = enabled.index(max(0, min(self.selected, len(self.items) - 1)))
        except ValueError:
            position = 0
        self.selected = enabled[(position + delta) % len(enabled)]
        if self.on_change:
            self.on_change(self.selected)

    def activate(self) -> None:
        if self.items and 0 <= self.selected < len(self.items):
            item = self.items[self.selected]
            if item.enabled:
                item.on_select()


@dataclass(slots=True)
class Image(Component):
    source: str | Path | bytes | Any = b""
    fit: str = "contain"
    invert: bool = False
    source_size: tuple[int, int] | None = None
    source_mode: str = "L"

    def __init__(
        self,
        source: str | Path | bytes | Any,
        *,
        fit: str = "contain",
        invert: bool = False,
        source_size: tuple[int, int] | None = None,
        source_mode: str = "L",
        key: str | None = None,
        width: int | None = None,
        height: int | None = None,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.source = source
        self.fit = fit
        self.invert = invert
        self.source_size = source_size
        self.source_mode = source_mode


@dataclass(slots=True)
class QRCode(Component):
    data: str = ""

    def __init__(self, data: str, *, size: int = 120, key: str | None = None, visible: bool = True) -> None:
        Component.__init__(self, key=key, width=size, height=size, visible=visible)
        self.data = data


@dataclass(slots=True)
class Progress(Component):
    value: float = 0.0
    label: str = ""

    def __init__(
        self,
        value: float,
        *,
        label: str = "",
        key: str | None = None,
        width: int | None = None,
        height: int | None = 20,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.value = max(0.0, min(float(value), 1.0))
        self.label = label


@dataclass(slots=True)
class TextInput(Component):
    value: str = ""
    placeholder: str = ""
    password: bool = False
    on_change: TextCallback | None = None
    on_submit: Callback | None = None
    max_length: int = 128

    def __init__(
        self,
        value: str = "",
        *,
        placeholder: str = "",
        password: bool = False,
        on_change: TextCallback | None = None,
        on_submit: Callback | None = None,
        max_length: int = 128,
        key: str | None = "input",
        width: int | None = None,
        height: int | None = 38,
        flex: int = 0,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.value = value
        self.placeholder = placeholder
        self.password = password
        self.on_change = on_change
        self.on_submit = on_submit
        self.max_length = max_length

    @property
    def focusable(self) -> bool:
        return self.visible

    def replace(self, value: str) -> None:
        self.value = value[: self.max_length]
        if self.on_change:
            self.on_change(self.value)


@dataclass(slots=True)
class Keyboard(Component):
    """Small joystick-navigable on-screen keyboard.

    Apps own the selected row/column so rebuilding a view never loses state.
    Special key labels such as ``SPACE``, ``BACK``, and ``OK`` are passed to the
    callback unchanged, leaving their meaning under app control.
    """

    rows: list[list[str]] = field(default_factory=list)
    selected_row: int = 0
    selected_column: int = 0
    on_key: KeyboardCallback | None = None
    on_move: Callable[[int, int], Any] | None = None

    def __init__(
        self,
        rows: Sequence[Sequence[str]],
        on_key: KeyboardCallback,
        *,
        selected_row: int = 0,
        selected_column: int = 0,
        on_move: Callable[[int, int], Any] | None = None,
        key: str | None = "keyboard",
        width: int | None = None,
        height: int | None = None,
        flex: int = 1,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.rows = [list(row) for row in rows]
        self.selected_row = selected_row
        self.selected_column = selected_column
        self.on_key = on_key
        self.on_move = on_move
        self._normalize()

    @property
    def focusable(self) -> bool:
        return bool(self.rows) and self.visible

    def _normalize(self) -> None:
        if not self.rows:
            self.selected_row = self.selected_column = 0
            return
        self.selected_row %= len(self.rows)
        row = self.rows[self.selected_row]
        self.selected_column = self.selected_column % len(row) if row else 0

    def move(self, row_delta: int, column_delta: int) -> None:
        if not self.rows:
            return
        self.selected_row = (self.selected_row + row_delta) % len(self.rows)
        row = self.rows[self.selected_row]
        if row:
            self.selected_column = (self.selected_column + column_delta) % len(row)
        else:
            self.selected_column = 0
        if self.on_move:
            self.on_move(self.selected_row, self.selected_column)

    def activate(self) -> None:
        if not self.rows:
            return
        row = self.rows[self.selected_row]
        if row and self.on_key:
            self.on_key(row[self.selected_column])


@dataclass(slots=True)
class Canvas(Component):
    draw: Callable[[Any, tuple[int, int, int, int]], Any] | None = None

    def __init__(
        self,
        draw: Callable[[Any, tuple[int, int, int, int]], Any],
        *,
        key: str | None = None,
        width: int | None = None,
        height: int | None = None,
        flex: int = 1,
        visible: bool = True,
    ) -> None:
        Component.__init__(self, key=key, width=width, height=height, flex=flex, visible=visible)
        self.draw = draw


@dataclass(slots=True)
class Screen:
    body: Component
    title: str = ""
    footer: str = ""
    status: str = ""
    full_refresh: bool = False


def menu_items(values: Iterable[tuple[str, Callback]]) -> list[MenuItem]:
    """Convenience helper for the most common menu declaration."""

    return [MenuItem(label, callback) for label, callback in values]
