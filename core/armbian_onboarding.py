"""Integration with Armbian's existing first-login workflow.

Badge Launcher only collects the answers. Armbian remains responsible for
changing passwords, creating the sudo-enabled user, and completing the rest of
its first-login setup.
"""

import os


ARMBIAN_RELEASE = "/etc/armbian-release"
FIRSTLOGIN_MARKER = "/root/.not_logged_in_yet"
FIRSTLOGIN_PROGRAM = "/usr/lib/armbian/armbian-firstlogin"
DEFAULT_HELPER = "scripts/armbian-onboarding-helper"

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
    """Raised when a value cannot safely be passed to Armbian."""


class CompletionResult:
    """Result returned after asking Armbian to finish first-login."""

    def __init__(self, complete, exit_code=0, message=""):
        self.complete = complete
        self.exit_code = exit_code
        self.message = message


def _rooted(root, path):
    if root == "/":
        return path
    return root.rstrip("/") + path


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _chmod_private(path):
    """Set mode 0600 on CPython and the launcher's Unix MicroPython."""
    if hasattr(os, "chmod"):
        os.chmod(path, 0o600)
        return

    # The Unix MicroPython build intentionally exposes a small os module, but
    # it includes ffi (also used by drivers/input.py). Change the mode before
    # writing any preset values so credentials are never briefly world-readable.
    try:
        import ffi
        libc = ffi.open("libc.so.6")
        chmod = libc.func("i", "chmod", "si")
        if chmod(path, 0o600) != 0:
            raise OSError("chmod failed")
    except ImportError:
        raise OSError("No private-file mode implementation is available")


def _read_first_line(path, fallback):
    try:
        with open(path, "r") as source:
            value = source.readline().strip()
            return value if value else fallback
    except OSError:
        return fallback


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _read_locale(root):
    path = _rooted(root, "/etc/default/locale")
    try:
        with open(path, "r") as source:
            for line in source:
                if line.startswith("LANG="):
                    value = _unquote(line.split("=", 1)[1])
                    if _valid_system_token(value, allow_slash=False):
                        return value
    except OSError:
        pass
    return "en_US.UTF-8"


def _read_timezone(root):
    value = _read_first_line(_rooted(root, "/etc/timezone"), "Etc/UTC")
    if _valid_system_token(value, allow_slash=True):
        return value
    return "Etc/UTC"


def _valid_system_token(value, allow_slash):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+.-"
    if allow_slash:
        allowed += "/"
    return bool(value) and all(char in allowed for char in value)


def _shell_quote(value):
    """Return a Bash-safe, single-quoted scalar.

    Passwords never appear in a command line. Armbian's supported preset file
    is the only place they are handed off, and that file is mode 0600.
    """
    if "\n" in value or "\r" in value or "\x00" in value:
        raise ValidationError("Values cannot contain line breaks")
    return "'" + value.replace("'", "'\"'\"'") + "'"


def validate_username(username):
    if not username:
        raise ValidationError("Enter a username")
    if len(username) > 32:
        raise ValidationError("Username must be 32 characters or fewer")
    ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ascii_digits = "0123456789"
    if username[0] not in ascii_letters:
        raise ValidationError("Username must start with a letter")
    if not all(char in ascii_letters or char in ascii_digits for char in username):
        raise ValidationError("Use letters and numbers only")
    if username.lower() in ("root", "nobody"):
        raise ValidationError("Choose a different username")
    return username.lower()


def validate_real_name(real_name):
    real_name = real_name.strip()
    if not real_name:
        raise ValidationError("Enter your name")
    if len(real_name) > 64:
        raise ValidationError("Name must be 64 characters or fewer")
    if any(char in real_name for char in (":", "\n", "\r", "\x00")):
        raise ValidationError("Name contains an unsupported character")
    return real_name


def validate_password(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValidationError("Password must be 128 characters or fewer")
    if any(char in password for char in ("\n", "\r", "\x00")):
        raise ValidationError("Password contains an unsupported character")
    return password


def validate_answers(answers):
    normalized = {
        "root_password": validate_password(answers.get("root_password", "")),
        "username": validate_username(answers.get("username", "")),
        "real_name": validate_real_name(answers.get("real_name", "")),
        "user_password": validate_password(answers.get("user_password", "")),
    }
    if answers.get("root_password_confirm") != normalized["root_password"]:
        raise ValidationError("Root passwords do not match")
    if answers.get("user_password_confirm") != normalized["user_password"]:
        raise ValidationError("User passwords do not match")
    return normalized


def _process_is_firstlogin(proc_root="/proc"):
    """Detect an already-running Armbian first-login process."""
    try:
        entries = os.listdir(proc_root)
    except OSError:
        return False

    needle = FIRSTLOGIN_PROGRAM.encode()
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(proc_root.rstrip("/") + "/" + entry + "/cmdline", "rb") as cmdline:
                if needle in cmdline.read():
                    return True
        except OSError:
            pass
    return False


class ArmbianOnboarding:
    """Detect and complete Armbian onboarding without reimplementing it."""

    def __init__(self, root="/", helper_path=DEFAULT_HELPER, runner=None, proc_root="/proc"):
        self.root = root
        self.helper_path = helper_path
        self.runner = runner if runner is not None else os.system
        self.proc_root = proc_root

    @property
    def marker_path(self):
        return _rooted(self.root, FIRSTLOGIN_MARKER)

    def is_supported(self):
        return (
            _exists(_rooted(self.root, ARMBIAN_RELEASE))
            and _exists(_rooted(self.root, FIRSTLOGIN_PROGRAM))
        )

    def is_pending(self):
        return self.is_supported() and _exists(self.marker_path)

    def is_running(self):
        return _process_is_firstlogin(self.proc_root)

    def _accounts(self):
        accounts = []
        try:
            with open(_rooted(self.root, "/etc/passwd"), "r") as passwd_file:
                for line in passwd_file:
                    fields = line.rstrip("\n").split(":")
                    if len(fields) < 4:
                        continue
                    try:
                        uid = int(fields[2])
                    except ValueError:
                        continue
                    accounts.append((fields[0], uid))
        except OSError:
            pass
        return accounts

    def _validate_account_state(self, username):
        """Prevent Armbian from accidentally repurposing a system account."""
        accounts = self._accounts()
        regular_users = [name for name, uid in accounts if uid >= 1000 and name != "nobody"]
        if regular_users:
            # Armbian intentionally reuses an already-created regular user after
            # a power-loss or other partial first-login run.
            if username == regular_users[0]:
                return
            raise ValidationError("Armbian is already creating user " + regular_users[0])
        if any(name == username for name, _uid in accounts):
            raise ValidationError("Username already exists; choose another")

    def _preset_values(self, answers):
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

    def _write_presets(self, answers):
        """Atomically merge Badge Launcher answers into Armbian's marker."""
        existing = []
        try:
            with open(self.marker_path, "r") as marker:
                existing = marker.readlines()
        except OSError:
            pass

        kept = []
        for line in existing:
            stripped = line.lstrip()
            if any(stripped.startswith(key + "=") for key in MANAGED_KEYS):
                continue
            kept.append(line)

        if kept and not kept[-1].endswith("\n"):
            kept[-1] += "\n"
        kept.append("\n# Managed by Badge Launcher on-screen onboarding\n")
        for key, value in self._preset_values(answers).items():
            kept.append(key + "=" + _shell_quote(value) + "\n")

        temp_path = self.marker_path + ".badge-launcher.tmp"
        try:
            with open(temp_path, "w") as marker:
                _chmod_private(temp_path)
                for line in kept:
                    marker.write(line)
                marker.flush()
                if hasattr(os, "fsync"):
                    os.fsync(marker.fileno())
            os.rename(temp_path, self.marker_path)
            if hasattr(os, "sync"):
                os.sync()
        except Exception:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _exit_code(system_result):
        if system_result is None:
            return 1
        if system_result > 255:
            return (system_result >> 8) & 0xFF
        return system_result

    def complete(self, raw_answers):
        """Validate answers and run the distribution-owned first-login tool."""
        if not self.is_pending():
            return CompletionResult(True, 0, "Armbian onboarding is already complete")
        if self.is_running():
            return CompletionResult(False, 75, "Armbian setup is already running on another console")

        answers = validate_answers(raw_answers)
        self._validate_account_state(answers["username"])
        self._write_presets(answers)

        try:
            result = self.runner(self.helper_path)
        except Exception as error:
            return CompletionResult(False, 1, "Could not start Armbian setup: " + str(error))

        exit_code = self._exit_code(result)
        complete = not _exists(self.marker_path)
        if complete:
            return CompletionResult(True, exit_code, "Setup complete")
        if exit_code == 75:
            message = "Armbian setup is already running on another console"
        else:
            message = "Armbian setup did not finish; it is safe to retry"
        return CompletionResult(False, exit_code, message)
