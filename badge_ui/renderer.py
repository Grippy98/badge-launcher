"""Pillow renderer for the public ``badge_sdk`` component tree."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math
from pathlib import Path
from typing import Iterable

from badge_sdk.components import (
    Box,
    Button,
    Canvas,
    Column,
    Component,
    Image as ImageComponent,
    Keyboard,
    Menu,
    Progress,
    QRCode,
    Row,
    Rule,
    Screen,
    Spacer,
    Text,
    TextInput,
)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover - exercised by installation checks
    raise RuntimeError("Badge Launcher requires Pillow (python3-pil or pip install Pillow)") from exc

Bounds = tuple[int, int, int, int]


def _font_candidates(bold: bool) -> list[str]:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    mac_name = "Arial Bold.ttf" if bold else "Arial.ttf"
    return [
        f"/usr/share/fonts/truetype/dejavu/{name}",
        f"/usr/share/fonts/dejavu/{name}",
        f"/System/Library/Fonts/Supplemental/{mac_name}",
        f"/Library/Fonts/{mac_name}",
    ]


@lru_cache(maxsize=64)
def get_font(size: int, bold: bool = False):
    for candidate in _font_candidates(bold):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, max(8, int(size)))
    return ImageFont.load_default()


def _inner(bounds: Bounds, padding: int) -> Bounds:
    x0, y0, x1, y1 = bounds
    return x0 + padding, y0 + padding, max(x0 + padding, x1 - padding), max(y0 + padding, y1 - padding)


def _size(bounds: Bounds) -> tuple[int, int]:
    return max(0, bounds[2] - bounds[0]), max(0, bounds[3] - bounds[1])


def _component_key(component: Component, path: str) -> str:
    return component.key or path


class Renderer:
    """Turn a component tree into a deterministic 8-bit grayscale frame."""

    def __init__(self) -> None:
        self.focusables: list[tuple[str, Component]] = []
        self.bounds_by_key: dict[str, Bounds] = {}

    def collect_focusables(self, screen: Screen) -> list[tuple[str, Component]]:
        collected: list[tuple[str, Component]] = []

        def visit(component: Component, path: str) -> None:
            if not component.visible:
                return
            key = _component_key(component, path)
            if component.focusable:
                collected.append((key, component))
            if isinstance(component, (Column, Row)):
                for index, child in enumerate(component.children):
                    visit(child, f"{path}/{index}")
            elif isinstance(component, Box) and component.child is not None:
                visit(component.child, f"{path}/0")

        visit(screen.body, "body")
        return collected

    def render(self, screen: Screen, width: int, height: int, focused_key: str | None = None):
        image = Image.new("L", (width, height), 255)
        draw = ImageDraw.Draw(image)
        self.focusables = self.collect_focusables(screen)
        self.bounds_by_key = {}

        top = 0
        if screen.title:
            draw.rectangle((0, 0, width - 1, 27), fill=255, outline=0, width=1)
            self._draw_text(draw, (6, 2, width - 6, 25), screen.title, 17, "center", True, False, True)
            top = 28

        bottom = height
        if screen.footer:
            bottom -= 21
            draw.rectangle((0, bottom, width - 1, height - 1), fill=255, outline=0, width=1)
            self._draw_text(draw, (4, bottom + 2, width - 4, height - 2), screen.footer, 10, "center", False, False, False)

        body_bounds = (0, top, width, bottom)
        self._render_component(image, draw, screen.body, body_bounds, "body", focused_key)

        if screen.status:
            status_width = min(width - 30, 340)
            status_height = min(92, height - 40)
            x0 = (width - status_width) // 2
            y0 = (height - status_height) // 2
            draw.rectangle((x0, y0, x0 + status_width, y0 + status_height), fill=255, outline=0, width=2)
            self._draw_text(
                draw,
                (x0 + 8, y0 + 8, x0 + status_width - 8, y0 + status_height - 8),
                screen.status,
                13,
                "center",
                False,
                False,
                True,
            )
        return image

    def _preferred_height(self, component: Component, available: int) -> int:
        if component.height is not None:
            return max(0, component.height)
        if isinstance(component, Text):
            return max(component.size + 6, 16)
        if isinstance(component, Button):
            return 34
        if isinstance(component, Menu):
            return min(available, component.rows * component.row_height)
        if isinstance(component, TextInput):
            return 38
        if isinstance(component, Progress):
            return 20
        if isinstance(component, Rule):
            return component.thickness
        if isinstance(component, Spacer):
            return component.size
        if isinstance(component, QRCode):
            return component.height or 120
        if isinstance(component, (Column, Row, Box, Canvas, ImageComponent)):
            return available
        return 20

    def _preferred_width(self, component: Component, available: int) -> int:
        if component.width is not None:
            return max(0, component.width)
        if isinstance(component, Rule) and component.vertical:
            return component.thickness
        if isinstance(component, QRCode):
            return component.width or 120
        return available

    def _render_component(
        self,
        image,
        draw,
        component: Component,
        bounds: Bounds,
        path: str,
        focused_key: str | None,
    ) -> None:
        if not component.visible:
            return
        key = _component_key(component, path)
        self.bounds_by_key[key] = bounds
        focused = key == focused_key
        x0, y0, x1, y1 = bounds
        if x1 <= x0 or y1 <= y0:
            return

        if isinstance(component, Text):
            self._draw_text(
                draw,
                bounds,
                component.text,
                component.size,
                component.align,
                component.bold,
                component.invert,
                component.wrap,
            )
        elif isinstance(component, Spacer):
            return
        elif isinstance(component, Rule):
            if component.vertical:
                x = (x0 + x1) // 2
                draw.line((x, y0, x, y1 - 1), fill=0, width=component.thickness)
            else:
                y = (y0 + y1) // 2
                draw.line((x0, y, x1 - 1, y), fill=0, width=component.thickness)
        elif isinstance(component, Column):
            self._render_container(image, draw, component, bounds, path, focused_key, vertical=True)
        elif isinstance(component, Row):
            self._render_container(image, draw, component, bounds, path, focused_key, vertical=False)
        elif isinstance(component, Box):
            fill = 0 if component.invert else 255
            outline = 255 if component.invert else 0
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=fill, outline=outline, width=max(0, component.border))
            if component.child:
                self._render_component(
                    image,
                    draw,
                    component.child,
                    _inner(bounds, component.padding + component.border),
                    f"{path}/0",
                    focused_key,
                )
        elif isinstance(component, Button):
            invert = focused and component.enabled
            fill, ink = (0, 255) if invert else (255, 0)
            if not component.enabled:
                ink = 128
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=fill, outline=ink, width=2 if focused else 1)
            self._draw_text(draw, _inner(bounds, 4), component.label, 14, "center", focused, invert, True)
        elif isinstance(component, Menu):
            self._render_menu(draw, component, bounds, focused)
        elif isinstance(component, Keyboard):
            self._render_keyboard(draw, component, bounds, focused)
        elif isinstance(component, ImageComponent):
            self._render_image(image, component, bounds)
        elif isinstance(component, QRCode):
            self._render_qr(image, draw, component, bounds)
        elif isinstance(component, Progress):
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255, outline=0, width=1)
            fill_width = int(max(0, x1 - x0 - 4) * component.value)
            if fill_width:
                draw.rectangle((x0 + 2, y0 + 2, x0 + 2 + fill_width, y1 - 3), fill=0)
            if component.label:
                self._draw_text(draw, bounds, component.label, 11, "center", False, component.value > 0.5, False)
        elif isinstance(component, TextInput):
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255, outline=0, width=2 if focused else 1)
            value = ("*" * len(component.value)) if component.password else component.value
            shown = value or component.placeholder
            if focused:
                shown += "_"
            self._draw_text(draw, _inner(bounds, 5), shown, 14, "left", False, False, False)
        elif isinstance(component, Canvas) and component.draw is not None:
            component.draw(draw, bounds)

    def _render_container(
        self,
        image,
        draw,
        component: Column | Row,
        bounds: Bounds,
        path: str,
        focused_key: str | None,
        *,
        vertical: bool,
    ) -> None:
        x0, y0, x1, y1 = bounds
        if component.invert or component.border:
            fill, ink = (0, 255) if component.invert else (255, 0)
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=fill, outline=ink, width=component.border)
        content = _inner(bounds, component.padding + component.border)
        children = [child for child in component.children if child.visible]
        if not children:
            return
        available_main = (content[3] - content[1]) if vertical else (content[2] - content[0])
        gaps = component.gap * max(0, len(children) - 1)
        fixed = 0
        flex_total = 0
        preferred: list[int] = []
        for child in children:
            if child.flex:
                flex_total += child.flex
                preferred.append(0)
            else:
                value = (
                    self._preferred_height(child, available_main)
                    if vertical
                    else self._preferred_width(child, available_main)
                )
                preferred.append(value)
                fixed += value
        remainder = max(0, available_main - fixed - gaps)
        cursor = content[1] if vertical else content[0]
        for index, (child, base) in enumerate(zip(children, preferred)):
            main_size = base
            if child.flex and flex_total:
                main_size = max(0, int(remainder * child.flex / flex_total))
            if vertical:
                child_width = min(content[2] - content[0], self._preferred_width(child, content[2] - content[0]))
                if component.align == "center":
                    child_x = content[0] + ((content[2] - content[0]) - child_width) // 2
                elif component.align == "end":
                    child_x = content[2] - child_width
                else:
                    child_x = content[0]
                child_bounds = (child_x, cursor, child_x + child_width, min(content[3], cursor + main_size))
            else:
                child_height = min(content[3] - content[1], self._preferred_height(child, content[3] - content[1]))
                if component.align == "center":
                    child_y = content[1] + ((content[3] - content[1]) - child_height) // 2
                elif component.align == "end":
                    child_y = content[3] - child_height
                else:
                    child_y = content[1]
                child_bounds = (cursor, child_y, min(content[2], cursor + main_size), child_y + child_height)
            self._render_component(image, draw, child, child_bounds, f"{path}/{index}", focused_key)
            cursor += main_size + component.gap

    def _render_menu(self, draw, menu: Menu, bounds: Bounds, focused: bool) -> None:
        x0, y0, x1, y1 = bounds
        if not menu.items:
            self._draw_text(draw, bounds, menu.empty_text, 14, "center", False, False, True)
            return
        selected = max(0, min(menu.selected, len(menu.items) - 1))
        rows = max(1, min(menu.rows, max(1, (y1 - y0) // menu.row_height)))
        start = max(0, min(selected - rows // 2, len(menu.items) - rows))
        for visible_index, item_index in enumerate(range(start, min(len(menu.items), start + rows))):
            item = menu.items[item_index]
            top = y0 + visible_index * menu.row_height
            bottom = min(y1, top + menu.row_height - 2)
            is_selected = item_index == selected
            invert = is_selected
            fill, ink = (0, 255) if invert else (255, 0)
            if not item.enabled:
                ink = 128
            draw.rectangle((x0, top, x1 - 1, bottom), fill=fill, outline=ink, width=2 if is_selected and focused else 1)
            detail_space = 0
            if item.detail:
                detail_space = min(120, (x1 - x0) // 3)
                self._draw_text(
                    draw,
                    (x1 - detail_space, top + 2, x1 - 4, bottom - 2),
                    item.detail,
                    10,
                    "right",
                    False,
                    invert,
                    False,
                )
            self._draw_text(
                draw,
                (x0 + 6, top + 2, x1 - detail_space - 4, bottom - 2),
                item.label,
                14,
                "left",
                is_selected,
                invert,
                False,
            )
        if start > 0:
            draw.polygon(((x1 - 12, y0 + 3), (x1 - 4, y0 + 3), (x1 - 8, y0 - 1)), fill=0)
        if start + rows < len(menu.items):
            draw.polygon(((x1 - 12, y1 - 4), (x1 - 4, y1 - 4), (x1 - 8, y1)), fill=0)

    def _render_keyboard(self, draw, keyboard: Keyboard, bounds: Bounds, focused: bool) -> None:
        x0, y0, x1, y1 = bounds
        if not keyboard.rows:
            return
        row_height = max(18, (y1 - y0) // len(keyboard.rows))
        for row_index, row in enumerate(keyboard.rows):
            if not row:
                continue
            key_width = max(1, (x1 - x0) // len(row))
            for column, label in enumerate(row):
                left = x0 + column * key_width
                right = x1 if column == len(row) - 1 else left + key_width
                top = y0 + row_index * row_height
                bottom = y1 if row_index == len(keyboard.rows) - 1 else top + row_height
                selected = row_index == keyboard.selected_row and column == keyboard.selected_column
                fill, ink = (0, 255) if selected else (255, 0)
                draw.rectangle((left + 1, top + 1, right - 2, bottom - 2), fill=fill, outline=ink, width=2 if selected and focused else 1)
                shown = "_" if label == "SPACE" else ("<" if label == "BACK" else label)
                self._draw_text(draw, (left + 2, top + 2, right - 3, bottom - 3), shown, 11, "center", selected, selected, False)

    def _load_image(self, source, source_size=None, source_mode="L"):
        if hasattr(source, "convert") and hasattr(source, "size"):
            return source.convert("L")
        data: bytes
        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.suffix.lower() == ".bin":
                data = path.read_bytes()
            else:
                return Image.open(path).convert("L")
        elif isinstance(source, bytes):
            data = source
            try:
                return Image.open(BytesIO(data)).convert("L")
            except Exception:
                pass
        else:
            return None
        if source_size:
            try:
                return Image.frombytes(source_mode, source_size, data).convert("L")
            except (ValueError, TypeError):
                return None
        side = math.isqrt(len(data))
        if side * side == len(data):
            return Image.frombytes("L", (side, side), data)
        return None

    def _render_image(self, target, component: ImageComponent, bounds: Bounds) -> None:
        source = self._load_image(component.source, component.source_size, component.source_mode)
        if source is None:
            return
        width, height = _size(bounds)
        if width <= 0 or height <= 0:
            return
        if component.fit == "stretch":
            rendered = source.resize((width, height), Image.Resampling.LANCZOS)
        else:
            rendered = ImageOps.contain(source, (width, height), Image.Resampling.LANCZOS)
        if component.invert:
            rendered = ImageOps.invert(rendered)
        x = bounds[0] + (width - rendered.width) // 2
        y = bounds[1] + (height - rendered.height) // 2
        target.paste(rendered, (x, y))

    def _render_qr(self, target, draw, component: QRCode, bounds: Bounds) -> None:
        try:
            import qrcode

            qr = qrcode.QRCode(border=1, box_size=2)
            qr.add_data(component.data)
            qr.make(fit=True)
            rendered = qr.make_image(fill_color="black", back_color="white").convert("L")
            rendered = ImageOps.contain(rendered, _size(bounds), Image.Resampling.NEAREST)
            x = bounds[0] + (bounds[2] - bounds[0] - rendered.width) // 2
            y = bounds[1] + (bounds[3] - bounds[1] - rendered.height) // 2
            target.paste(rendered, (x, y))
        except Exception:
            draw.rectangle((bounds[0], bounds[1], bounds[2] - 1, bounds[3] - 1), outline=0)
            self._draw_text(draw, bounds, "QR unavailable", 11, "center", False, False, True)

    def _wrap(self, draw, text: str, font, max_width: int) -> list[str]:
        result: list[str] = []
        for paragraph in str(text).splitlines() or [""]:
            words = paragraph.split(" ")
            line = ""
            for word in words:
                candidate = word if not line else f"{line} {word}"
                if not line or draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
                    line = candidate
                else:
                    result.append(line)
                    line = word
            result.append(line)
        return result

    def _draw_text(
        self,
        draw,
        bounds: Bounds,
        text: str,
        size: int,
        align: str,
        bold: bool,
        invert: bool,
        wrap: bool,
    ) -> None:
        x0, y0, x1, y1 = bounds
        if x1 <= x0 or y1 <= y0:
            return
        font = get_font(size, bold)
        lines = self._wrap(draw, text, font, x1 - x0) if wrap else str(text).splitlines()[:1]
        line_height = max(size + 2, draw.textbbox((0, 0), "Ag", font=font)[3] + 2)
        total_height = line_height * len(lines)
        y = y0 + max(0, (y1 - y0 - total_height) // 2)
        ink = 255 if invert else 0
        for line in lines:
            width = draw.textbbox((0, 0), line, font=font)[2]
            if align == "center":
                x = x0 + max(0, (x1 - x0 - width) // 2)
            elif align == "right":
                x = max(x0, x1 - width)
            else:
                x = x0
            draw.text((x, y), line, fill=ink, font=font)
            y += line_height
            if y >= y1:
                break
