"""Safe integration with Armbian's distribution-owned first-login workflow.

Badge Launcher collects and validates answers, writes them to Armbian's
standard private preset marker, then invokes Armbian's own first-login program.
It does not duplicate account creation or password management.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Callable


ARMBIAN_RELEASE = "/etc/armbian-release"
FIRSTLOGIN_MARKER = "/root/.not_logged_in_yet"
FIRSTLOGIN_PROGRAM = "/usr/lib/armbian/armbian-firstlogin"
FIRSTLOGIN_LOCK = "/run/badge-launcher-armbian-onboarding.lock"
FIRSTLOGIN_LOG = "/var/log/badge-launcher-onboarding.log"

MANAGED_KEYS = (
    "PRESET_ROOT_PASSWORD",
    "PRESET_USER_NAME",
    "PRESET_USER_PASSWORD",
    "PRESET_DEFAULT_REALNAME",
    "PRESET_USER_SHELL",
    "PRESET_LOCALE",
    "PRESET_TIMEZONE",
    "PRESET_CONNECT_WIRELESS",
    "SET_LANG_BASED_ON_LOCATION",
)


class ValidationError(ValueError):
    """Raised when an answer cannot safely be handed to Armbian."""


@dataclass(frozen=True, slots=True)
class CompletionResult:
    complete: bool
    exit_code: int = 0
    message: str = ""


def _rooted(root: str | os.PathLike[str], path: str) -> Path:
    root_path = Path(root)
    return Path(path) if root_path == Path("/") else root_path / path.lstrip("/")


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _read_release_value(path: Path, key: str) -> str:
    try:
        for line in path.read_text().splitlines():
            if line.startswith(f"{key}="):
                return _unquote(line.split("=", 1)[1])
    except OSError:
        pass
    return ""


def _valid_system_token(value: str, *, allow_slash: bool) -> bool:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+.-"
    if allow_slash:
        allowed += "/"
    return bool(value) and all(character in allowed for character in value)


def _read_locale(root: str | os.PathLike[str]) -> str:
    try:
        for line in _rooted(root, "/etc/default/locale").read_text().splitlines():
            if line.startswith("LANG="):
                value = _unquote(line.split("=", 1)[1])
                if _valid_system_token(value, allow_slash=False):
                    return value
    except OSError:
        pass
    return "en_US.UTF-8"


def _read_timezone(root: str | os.PathLike[str]) -> str:
    try:
        value = _rooted(root, "/etc/timezone").read_text().splitlines()[0].strip()
    except (OSError, IndexError):
        value = "Etc/UTC"
    return value if _valid_system_token(value, allow_slash=True) else "Etc/UTC"


def _shell_quote(value: str) -> str:
    """Encode one Bash-safe scalar for Armbian's preset marker."""

    if any(character in value for character in ("\n", "\r", "\x00")):
        raise ValidationError("Values cannot contain line breaks")
    return "'" + value.replace("'", "'\"'\"'") + "'"


def validate_username(username: str) -> str:
    if not username:
        raise ValidationError("Enter a username")
    if len(username) > 32:
        raise ValidationError("Username must be 32 characters or fewer")
    ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ascii_digits = "0123456789"
    if username[0] not in ascii_letters:
        raise ValidationError("Username must start with a letter")
    if not all(character in ascii_letters + ascii_digits for character in username):
        raise ValidationError("Use letters and numbers only")
    if username.lower() in {"root", "nobody"}:
        raise ValidationError("Choose a different username")
    return username.lower()


def validate_real_name(real_name: str) -> str:
    normalized = real_name.strip()
    if not normalized:
        raise ValidationError("Enter your name")
    if len(normalized) > 64:
        raise ValidationError("Name must be 64 characters or fewer")
    if any(character in normalized for character in (":", "\n", "\r", "\x00")):
        raise ValidationError("Name contains an unsupported character")
    return normalized


def validate_password(password: str) -> str:
    if not password:
        raise ValidationError("Enter a password")
    if len(password) > 128:
        raise ValidationError("Password must be 128 characters or fewer")
    if any(character in password for character in ("\n", "\r", "\x00")):
        raise ValidationError("Password contains an unsupported character")
    return password


def validate_answers(answers: dict[str, str]) -> dict[str, str]:
    return {
        "root_password": validate_password(answers.get("root_password", "")),
        "username": validate_username(answers.get("username", "")),
        "real_name": validate_real_name(answers.get("real_name", "")),
        "user_password": validate_password(answers.get("user_password", "")),
    }


def _process_is_firstlogin(proc_root: str | os.PathLike[str] = "/proc") -> bool:
    root = Path(proc_root)
    try:
        entries = tuple(root.iterdir())
    except OSError:
        return False
    needle = FIRSTLOGIN_PROGRAM.encode()
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if needle in (entry / "cmdline").read_bytes():
                return True
        except OSError:
            pass
    return False


class ArmbianOnboarding:
    """Detect, prepare, and complete Armbian onboarding."""

    def __init__(
        self,
        root: str | os.PathLike[str] = "/",
        *,
        runner: Callable[[str], int | None] | None = None,
        helper_path: str | None = None,
        proc_root: str | os.PathLike[str] = "/proc",
    ) -> None:
        self.root = Path(root)
        self.runner = runner
        self.helper_path = helper_path
        self.proc_root = Path(proc_root)

    @property
    def marker_path(self) -> Path:
        return _rooted(self.root, FIRSTLOGIN_MARKER)

    @property
    def firstlogin_path(self) -> Path:
        return _rooted(self.root, FIRSTLOGIN_PROGRAM)

    def is_supported(self) -> bool:
        return _rooted(self.root, ARMBIAN_RELEASE).exists() and self.firstlogin_path.exists()

    def is_pending(self) -> bool:
        return self.is_supported() and self.marker_path.exists()

    def system_version(self) -> str:
        version = _read_release_value(_rooted(self.root, ARMBIAN_RELEASE), "VERSION")
        return f"Armbian {version}" if version else "Armbian"

    def is_running(self) -> bool:
        return _process_is_firstlogin(self.proc_root)

    def _accounts(self) -> list[tuple[str, int]]:
        accounts: list[tuple[str, int]] = []
        try:
            lines = _rooted(self.root, "/etc/passwd").read_text().splitlines()
        except OSError:
            return accounts
        for line in lines:
            fields = line.split(":")
            if len(fields) < 4:
                continue
            try:
                accounts.append((fields[0], int(fields[2])))
            except ValueError:
                pass
        return accounts

    def _validate_account_state(self, username: str) -> None:
        accounts = self._accounts()
        regular_users = [name for name, uid in accounts if uid >= 1000 and name != "nobody"]
        if regular_users:
            # Armbian deliberately reuses the first regular user after a
            # partially completed first-login run.
            if username == regular_users[0]:
                return
            raise ValidationError(f"Armbian is already creating user {regular_users[0]}")
        if any(name == username for name, _uid in accounts):
            raise ValidationError("Username already exists; choose another")

    def _preset_values(self, answers: dict[str, str]) -> dict[str, str]:
        return {
            "PRESET_ROOT_PASSWORD": answers["root_password"],
            "PRESET_USER_NAME": answers["username"],
            "PRESET_USER_PASSWORD": answers["user_password"],
            "PRESET_DEFAULT_REALNAME": answers["real_name"],
            "PRESET_USER_SHELL": "bash",
            "PRESET_LOCALE": _read_locale(self.root),
            "PRESET_TIMEZONE": _read_timezone(self.root),
            "PRESET_CONNECT_WIRELESS": "n",
            "SET_LANG_BASED_ON_LOCATION": "n",
        }

    def _write_presets(self, answers: dict[str, str]) -> None:
        """Atomically merge managed values into the mode-0600 marker."""

        try:
            existing = self.marker_path.read_text().splitlines(keepends=True)
        except OSError:
            existing = []
        kept = [
            line
            for line in existing
            if not any(line.lstrip().startswith(f"{key}=") for key in MANAGED_KEYS)
        ]
        if kept and not kept[-1].endswith("\n"):
            kept[-1] += "\n"
        kept.append("\n# Managed by Badge Launcher on-screen onboarding\n")
        kept.extend(
            f"{key}={_shell_quote(value)}\n"
            for key, value in self._preset_values(answers).items()
        )

        self.marker_path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".badge-onboarding-",
            dir=self.marker_path.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(file_descriptor, 0o600)
            with os.fdopen(file_descriptor, "w") as marker:
                marker.writelines(kept)
                marker.flush()
                os.fsync(marker.fileno())
            os.replace(temporary, self.marker_path)
            os.chmod(self.marker_path, 0o600)
            try:
                directory = os.open(self.marker_path.parent, os.O_RDONLY | os.O_DIRECTORY)
            except (AttributeError, OSError):
                directory = None
            if directory is not None:
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except Exception:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
            try:
                temporary.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _exit_code(result: int | None) -> int:
        if result is None:
            return 1
        return (result >> 8) & 0xFF if result > 255 else int(result)

    def _run_firstlogin(self) -> int:
        """Run first-login with a real console, private log, and process lock."""

        lock = _rooted(self.root, FIRSTLOGIN_LOCK)
        log = _rooted(self.root, FIRSTLOGIN_LOG)
        try:
            lock.mkdir(parents=True)
        except FileExistsError:
            return 75
        try:
            tty = next(
                (path for path in (Path("/dev/tty0"), Path("/dev/console")) if path.exists()),
                None,
            )
            if tty is None:
                return 69
            log.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with open(tty, "rb", buffering=0) as console, os.fdopen(descriptor, "wb", buffering=0) as output:
                completed = subprocess.run(
                    [str(self.firstlogin_path)],
                    stdin=console,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            result = completed.returncode
            return result if result or not self.marker_path.exists() else 1
        except OSError:
            return 69
        finally:
            try:
                lock.rmdir()
            except OSError:
                pass

    def complete(self, raw_answers: dict[str, str]) -> CompletionResult:
        """Validate answers and ask Armbian to complete its own setup."""

        if not self.is_pending():
            return CompletionResult(True, 0, "Armbian onboarding is already complete")
        if self.is_running():
            return CompletionResult(False, 75, "Armbian setup is already running on another console")

        answers = validate_answers(raw_answers)
        self._validate_account_state(answers["username"])
        self._write_presets(answers)

        try:
            if self.runner is not None:
                command = self.helper_path or str(self.firstlogin_path)
                result = self.runner(command)
                exit_code = self._exit_code(result)
            elif self.helper_path:
                completed = subprocess.run([self.helper_path], check=False)
                exit_code = completed.returncode
            else:
                exit_code = self._run_firstlogin()
        except Exception as error:
            return CompletionResult(False, 1, f"Could not start Armbian setup: {error}")

        complete = not self.marker_path.exists()
        if complete:
            return CompletionResult(True, exit_code, "Setup complete")
        message = (
            "Armbian setup is already running on another console"
            if exit_code == 75
            else "Armbian setup did not finish; it is safe to retry"
        )
        return CompletionResult(False, exit_code, message)
