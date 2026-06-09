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
ACCEL_FULL_SCALE_G = 2.0
REFRESH_MS = 900
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

        self.light_title = self.make_label("ON-BOARD LIGHT", 10, 46, "font_montserrat_16")
        self.light_value = self.make_label("--", 10, 68, "font_montserrat_24")
        self.light_detail = self.make_label("", 10, 96, "font_montserrat_14")
        self.light_bar_bg = self.make_bar(220, 74, 160, 14)
        self.light_bar_fill = self.make_bar_fill(self.light_bar_bg)

        self.rule_mid = self.make_rule(8, 122, width - 16)

        self.accel_title = self.make_label("ON-BOARD ACCEL", 10, 132, "font_montserrat_16")
        self.accel_name = self.make_label("", 10, 154, "font_montserrat_14")
        self.accel_x = self.make_label("", 10, 176, "font_montserrat_16")
        self.accel_y = self.make_label("", 10, 198, "font_montserrat_16")
        self.accel_z = self.make_label("", 10, 220, "font_montserrat_16")
        self.accel_mag = self.make_label("", 10, 240, "font_montserrat_14")

        self.opt_rule = self.make_rule(8, 258, width - 16)
        self.opt_title = self.make_label("QWIIC OPT3001", 10, 266, "font_montserrat_16")
        self.opt_value = self.make_label("", 10, 286, "font_montserrat_14")
        self.opt_widgets = [
            self.opt_rule,
            self.opt_title,
            self.opt_value,
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

    def make_bar(self, x, y, width, height):
        bar = lv.obj(self.screen)
        bar.set_pos(x, y)
        bar.set_size(width, height)
        bar.set_style_bg_color(lv.color_white(), 0)
        bar.set_style_bg_opa(lv.OPA.COVER, 0)
        bar.set_style_border_color(lv.color_black(), 0)
        bar.set_style_border_width(2, 0)
        bar.set_style_radius(0, 0)
        return bar

    def make_bar_fill(self, parent):
        fill = lv.obj(parent)
        fill.set_pos(0, 0)
        fill.set_size(0, 10)
        fill.set_style_bg_color(lv.color_black(), 0)
        fill.set_style_bg_opa(lv.OPA.COVER, 0)
        fill.set_style_border_width(0, 0)
        fill.set_style_radius(0, 0)
        return fill

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
            self.set_cached_text("light_detail", self.light_detail, "ADC channel 2 unavailable")
            self.set_bar_fill(0.0)
            return

        percent = int((light["raw"] / ADC_MAX_RAW) * 100)
        mv_text = ""
        if light["millivolts"] is not None:
            mv_text = "  {:.0f} mV".format(light["millivolts"])

        self.set_cached_text(
            "light_value",
            self.light_value,
            "raw {:4d}   {:3d}%".format(light["raw"], percent),
        )
        self.set_cached_text(
            "light_detail",
            self.light_detail,
            "{} / in_voltage{}_raw{}".format(light["name"], ADC_LIGHT_CHANNEL, mv_text),
        )
        self.set_bar_fill(light["raw"] / ADC_MAX_RAW)

    def render_accel(self, accel):
        if not accel:
            self.set_cached_text("accel_name", self.accel_name, "accelerometer not found")
            self.set_cached_text("accel_x", self.accel_x, "")
            self.set_cached_text("accel_y", self.accel_y, "")
            self.set_cached_text("accel_z", self.accel_z, "")
            self.set_cached_text("accel_mag", self.accel_mag, "")
            return

        self.set_cached_text("accel_name", self.accel_name, accel["name"])
        self.set_cached_text("accel_x", self.accel_x, "X  {:+.2f} g".format(accel["axes_g"]["X"]))
        self.set_cached_text("accel_y", self.accel_y, "Y  {:+.2f} g".format(accel["axes_g"]["Y"]))
        self.set_cached_text("accel_z", self.accel_z, "Z  {:+.2f} g".format(accel["axes_g"]["Z"]))
        self.set_cached_text(
            "accel_mag",
            self.accel_mag,
            "|g| {:.2f}   scale {:.6f}".format(accel["magnitude_g"], accel["scale"]),
        )

    def render_opt(self, opt_iio, probe):
        if opt_iio:
            self.set_opt_visible(True)
            self.set_cached_text("opt_title", self.opt_title, "QWIIC OPT3001")
            if opt_iio["lux"] is not None:
                self.set_cached_text("opt_value", self.opt_value, "{:.2f} lux via IIO".format(opt_iio["lux"]))
            else:
                self.set_cached_text("opt_value", self.opt_value, "{} present via IIO".format(opt_iio["name"]))
            return

        if probe and probe.get("detected"):
            self.set_opt_visible(True)
            self.set_cached_text("opt_title", self.opt_title, "QWIIC OPT3001 ON i2c-{}".format(probe["bus"]))
            if self.opt3001_driver_available:
                detail = "Detected at 0x{:02x}; waiting for IIO node".format(probe["address"])
            else:
                detail = "Detected at 0x{:02x}; kernel has no IIO driver".format(probe["address"])
            self.set_cached_text("opt_value", self.opt_value, detail)
            return

        self.set_opt_visible(False)

    def set_bar_fill(self, fraction):
        fraction = _clamp(fraction, 0.0, 1.0)
        bar_width = 156
        fill_width = int(bar_width * fraction)
        if self.render_cache.get("light_bar_fill") == fill_width:
            return
        self.light_bar_fill.set_size(fill_width, 10)
        self.render_cache["light_bar_fill"] = fill_width

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
        for device in devices:
            path = device["path"]
            name_lower = device["name"].lower()
            has_opt_name = "opt3001" in name_lower
            has_illuminance = (
                _read_text(path + "/in_illuminance_input") is not None or
                _read_text(path + "/in_illuminance_raw") is not None
            )
            if not has_opt_name and not has_illuminance:
                continue

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

        return None

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
