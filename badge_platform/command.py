"""Non-shell subprocess helpers shared by platform services."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CommandRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        timeout: float = 20,
        cwd: str | os.PathLike[str] | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        clean_args = tuple(str(arg) for arg in args)
        try:
            completed = subprocess.run(
                clean_args,
                cwd=cwd,
                env=dict(env) if env else None,
                capture_output=True,
                text=True,
                input=input_text,
                stdin=subprocess.DEVNULL if input_text is None else None,
                timeout=timeout,
                check=False,
            )
            return CommandResult(clean_args, completed.returncode, completed.stdout, completed.stderr)
        except FileNotFoundError as exc:
            return CommandResult(clean_args, 127, "", str(exc))
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return CommandResult(clean_args, 124, stdout, stderr or "command timed out")
