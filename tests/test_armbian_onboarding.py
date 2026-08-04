import os
import stat
import tempfile
import unittest

from core.armbian_onboarding import (
    ArmbianOnboarding,
    ValidationError,
    validate_answers,
    validate_password,
    validate_username,
)


class ArmbianOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        for directory in (
            "etc/default",
            "root",
            "usr/lib/armbian",
            "proc",
        ):
            os.makedirs(os.path.join(self.root, directory), exist_ok=True)
        self._write("etc/armbian-release", 'BOARD=beaglebadge\nVERSION="26.08.0-trunk"\n')
        self._write("etc/default/locale", 'LANG="en_GB.UTF-8"\n')
        self._write("etc/timezone", "Europe/London\n")
        self._write("etc/passwd", "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\n")
        self._write("usr/lib/armbian/armbian-firstlogin", "#!/bin/sh\n")
        self._write("root/.not_logged_in_yet", "PRESET_NET_CHANGE_DEFAULTS=0\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, relative_path, content):
        path = os.path.join(self.root, relative_path)
        with open(path, "w") as output:
            output.write(content)

    @staticmethod
    def _answers():
        return {
            "root_password": "Root's-safe-$ecret1",
            "username": "Andrei98",
            "real_name": "Andrei Aldea",
            "user_password": "User-safe-$ecret2",
        }

    def _backend(self, runner=None):
        return ArmbianOnboarding(
            root=self.root,
            helper_path="/fixed/helper/path",
            runner=runner,
            proc_root=os.path.join(self.root, "proc"),
        )

    def test_detects_only_supported_pending_armbian(self):
        backend = self._backend()
        self.assertTrue(backend.is_supported())
        self.assertTrue(backend.is_pending())
        self.assertEqual(backend.system_version(), "Armbian 26.08.0-trunk")
        os.remove(os.path.join(self.root, "root/.not_logged_in_yet"))
        self.assertFalse(backend.is_pending())

    def test_validation_matches_armbian_username_rules(self):
        self.assertEqual(validate_username("Andrei98"), "andrei98")
        for invalid in ("", "98andrei", "andrei_badge", "root"):
            with self.assertRaises(ValidationError):
                validate_username(invalid)
        self.assertEqual(validate_password("x"), "x")
        with self.assertRaisesRegex(ValidationError, "Enter a password"):
            validate_password("")

    def test_preset_merge_is_atomic_private_and_shell_safe(self):
        backend = self._backend()
        backend._write_presets(validate_answers(self._answers()))
        marker = os.path.join(self.root, "root/.not_logged_in_yet")
        with open(marker) as source:
            contents = source.read()

        self.assertIn("PRESET_NET_CHANGE_DEFAULTS=0", contents)
        self.assertIn("PRESET_USER_NAME='andrei98'", contents)
        self.assertIn("PRESET_DEFAULT_REALNAME='Andrei Aldea'", contents)
        self.assertIn("PRESET_LOCALE='en_GB.UTF-8'", contents)
        self.assertIn("PRESET_TIMEZONE='Europe/London'", contents)
        self.assertIn("PRESET_ROOT_PASSWORD='Root'\"'\"'s-safe-$ecret1'", contents)
        self.assertEqual(stat.S_IMODE(os.stat(marker).st_mode), 0o600)

    def test_complete_passes_no_credentials_on_command_line(self):
        commands = []
        marker = os.path.join(self.root, "root/.not_logged_in_yet")

        def successful_runner(command):
            commands.append(command)
            os.remove(marker)
            return 0

        answers = self._answers()
        result = self._backend(successful_runner).complete(answers)
        self.assertTrue(result.complete)
        self.assertEqual(commands, ["/fixed/helper/path"])
        for secret_key in ("root_password", "user_password"):
            self.assertNotIn(answers[secret_key], commands[0])

    def test_failed_firstlogin_keeps_pending_marker_for_retry(self):
        result = self._backend(lambda _command: 256).complete(self._answers())
        self.assertFalse(result.complete)
        self.assertEqual(result.exit_code, 1)
        self.assertTrue(os.path.exists(os.path.join(self.root, "root/.not_logged_in_yet")))

    def test_existing_system_account_cannot_be_repurposed(self):
        answers = self._answers()
        answers["username"] = "daemon"
        with self.assertRaisesRegex(ValidationError, "already exists"):
            self._backend(lambda _command: 0).complete(answers)

    def test_partial_firstlogin_can_retry_its_regular_user(self):
        self._write(
            "etc/passwd",
            "root:x:0:0:root:/root:/bin/bash\n"
            "andrei98:x:1000:1000:Andrei Aldea:/home/andrei98:/bin/bash\n",
        )
        marker = os.path.join(self.root, "root/.not_logged_in_yet")

        def successful_retry(_command):
            os.remove(marker)
            return 0

        result = self._backend(successful_retry).complete(self._answers())
        self.assertTrue(result.complete)

    def test_running_console_firstlogin_is_not_raced(self):
        proc_dir = os.path.join(self.root, "proc/123")
        os.makedirs(proc_dir)
        with open(os.path.join(proc_dir, "cmdline"), "wb") as cmdline:
            cmdline.write(b"bash\0/usr/lib/armbian/armbian-firstlogin\0")
        called = []
        result = self._backend(lambda command: called.append(command)).complete(self._answers())
        self.assertFalse(result.complete)
        self.assertEqual(result.exit_code, 75)
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
