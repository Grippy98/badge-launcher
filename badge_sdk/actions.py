"""Portable input and display actions exposed to badge applications."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    QUIT = "quit"
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    SELECT = "select"
    BACK = "back"
    TEXT = "text"
    DELETE = "delete"


class RefreshMode(str, Enum):
    AUTO = "auto"
    PARTIAL = "partial"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class InputEvent:
    action: Action
    text: str = ""
    repeat: bool = False
