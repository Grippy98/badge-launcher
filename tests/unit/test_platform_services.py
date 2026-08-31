import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

from badge_platform.badgebeam import BadgeBeamService
from badge_platform.command import CommandRunner
from badge_platform.hardware import I2CService, SoundService
from badge_platform.input import PLAIN, SHIFTED
from badge_platform.network import NetworkService, _split_escaped
from badge_platform.settings import Settings
from badge_platform.system import SystemService
from builtin_apps.settings.wifi import WifiApp
from builtin_apps.tools.file_manager import FileManagerApp
from scripts.badgebeam_advertising import LegacyAdvertisingError, LegacyMgmtAdvertiser
from scripts.badgebeam_frames import FrameAccumulator


def test_settings_migrate_and_write_atomically(tmp_path):
    legacy = tmp_path / "config.json"
    legacy.write_text('{"badge_name":"Ada","sound_enabled":false}')
    destination = tmp_path / "state" / "settings.json"
    settings = Settings(destination, legacy)
    assert settings.get("badge_name") == "Ada"
    settings.set("badge_info", "Developer")
    reloaded = Settings(destination)
    assert reloaded.get("badge_info") == "Developer"
    assert destination.stat().st_mode & 0o777 == 0o600


def test_nmcli_escape_parser_does_not_use_shell_splitting():
    assert _split_escaped(r"*:Cafe\: Upstairs:82:WPA2") == ["*", "Cafe: Upstairs", "82", "WPA2"]


def test_physical_keyboard_maps_common_password_punctuation():
    assert "".join(PLAIN[code] for code in (12, 13, 26, 27, 39, 40, 41, 43, 53)) == "-=[];'`\\/"
    assert "".join(SHIFTED[code] for code in (12, 13, 26, 27, 39, 40, 41, 43, 53)) == '_+{}:\"~|?'


def test_wifi_keyboard_supports_uppercase_and_password_punctuation():
    app = WifiApp()
    app._keyboard_key("SHIFT")
    assert app._keyboard_rows()[1][0] == "Q"
    app._keyboard_key("Q")
    app._keyboard_key("@")
    assert app.password == "Q@"
    assert not app.keyboard_shift


def test_command_runner_uses_private_stdin_for_input(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr("badge_platform.command.subprocess.run", fake_run)
    result = CommandRunner().run(["tool", "safe"], input_text="secret\n")
    assert result.ok
    assert result.args == ("tool", "safe")
    assert captured["input"] == "secret\n"
    assert "secret" not in " ".join(captured["args"])


def test_wifi_password_never_appears_in_process_arguments():
    class CaptureCommands:
        def __init__(self):
            self.args = []
            self.input_text = None

        def run(self, args, **kwargs):
            self.args = list(args)
            self.input_text = kwargs.get("input_text")
            return SimpleNamespace(ok=True, stdout="connected", stderr="")

    commands = CaptureCommands()
    ok, _message = NetworkService(commands).connect("Cafe WiFi", "top secret", "wlan0")
    assert ok
    assert commands.args == [
        "nmcli",
        "--ask",
        "device",
        "wifi",
        "connect",
        "Cafe WiFi",
        "ifname",
        "wlan0",
    ]
    assert commands.input_text == "top secret\n"
    assert "top secret" not in commands.args


class FakeCommands:
    def run(self, args, timeout=20):
        class Result:
            ok = True
            stderr = ""
            stdout = """     0 1 2 3 4 5 6 7 8 9 a b c d e f
00:                         -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- UU -- -- -- -- -- -- 5b -- -- -- --
"""

        return Result()


def test_i2c_parser_handles_kernel_owned_addresses(tmp_path, monkeypatch):
    service = I2CService(FakeCommands())
    monkeypatch.setattr(service, "buses", lambda: [2])
    devices, error = service.scan(2)
    assert error == ""
    assert [(device.address, device.in_use) for device in devices] == [(0x54, True), (0x5B, False)]


def test_system_service_prefers_badge_fuel_gauge_over_other_supplies(tmp_path):
    def supply(name, kind, capacity, status="Unknown", present="1"):
        root = tmp_path / name
        root.mkdir()
        (root / "type").write_text(kind)
        (root / "capacity").write_text(str(capacity))
        (root / "status").write_text(status)
        (root / "present").write_text(present)

    supply("usb", "USB", 100)
    supply("BAT0", "Battery", 20, "Discharging")
    supply("bq27541-0", "Battery", 63, "Charging")
    service = SystemService(FakeCommands(), power_supply_root=tmp_path)
    assert service.battery().name == "bq27541-0"
    assert service.battery().percent == 63

    (tmp_path / "bq27541-0" / "present").write_text("0")
    assert service.battery().name == "BAT0"


def test_sound_device_failure_disables_sound_without_crashing():
    class BrokenStream:
        def __init__(self):
            self.closed = False

        def write(self, _payload):
            raise OSError("device removed")

        def close(self):
            self.closed = True

    sound = SoundService(open_device=False)
    stream = BrokenStream()
    sound.stream = stream
    sound.start(1000)
    assert stream.closed
    assert sound.stream is None


def test_sound_stop_and_close_silence_an_active_tone_after_disable(monkeypatch):
    class RecordingStream:
        def __init__(self):
            self.events = []
            self.closed = False

        def write(self, payload):
            self.events.append(SoundService.EVENT.unpack(payload)[2:])

        def close(self):
            self.closed = True

    sleeps = []
    monkeypatch.setattr("badge_platform.hardware.time.sleep", sleeps.append)
    sound = SoundService(enabled=True, open_device=False)
    stream = RecordingStream()
    sound.stream = stream

    sound.start(900)
    assert stream.events[-2:] == [
        (SoundService.EV_SND, SoundService.SND_TONE, 900),
        (SoundService.EV_SYN, 0, 0),
    ]

    sound.enabled = False
    before_disabled_start = list(stream.events)
    sound.start(1200)
    sound.beep(0.5, 1200)
    assert stream.events == before_disabled_start
    assert sleeps == []

    sound.stop()
    assert stream.events[-2:] == [
        (SoundService.EV_SND, SoundService.SND_TONE, 0),
        (SoundService.EV_SYN, 0, 0),
    ]

    sound.close()
    assert stream.events[-2:] == [
        (SoundService.EV_SND, SoundService.SND_TONE, 0),
        (SoundService.EV_SYN, 0, 0),
    ]
    assert stream.closed


def test_file_manager_defaults_to_its_scoped_data_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("BADGE_FILES_ROOT", raising=False)
    app = FileManagerApp()
    app._attach(SimpleNamespace(data_dir=tmp_path / "file-manager"))
    app.on_start()
    assert app.root == (tmp_path / "file-manager" / "files").resolve()
    assert app.root.is_dir()


def test_badgebeam_status_checks_receiver_pid_and_payload(tmp_path):
    service = BadgeBeamService(tmp_path)
    assert service.status() == "BadgeBeam receiver unavailable"

    service.data_dir.mkdir(parents=True)
    service.marker.write_text(json.dumps({"pid": os.getpid()}))
    assert service.running
    assert service.status() == "BadgeBeam receiver running"

    service.marker.write_text(json.dumps({"pid": os.getpid(), "advertising": "external"}))
    assert "external BLE advertising required" in service.status()

    service.marker.write_text(json.dumps({"pid": os.getpid(), "advertising": "legacy-mgmt"}))
    assert "experimental" in service.status()

    service.marker.write_text(json.dumps({"pid": 999_999_999}))
    service.payload.write_bytes(b"frame")
    assert not service.running
    assert service.status() == "Receiver stopped; showing last image"


def test_badgebeam_frame_accumulator_preserves_boundary_tail():
    accumulator = FrameAccumulator(4)
    assert accumulator.push(b"abc") == []
    assert accumulator.push(b"defghi") == [b"abcd", b"efgh"]
    assert bytes(accumulator.buffer) == b"i"


def test_legacy_mgmt_advertiser_uses_argv_and_removes_its_instance():
    calls = []

    def runner(args):
        calls.append(tuple(args))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    advertiser = LegacyMgmtAdvertiser(
        "hci0",
        "12345678-1234-5678-1234-56789abcdef0",
        instance=3,
        runner=runner,
    )
    advertiser.start()
    advertiser.stop()
    assert calls == [
        ("btmgmt", "--index", "hci0", "rm-adv", "3"),
        (
            "btmgmt",
            "--index",
            "hci0",
            "add-adv",
            "-c",
            "-g",
            "-u",
            "12345678-1234-5678-1234-56789abcdef0",
            "-n",
            "3",
        ),
        ("btmgmt", "--index", "hci0", "rm-adv", "3"),
    ]


def test_legacy_mgmt_advertiser_reports_add_failure():
    def runner(args):
        failed = "add-adv" in args
        return SimpleNamespace(
            returncode=1 if failed else 0,
            stdout="",
            stderr="controller rejected advertisement" if failed else "",
        )

    advertiser = LegacyMgmtAdvertiser(
        "hci1",
        "12345678-1234-5678-1234-56789abcdef0",
        runner=runner,
    )
    try:
        advertiser.start()
    except LegacyAdvertisingError as error:
        assert "controller rejected" in str(error)
    else:
        raise AssertionError("expected LegacyAdvertisingError")
    assert not advertiser.active


def test_legacy_mgmt_advertiser_rejects_reserved_instance_values():
    for instance in (0, 255):
        try:
            LegacyMgmtAdvertiser(
                "hci0",
                "12345678-1234-5678-1234-56789abcdef0",
                instance=instance,
            )
        except ValueError as error:
            assert "between 1 and 254" in str(error)
        else:
            raise AssertionError(f"expected instance {instance} to be rejected")

    advertiser = LegacyMgmtAdvertiser(
        "hci0",
        "12345678-1234-5678-1234-56789abcdef0",
        instance=254,
    )
    assert advertiser.instance == 254
