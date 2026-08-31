"""Explicit, dependency-free lifecycle for BadgeBeam's MGMT experiment."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import re
import subprocess
from typing import Protocol
from uuid import UUID


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str]], CommandResult]


class LegacyAdvertisingError(RuntimeError):
    """Raised when btmgmt cannot install the requested advertisement."""


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


class LegacyMgmtAdvertiser:
    """Own one opt-in btmgmt Add Advertising (0x003e) instance.

    This deliberately uses argv-only subprocess calls and never invokes a
    shell. It is experimental: callers must choose the mode explicitly and
    validate the resulting packets on their controller/BlueZ/kernel image.
    """

    def __init__(
        self,
        adapter: str,
        service_uuid: str,
        *,
        instance: int = 1,
        runner: Runner = run_command,
    ) -> None:
        if not re.fullmatch(r"hci[0-9]+", adapter):
            raise ValueError(f"invalid Bluetooth adapter: {adapter!r}")
        if not 1 <= int(instance) <= 254:
            raise ValueError("advertising instance must be between 1 and 254")
        self.adapter = adapter
        self.service_uuid = str(UUID(service_uuid))
        self.instance = int(instance)
        self.runner = runner
        self.active = False

    @property
    def add_command(self) -> tuple[str, ...]:
        # No -P/--phy flag: secondary-channel flags select the extended
        # advertising path that this experiment is intended to avoid.
        return (
            "btmgmt",
            "--index",
            self.adapter,
            "add-adv",
            "-c",
            "-g",
            "-u",
            self.service_uuid,
            "-n",
            str(self.instance),
        )

    @property
    def remove_command(self) -> tuple[str, ...]:
        return (
            "btmgmt",
            "--index",
            self.adapter,
            "rm-adv",
            str(self.instance),
        )

    def start(self) -> None:
        # Remove a stale instance left by an unclean service exit. This mode is
        # opt-in because the chosen instance must be reserved for BadgeBeam.
        try:
            self.runner(self.remove_command)
            result = self.runner(self.add_command)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise LegacyAdvertisingError(str(error)) from error
        if result.returncode:
            detail = (result.stderr or result.stdout or "btmgmt add-adv failed").strip()
            raise LegacyAdvertisingError(detail)
        self.active = True

    def stop(self) -> None:
        if self.active:
            try:
                self.runner(self.remove_command)
            except (OSError, subprocess.TimeoutExpired):
                pass
            finally:
                self.active = False


__all__ = ["LegacyAdvertisingError", "LegacyMgmtAdvertiser", "run_command"]
