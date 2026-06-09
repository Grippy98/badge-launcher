"""E-ink friendly IIO sensor visualizer for the BeagleBadge."""

import math
import os
import sys
import time

import lvgl as lv

if "core" not in sys.path:
    sys.path.append("core")

from core import app


IIO_ROOT = "/sys/bus/iio/devices"
ADC_LIGHT_CHANNEL = 2  # k3-am62l3-badge.dts: V23 is the on-board light sensor.
ADC_MAX_RAW = 4095.0
ADC_BAR_MAX_RAW = 256.0
ACCEL_FULL_SCALE_G = 2.0
OPT3001_BAR_MAX_LUX = 2000.0
BAR_SLOTS = 10
REFRESH_MS = 150
ACCEL_TARGET_SAMPLING_FREQUENCY = "104"
OPT3001_TARGET_INT_TIME = "0.1"
SCAN_INTERVAL_MS = 4000
QWIIC_BUSES = (1, 3)
OPT3001_ADDRESSES = (0x44, 0x45)


def _path_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _read_text(path):
    try:
        with open(path, "r") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _write_text(path, value):
    try:
        with open(path, "w") as handle:
            handle.write(value)
        return True
    except OSError:
        return False


def _read_float(path):
    text = _read_text(path)
    if text is None or text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _read_int(path):
    text = _read_text(path)
    if text is None or text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _clamp(value, lower, upper):
    if value < lower:
        return lower
    if value > upper:
        return upper
    return value


def _now_ms():
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.time() * 1000)


class SensorVisualizerApp(app.App):
    def __init__(self):
        super().__init__("IIO Sensors")
        self.screen = None
        self.timer = None
        self.current_key = 0
        self.key_state = lv.INDEV_STATE.RELEASED
        self.prev_state = lv.INDEV_STATE.RELEASED
        self.last_scan_ms = -SCAN_INTERVAL_MS
        self.last_probe = None
        self.render_cache = {}
        self.opt3001_driver_available = _path_exists("/sys/bus/i2c/drivers/opt3001")
        self.accel_path = None
        self.accel_original_sampling_frequency = None
        self.opt3001_path = None
        self.opt3001_original_int_time = None

    def enter(self, on_exit=None):
        self.on_exit_cb = on_exit
        self.perform_full_refresh()

        self.screen = lv.obj()
        self.screen.set_style_bg_color(lv.color_white(), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        self.screen.set_style_border_width(0, 0)
        self.screen.set_style_pad_all(0, 0)
        lv.screen_load(self.screen)

        import input

        if input.driver and input.driver.group:
            input.driver.group.remove_all_objs()
            self.screen.add_flag(lv.obj.FLAG.CLICKABLE)
            input.driver.group.add_obj(self.screen)
            lv.group_focus_obj(self.screen)

        self.screen.add_event_cb(self.on_key_event, lv.EVENT.KEY, None)
        self.build_ui()
        self.refresh(None)
        self.timer = lv.timer_create(self.refresh, REFRESH_MS, None)

    def exit(self):
        self.restore_runtime_tuning()
        if self.timer:
            self.timer.delete()
            self.timer = None
        if self.screen:
            self.screen.delete()
            self.screen = None

    def perform_full_refresh(self):
        try:
            from core.menu import full_refresh
            full_refresh()
        except Exception:
            pass

    def on_key_event(self, event):
        self.current_key = event.get_key()
        self.key_state = lv.INDEV_STATE.PRESSED

    def build_ui(self):
        disp = lv.display_get_default()
        width = disp.get_horizontal_resolution()

        self.title = lv.label(self.screen)
        self.title.set_text("IIO SENSORS")
        self.title.set_pos(10, 6)
        self.title.set_style_text_color(lv.color_black(), 0)
        self.try_set_font(self.title, "font_montserrat_24")

        self.exit_hint = lv.label(self.screen)
        self.exit_hint.set_text("ESC exit")
        self.exit_hint.set_style_text_color(lv.color_black(), 0)
        self.exit_hint.set_pos(width - 80, 12)
        self.try_set_font(self.exit_hint, "font_montserrat_14")

        self.rule_top = self.make_rule(8, 36, width - 16)

        self.light_title = self.make_label("ON-BOARD LIGHT", 10, 48, "font_montserrat_16")
        self.light_value = self.make_label("--", 10, 70, "font_montserrat_24")
        self.light_detail = self.make_label("", 94, 76, "font_montserrat_16")
        self.light_bar = self.make_segment_bar(246, 74)

        self.rule_mid = self.make_rule(8, 122, width - 16)

        self.accel_title = self.make_label("ON-BOARD ACCEL", 10, 134, "font_montserrat_16")
        self.accel_x_title = self.make_label("X", 18, 172, "font_montserrat_16")
        self.accel_y_title = self.make_label("Y", 146, 172, "font_montserrat_16")
        self.accel_z_title = self.make_label("Z", 274, 172, "font_montserrat_16")
        self.accel_x = self.make_label("", 38, 168, "font_montserrat_24")
        self.accel_y = self.make_label("", 166, 168, "font_montserrat_24")
        self.accel_z = self.make_label("", 294, 168, "font_montserrat_24")

        self.opt_rule = self.make_rule(8, 208, width - 16)
        self.opt_title = self.make_label("QWIIC OPT3001", 10, 220, "font_montserrat_16")
        self.opt_value = self.make_label("", 10, 242, "font_montserrat_24")
        self.opt_detail = self.make_label("", 94, 248, "font_montserrat_16")
        self.opt_bar = self.make_segment_bar(246, 246)
        self.opt_widgets = [
            self.opt_rule,
            self.opt_title,
            self.opt_value,
            self.opt_detail,
            self.opt_bar["container"],
        ]
        self.set_opt_visible(False)

    def make_label(self, text, x, y, font_name=None):
        label = lv.label(self.screen)
        label.set_text(text)
        label.set_pos(x, y)
        label.set_style_text_color(lv.color_black(), 0)
        if font_name:
            self.try_set_font(label, font_name)
        return label

    def make_rule(self, x, y, width):
        rule = lv.obj(self.screen)
        rule.set_pos(x, y)
        rule.set_size(width, 2)
        rule.set_style_bg_color(lv.color_black(), 0)
        rule.set_style_bg_opa(lv.OPA.COVER, 0)
        rule.set_style_border_width(0, 0)
        return rule

    def make_segment_bar(self, x, y):
        container = lv.obj(self.screen)
        container.set_pos(x, y)
        container.set_size(136, 16)
        container.set_style_bg_color(lv.color_white(), 0)
        container.set_style_bg_opa(lv.OPA.COVER, 0)
        container.set_style_border_color(lv.color_black(), 0)
        container.set_style_border_width(2, 0)
        container.set_style_radius(0, 0)
        container.set_style_pad_all(0, 0)

        segments = []
        for idx in range(BAR_SLOTS):
            seg = lv.obj(container)
            seg.set_pos(2 + (idx * 13), 2)
            seg.set_size(11, 10)
            seg.set_style_border_width(0, 0)
            seg.set_style_radius(0, 0)
            seg.set_style_bg_color(lv.color_white(), 0)
            seg.set_style_bg_opa(lv.OPA.COVER, 0)
            segments.append(seg)

        return {
            "container": container,
            "segments": segments,
        }

    def try_set_font(self, obj, font_name):
        try:
            obj.set_style_text_font(getattr(lv, font_name), 0)
        except Exception:
            pass

    def set_cached_text(self, key, label, text):
        if self.render_cache.get(key) == text:
            return
        label.set_text(text)
        self.render_cache[key] = text

    def set_opt_visible(self, visible):
        for widget in self.opt_widgets:
            if visible:
                widget.remove_flag(lv.obj.FLAG.HIDDEN)
            else:
                widget.add_flag(lv.obj.FLAG.HIDDEN)

    def refresh(self, _timer):
        if self.handle_input():
            return

        devices = self.list_iio_devices()
        self.ensure_runtime_tuning(devices)
        accel = self.read_accelerometer(devices)
        onboard_light = self.read_onboard_light(devices)
        opt_iio = self.read_opt3001_iio(devices)

        if opt_iio:
            self.last_probe = None
        elif (_now_ms() - self.last_scan_ms) >= SCAN_INTERVAL_MS:
            self.last_scan_ms = _now_ms()
            self.last_probe = self.scan_qwiic_opt3001()
            if self.last_probe and self.last_probe.get("detected"):
                self.try_bind_opt3001(self.last_probe["bus"], self.last_probe["address"])

        self.render_light(onboard_light)
        self.render_accel(accel)
        self.render_opt(opt_iio, self.last_probe)

    def ensure_runtime_tuning(self, devices):
        accel = self.find_accelerometer_device(devices)
        if accel:
            self.tune_accelerometer(accel["path"])

        opt = self.find_opt3001_device(devices)
        if opt:
            self.tune_opt3001(opt["path"])
        elif self.opt3001_path:
            self.restore_opt3001_tuning()

    def restore_runtime_tuning(self):
        self.restore_accelerometer_tuning()
        self.restore_opt3001_tuning()

    def tune_accelerometer(self, path):
        sampling_path = path + "/sampling_frequency"
        if not _path_exists(sampling_path):
            return

        if self.accel_path and self.accel_path != path:
            self.restore_accelerometer_tuning()

        if self.accel_original_sampling_frequency is None:
            self.accel_original_sampling_frequency = _read_text(sampling_path)
            self.accel_path = path

        current = _read_text(sampling_path)
        if current == ACCEL_TARGET_SAMPLING_FREQUENCY or current == (ACCEL_TARGET_SAMPLING_FREQUENCY + ".000000"):
            return

        _write_text(sampling_path, ACCEL_TARGET_SAMPLING_FREQUENCY + "\n")

    def restore_accelerometer_tuning(self):
        if not self.accel_path or self.accel_original_sampling_frequency is None:
            self.accel_path = None
            self.accel_original_sampling_frequency = None
            return

        sampling_path = self.accel_path + "/sampling_frequency"
        if _path_exists(sampling_path):
            _write_text(sampling_path, self.accel_original_sampling_frequency + "\n")

        self.accel_path = None
        self.accel_original_sampling_frequency = None

    def tune_opt3001(self, path):
        int_time_path = path + "/in_illuminance_integration_time"
        if not _path_exists(int_time_path):
            return

        if self.opt3001_path and self.opt3001_path != path:
            self.restore_opt3001_tuning()

        if self.opt3001_original_int_time is None:
            self.opt3001_original_int_time = _read_text(int_time_path)
            self.opt3001_path = path

        current = _read_text(int_time_path)
        if current == OPT3001_TARGET_INT_TIME or current == (OPT3001_TARGET_INT_TIME + "00000"):
            return

        _write_text(int_time_path, OPT3001_TARGET_INT_TIME + "\n")

    def restore_opt3001_tuning(self):
        if not self.opt3001_path or self.opt3001_original_int_time is None:
            self.opt3001_path = None
            self.opt3001_original_int_time = None
            return

        int_time_path = self.opt3001_path + "/in_illuminance_integration_time"
        if _path_exists(int_time_path):
            _write_text(int_time_path, self.opt3001_original_int_time + "\n")

        self.opt3001_path = None
        self.opt3001_original_int_time = None

    def find_accelerometer_device(self, devices):
        for device in devices:
            path = device["path"]
            if _path_exists(path + "/in_accel_x_raw") and _path_exists(path + "/in_accel_y_raw"):
                return device
        return None

    def find_opt3001_device(self, devices):
        for device in devices:
            path = device["path"]
            name_lower = device["name"].lower()
            if "opt3001" in name_lower:
                return device
            if _path_exists(path + "/in_illuminance_input") or _path_exists(path + "/in_illuminance_raw"):
                return device
        return None

    def handle_input(self):
        import input

        key = self.current_key
        state = self.key_state
        if state != lv.INDEV_STATE.PRESSED and input.driver:
            key = input.driver.last_key
            state = input.driver.state

        if state == lv.INDEV_STATE.PRESSED and self.prev_state == lv.INDEV_STATE.RELEASED:
            self.key_state = lv.INDEV_STATE.RELEASED
            backspace = getattr(lv.KEY, "BACKSPACE", -1)
            if key in (lv.KEY.ESC, lv.KEY.LEFT, backspace, ord("q")):
                self.exit()
                if self.on_exit_cb:
                    self.on_exit_cb()
                return True

        self.prev_state = state
        return False

    def render_light(self, light):
        if not light:
            self.set_cached_text("light_value", self.light_value, "not found")
            self.set_cached_text("light_detail", self.light_detail, "")
            self.set_bar_fill("light_bar_fill", self.light_bar, 0.0)
            return

        bar_fraction = _clamp(light["raw"] / ADC_BAR_MAX_RAW, 0.0, 1.0)
        percent = int(bar_fraction * 100)
        self.set_cached_text(
            "light_value",
            self.light_value,
            "{:3d}%".format(percent),
        )
        self.set_cached_text(
            "light_detail",
            self.light_detail,
            "raw {:4d}".format(light["raw"]),
        )
        self.set_bar_fill("light_bar_fill", self.light_bar, bar_fraction)

    def render_accel(self, accel):
        if not accel:
            self.set_cached_text("accel_x", self.accel_x, "--")
            self.set_cached_text("accel_y", self.accel_y, "--")
            self.set_cached_text("accel_z", self.accel_z, "--")
            return

        self.set_cached_text("accel_x", self.accel_x, "{:+.2f}".format(accel["axes_g"]["X"]))
        self.set_cached_text("accel_y", self.accel_y, "{:+.2f}".format(accel["axes_g"]["Y"]))
        self.set_cached_text("accel_z", self.accel_z, "{:+.2f}".format(accel["axes_g"]["Z"]))

    def render_opt(self, opt_iio, probe):
        if opt_iio:
            self.set_opt_visible(True)
            self.set_cached_text("opt_title", self.opt_title, "QWIIC OPT3001")
            if opt_iio["lux"] is not None:
                bar_fraction = self.opt_lux_fraction(opt_iio["lux"])
                percent = int(bar_fraction * 100)
                self.set_cached_text("opt_value", self.opt_value, "{:3d}%".format(percent))
                self.set_cached_text("opt_detail", self.opt_detail, "{:.1f} lux".format(opt_iio["lux"]))
                self.set_bar_fill("opt_bar_fill", self.opt_bar, bar_fraction)
            else:
                self.set_cached_text("opt_value", self.opt_value, "live")
                self.set_cached_text("opt_detail", self.opt_detail, "")
                self.set_bar_fill("opt_bar_fill", self.opt_bar, 0.0)
            return

        if probe and probe.get("detected"):
            self.set_opt_visible(True)
            self.set_cached_text("opt_title", self.opt_title, "QWIIC OPT3001")
            if self.opt3001_driver_available:
                self.set_cached_text("opt_value", self.opt_value, "detected")
                detail = "i2c-{} @ 0x{:02x}".format(probe["bus"], probe["address"])
            else:
                self.set_cached_text("opt_value", self.opt_value, "detected")
                detail = "i2c-{} @ 0x{:02x}".format(probe["bus"], probe["address"])
            self.set_cached_text("opt_detail", self.opt_detail, detail)
            self.set_bar_fill("opt_bar_fill", self.opt_bar, 0.0)
            return

        self.set_opt_visible(False)

    def set_bar_fill(self, key, bar, fraction):
        fraction = _clamp(fraction, 0.0, 1.0)
        filled = int((BAR_SLOTS * fraction) + 0.5)
        if self.render_cache.get(key) == filled:
            return
        for idx, seg in enumerate(bar["segments"]):
            color = lv.color_black() if idx < filled else lv.color_white()
            seg.set_style_bg_color(color, 0)
            try:
                lv.obj.invalidate(seg)
            except Exception:
                pass
        try:
            lv.obj.invalidate(bar["container"])
            lv.obj.invalidate(lv.scr_act())
            lv.refr_now(None)
        except Exception:
            pass
        self.render_cache[key] = filled

    def opt_lux_fraction(self, lux):
        lux = _clamp(lux, 0.0, OPT3001_BAR_MAX_LUX)
        if lux <= 0.0:
            return 0.0
        return math.log10(lux + 1.0) / math.log10(OPT3001_BAR_MAX_LUX + 1.0)

    def list_iio_devices(self):
        devices = []
        try:
            entries = os.listdir(IIO_ROOT)
        except OSError:
            return devices

        for entry in entries:
            if not entry.startswith("iio:device"):
                continue
            path = "{}/{}".format(IIO_ROOT, entry)
            name = _read_text(path + "/name")
            devices.append(
                {
                    "entry": entry,
                    "path": path,
                    "name": name or entry,
                }
            )

        devices.sort(key=lambda item: item["entry"])
        return devices

    def read_accelerometer(self, devices):
        for device in devices:
            path = device["path"]
            x_raw = _read_int(path + "/in_accel_x_raw")
            y_raw = _read_int(path + "/in_accel_y_raw")
            z_raw = _read_int(path + "/in_accel_z_raw")
            if x_raw is None or y_raw is None or z_raw is None:
                continue

            scale = _read_float(path + "/in_accel_scale")
            if scale is None:
                scale = 1.0

            axes_g = {
                "X": x_raw * scale,
                "Y": y_raw * scale,
                "Z": z_raw * scale,
            }

            return {
                "name": device["name"],
                "path": path,
                "scale": scale,
                "axes_g": axes_g,
                "magnitude_g": math.sqrt(
                    (axes_g["X"] * axes_g["X"]) +
                    (axes_g["Y"] * axes_g["Y"]) +
                    (axes_g["Z"] * axes_g["Z"])
                ),
            }

        return None

    def read_onboard_light(self, devices):
        channel_suffix = "/in_voltage{}_raw".format(ADC_LIGHT_CHANNEL)
        for device in devices:
            raw = _read_int(device["path"] + channel_suffix)
            if raw is None:
                continue

            scale = _read_float(device["path"] + "/in_voltage_scale")
            millivolts = None
            if scale is not None:
                millivolts = raw * scale

            return {
                "name": device["name"],
                "path": device["path"],
                "raw": raw,
                "scale": scale,
                "millivolts": millivolts,
            }

        return None

    def read_opt3001_iio(self, devices):
        device = self.find_opt3001_device(devices)
        if not device:
            return None

        path = device["path"]
        lux = _read_float(path + "/in_illuminance_input")
        raw = _read_float(path + "/in_illuminance_raw")
        scale = _read_float(path + "/in_illuminance_scale")
        if lux is None and raw is not None and scale is not None:
            lux = raw * scale

        return {
            "name": device["name"],
            "path": path,
            "lux": lux,
            "raw": raw,
            "scale": scale,
        }

    def scan_qwiic_opt3001(self):
        for bus in QWIIC_BUSES:
            if not _path_exists("/dev/i2c-{}".format(bus)):
                continue
            found = self.scan_i2c_bus(bus)
            for address in OPT3001_ADDRESSES:
                if address in found:
                    return {
                        "detected": True,
                        "bus": bus,
                        "address": address,
                    }

        return None

    def scan_i2c_bus(self, bus):
        output_path = "/tmp/iio_sensor_scan_{}.txt".format(bus)
        os.system("i2cdetect -y -r {} > {} 2>/dev/null".format(bus, output_path))

        found = []
        try:
            with open(output_path, "r") as handle:
                lines = handle.readlines()
        except OSError:
            return found

        for line in lines:
            parts = line.strip().split()
            if not parts:
                continue
            if not parts[0].endswith(":"):
                continue
            try:
                row = int(parts[0][:-1], 16)
            except ValueError:
                continue

            offset = 8 if row == 0 else 0
            for index, cell in enumerate(parts[1:]):
                if cell in ("--", "UU"):
                    continue
                try:
                    found.append(row + offset + index)
                except Exception:
                    pass

        return found

    def try_bind_opt3001(self, bus, address):
        if not self.opt3001_driver_available:
            return

        device_dir = "/sys/bus/i2c/devices/{}-00{:02x}".format(bus, address)
        if _path_exists(device_dir):
            return

        new_device_path = "/sys/bus/i2c/devices/i2c-{}/new_device".format(bus)
        _write_text(new_device_path, "opt3001 0x{:02x}\n".format(address))
