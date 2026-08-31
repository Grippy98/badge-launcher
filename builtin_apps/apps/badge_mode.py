"""Portable badge identity screen and editor."""

from __future__ import annotations

from pathlib import Path
import random

from badge_sdk import (
    Action,
    App,
    Box,
    Canvas,
    Column,
    Image,
    InputEvent,
    Keyboard,
    QRCode,
    RefreshMode,
    Row,
    Screen,
    Text,
    TextInput,
)


class BadgeModeApp(App):
    """Show and edit the name, description, artwork, and QR destination."""

    app_id = "badge-mode"
    name = "Badge Mode"
    category = "apps"
    description = "Display your badge identity and project link"

    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".bin"}
    EDIT_FIELDS = (
        ("badge_name", "Edit Name", 64),
        ("badge_info", "Edit Info", 256),
        ("badge_qr_link", "Edit QR Link", 512),
    )

    def __init__(self, *, rng: random.Random | None = None) -> None:
        super().__init__()
        self.rng = rng or random.Random()
        self.profile_images: list[Path] = []
        self.bundled_logos: dict[int, Path] = {}
        self.profile_index = 0
        self.edit_index: int | None = None
        self.edit_value = ""
        self.keyboard_row = 0
        self.keyboard_column = 0
        self.keyboard_shift = False
        self._random_logo = self.rng.choice((1, 2))

    @property
    def settings(self):
        if not self.context:
            raise RuntimeError("Badge Mode is not attached to a runtime")
        return self.context.services.settings

    def on_start(self) -> None:
        if not self.context:
            return
        user_profiles = self.context.data_dir / "profile_images"
        user_profiles.mkdir(parents=True, exist_ok=True)
        bundled_profiles = self.context.resources / "profile_images"
        asset_root = self.context.resources / "assets"
        self.bundled_logos = {
            index: path
            for index, path in (
                (1, asset_root / "beagle_logo.bin"),
                (2, asset_root / "ti_logo.bin"),
            )
            if path.is_file()
        }
        seen: set[Path] = set()
        self.profile_images = []
        for directory in (user_profiles, bundled_profiles):
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
                if path.is_file() and path.suffix.lower() in self.IMAGE_SUFFIXES:
                    resolved = path.resolve()
                    if resolved not in seen:
                        seen.add(resolved)
                        self.profile_images.append(resolved)

    def _cycle_art(self, delta: int) -> None:
        if self.profile_images:
            self.profile_index = (self.profile_index + delta) % len(self.profile_images)
        else:
            logo = int(self.settings.get("badge_logo", 0))
            logo = (logo + delta) % 3
            self.settings.set("badge_logo", logo)
            if logo == 0:
                self._random_logo = self.rng.choice((1, 2))
        self.invalidate(RefreshMode.FULL)

    def _begin_edit(self) -> None:
        self.edit_index = 0
        self.edit_value = str(self.settings.get(self.EDIT_FIELDS[0][0], ""))
        self.keyboard_row = 0
        self.keyboard_column = 0
        self.keyboard_shift = False
        self.invalidate(RefreshMode.FULL)

    def _set_edit_value(self, value: str) -> None:
        self.edit_value = value

    def _advance_edit(self) -> None:
        if self.edit_index is None:
            return
        key, _title, _limit = self.EDIT_FIELDS[self.edit_index]
        self.settings.set(key, self.edit_value)
        if self.edit_index + 1 < len(self.EDIT_FIELDS):
            self.edit_index += 1
            next_key, _next_title, _next_limit = self.EDIT_FIELDS[self.edit_index]
            self.edit_value = str(self.settings.get(next_key, ""))
            self.keyboard_row = 0
            self.keyboard_column = 0
            self.keyboard_shift = False
        else:
            self.edit_index = None
            self.edit_value = ""
        self.invalidate(RefreshMode.FULL)

    def _keyboard_rows(self) -> list[list[str]]:
        rows = [
            list("1234567890"),
            list("qwertyuiop"),
            list("asdfghjkl"),
            list("zxcvbnm"),
            [".", ":", "/", "-", "_", "@"],
            ["SHIFT*" if self.keyboard_shift else "SHIFT", "SPACE", "NL", "BACK", "OK"],
        ]
        if self.keyboard_shift:
            rows[1] = [key.upper() for key in rows[1]]
            rows[2] = [key.upper() for key in rows[2]]
            rows[3] = [key.upper() for key in rows[3]]
        return rows

    def _keyboard_moved(self, row: int, column: int) -> None:
        self.keyboard_row = row
        self.keyboard_column = column

    def _keyboard_key(self, key: str) -> None:
        if self.edit_index is None:
            return
        if key in {"SHIFT", "SHIFT*"}:
            self.keyboard_shift = not self.keyboard_shift
        elif key == "OK":
            self._advance_edit()
            return
        elif key == "BACK":
            self.edit_value = self.edit_value[:-1]
        else:
            addition = " " if key == "SPACE" else ("\n" if key == "NL" else key)
            limit = self.EDIT_FIELDS[self.edit_index][2]
            self.edit_value = (self.edit_value + addition)[:limit]
            if self.keyboard_shift and key.isalpha() and len(key) == 1:
                self.keyboard_shift = False
        self.invalidate(RefreshMode.PARTIAL)

    def handle(self, event: InputEvent) -> bool:
        if self.edit_index is not None:
            # Legacy Badge Mode used BACK to save the current field and advance.
            if event.action == Action.BACK:
                self._advance_edit()
                return True
            return False
        if event.action == Action.LEFT:
            self._cycle_art(-1)
            return True
        if event.action == Action.RIGHT:
            self._cycle_art(1)
            return True
        if event.action == Action.SELECT:
            self._begin_edit()
            return True
        return False

    def _draw_logo(self, draw, bounds: tuple[int, int, int, int]) -> None:
        x0, y0, x1, y1 = bounds
        inset = 5
        draw.rectangle((x0 + inset, y0 + inset, x1 - inset - 1, y1 - inset - 1), outline=0, width=3)
        configured = int(self.settings.get("badge_logo", 0))
        choice = self._random_logo if configured == 0 else configured
        label = "BB" if choice == 1 else "TI"
        text_x = x0 + max(8, (x1 - x0) // 2 - 12)
        text_y = y0 + max(8, (y1 - y0) // 2 - 6)
        draw.text((text_x, text_y), label, fill=0)

    def _art(self):
        if self.profile_images:
            return Image(self.profile_images[self.profile_index], fit="contain", width=128, height=128)
        configured = int(self.settings.get("badge_logo", 0))
        choice = self._random_logo if configured == 0 else configured
        if choice in self.bundled_logos:
            return Image(
                self.bundled_logos[choice],
                source_size=(128, 128),
                source_mode="L",
                fit="contain",
                width=128,
                height=128,
            )
        return Canvas(self._draw_logo, width=128, height=128, flex=0)

    def _normal_view(self) -> Screen:
        badge_name = str(self.settings.get("badge_name", "Beagle\nBadge"))
        badge_info = str(self.settings.get("badge_info", "Badge Launcher"))
        qr_link = str(self.settings.get("badge_qr_link", "https://beagleboard.org"))
        if self.profile_images:
            art_status = f"Profile {self.profile_index + 1}/{len(self.profile_images)}"
        else:
            modes = ("Random", "Beagle", "TI")
            art_status = "Logo: " + modes[int(self.settings.get("badge_logo", 0)) % len(modes)]
        return Screen(
            Column(
                Text(art_status, size=11, align="center"),
                Row(
                    Box(self._art(), padding=2, border=0, width=138, height=138),
                    Box(QRCode(qr_link, size=128), padding=3, width=138, height=138),
                    gap=12,
                    align="center",
                    height=145,
                ),
                Text(badge_name, size=22, bold=True, align="center", height=42),
                Text(badge_info, size=13, align="center", flex=1),
                gap=3,
                padding=5,
            ),
            footer="SELECT: edit  LEFT/RIGHT: artwork  BACK: exit",
        )

    def _editor_view(self) -> Screen:
        assert self.edit_index is not None
        _key, title, limit = self.EDIT_FIELDS[self.edit_index]
        return Screen(
            Column(
                Text(f"Field {self.edit_index + 1} of {len(self.EDIT_FIELDS)}", size=11, align="center"),
                TextInput(
                    self.edit_value,
                    on_change=self._set_edit_value,
                    on_submit=self._advance_edit,
                    max_length=limit,
                    key="badge-editor",
                    height=64 if self.edit_index != 2 else 42,
                ),
                Text("DOWN: on-screen keyboard", size=11, align="center"),
                Keyboard(
                    self._keyboard_rows(),
                    self._keyboard_key,
                    selected_row=self.keyboard_row,
                    selected_column=self.keyboard_column,
                    on_move=self._keyboard_moved,
                    key="badge-keyboard",
                ),
                padding=6,
                gap=5,
            ),
            title=title,
            footer="SELECT: choose  BACK: save and continue",
        )

    def view(self) -> Screen:
        return self._editor_view() if self.edit_index is not None else self._normal_view()
