"""Linux framebuffer output with stride and bit-depth handling.

The badge kernel owns the SSD16xx/e-paper refresh policy.  This backend writes a
canonical Pillow grayscale frame to the framebuffer without assuming that it is
32 bpp.  Driver-specific waveform/partial-refresh hooks can be added behind this
same interface after their ABI is known.
"""

from __future__ import annotations

import ctypes
import fcntl
import mmap
import os
from pathlib import Path
import time
from typing import Iterable

from badge_sdk import InputEvent, RefreshMode


FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602


class _Bitfield(ctypes.Structure):
    _fields_ = [
        ("offset", ctypes.c_uint32),
        ("length", ctypes.c_uint32),
        ("msb_right", ctypes.c_uint32),
    ]


class _VariableInfo(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_uint32),
        ("yres", ctypes.c_uint32),
        ("xres_virtual", ctypes.c_uint32),
        ("yres_virtual", ctypes.c_uint32),
        ("xoffset", ctypes.c_uint32),
        ("yoffset", ctypes.c_uint32),
        ("bits_per_pixel", ctypes.c_uint32),
        ("grayscale", ctypes.c_uint32),
        ("red", _Bitfield),
        ("green", _Bitfield),
        ("blue", _Bitfield),
        ("transp", _Bitfield),
        ("nonstd", ctypes.c_uint32),
        ("activate", ctypes.c_uint32),
        ("height_mm", ctypes.c_uint32),
        ("width_mm", ctypes.c_uint32),
        ("accel_flags", ctypes.c_uint32),
        ("pixclock", ctypes.c_uint32),
        ("left_margin", ctypes.c_uint32),
        ("right_margin", ctypes.c_uint32),
        ("upper_margin", ctypes.c_uint32),
        ("lower_margin", ctypes.c_uint32),
        ("hsync_len", ctypes.c_uint32),
        ("vsync_len", ctypes.c_uint32),
        ("sync", ctypes.c_uint32),
        ("vmode", ctypes.c_uint32),
        ("rotate", ctypes.c_uint32),
        ("colorspace", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]


class _FixedInfo(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char * 16),
        ("smem_start", ctypes.c_ulong),
        ("smem_len", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("type_aux", ctypes.c_uint32),
        ("visual", ctypes.c_uint32),
        ("xpanstep", ctypes.c_uint16),
        ("ypanstep", ctypes.c_uint16),
        ("ywrapstep", ctypes.c_uint16),
        ("line_length", ctypes.c_uint32),
        ("mmio_start", ctypes.c_ulong),
        ("mmio_len", ctypes.c_uint32),
        ("accel", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint16),
        ("reserved", ctypes.c_uint16 * 2),
    ]


def _ioctl_struct(fd: int, request: int, structure):
    buffer = bytearray(ctypes.sizeof(structure))
    fcntl.ioctl(fd, request, buffer, True)
    return structure.from_buffer_copy(buffer)


def _read_int(path: Path, default: int) -> int:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return default


class FramebufferBackend:
    def __init__(self, device: str = "/dev/fb0", width: int | None = None, height: int | None = None) -> None:
        self.device = device
        self.fd = os.open(device, os.O_RDWR)
        variable = None
        fixed = None
        try:
            variable = _ioctl_struct(self.fd, FBIOGET_VSCREENINFO, _VariableInfo)
            fixed = _ioctl_struct(self.fd, FBIOGET_FSCREENINFO, _FixedInfo)
        except OSError:
            # Minimal framebuffer drivers do not always expose every ioctl;
            # retain the sysfs fallback used by early BeagleBadge images.
            pass
        fb_name = Path(device).name
        sysfs = Path("/sys/class/graphics") / fb_name
        virtual = ""
        try:
            virtual = (sysfs / "virtual_size").read_text().strip()
        except OSError:
            pass
        detected_width, detected_height = 400, 300
        if "," in virtual:
            try:
                detected_width, detected_height = (int(part) for part in virtual.split(",", 1))
            except ValueError:
                pass
        ioctl_width = int(variable.xres) if variable and variable.xres else detected_width
        ioctl_height = int(variable.yres) if variable and variable.yres else detected_height
        self.width = width or ioctl_width
        self.height = height or ioctl_height
        ioctl_bpp = int(variable.bits_per_pixel) if variable and variable.bits_per_pixel else 0
        self.bits_per_pixel = ioctl_bpp or _read_int(sysfs / "bits_per_pixel", 32)
        bytes_per_line = max(1, (self.width * self.bits_per_pixel + 7) // 8)
        ioctl_stride = int(fixed.line_length) if fixed and fixed.line_length else 0
        self.stride = ioctl_stride or _read_int(sysfs / "stride", bytes_per_line)
        self.stride = max(self.stride, bytes_per_line)
        self.variable_info = variable
        self.fixed_info = fixed
        self.invert = os.environ.get("BADGE_FB_INVERT", "0").lower() in {"1", "true", "yes"}
        self.full_refresh_cycle = os.environ.get("BADGE_FULL_REFRESH_CYCLE", "1").lower() in {"1", "true", "yes"}
        required_size = self.stride * self.height
        reported_size = int(fixed.smem_len) if fixed and fixed.smem_len else 0
        if reported_size and reported_size < required_size:
            os.close(self.fd)
            raise RuntimeError(
                f"framebuffer memory ({reported_size} bytes) is smaller than "
                f"the requested {self.width}x{self.height} frame ({required_size} bytes)"
            )
        self.map_size = reported_size or required_size
        try:
            self.memory = mmap.mmap(
                self.fd,
                self.map_size,
                mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE,
            )
        except Exception:
            os.close(self.fd)
            raise

    def poll(self) -> list[InputEvent]:
        return []

    def present(self, image, refresh: RefreshMode = RefreshMode.AUTO, damage=None) -> None:
        from PIL import Image, ImageOps

        frame = image.convert("L").resize((self.width, self.height))
        if self.invert:
            frame = ImageOps.invert(frame)
        if refresh == RefreshMode.FULL and self.full_refresh_cycle:
            self._write_frame(Image.new("L", (self.width, self.height), 0))
            time.sleep(0.3)
            self._write_frame(Image.new("L", (self.width, self.height), 255))
            time.sleep(0.3)
        self._write_frame(frame)

    def _write_frame(self, frame) -> None:
        packed = self._pack(frame)
        self.memory.seek(0)
        self.memory.write(packed)
        self.memory.flush()

    def _rows(self, raw: bytes, raw_stride: int) -> bytes:
        if raw_stride == self.stride:
            return raw
        output = bytearray(self.stride * self.height)
        for row in range(self.height):
            source = row * raw_stride
            target = row * self.stride
            output[target : target + raw_stride] = raw[source : source + raw_stride]
        return bytes(output)

    def _pack(self, frame) -> bytes:
        bpp = self.bits_per_pixel
        if bpp == 1:
            mono = frame.convert("1", dither=0)
            raw_stride = (self.width + 7) // 8
            return self._rows(mono.tobytes(), raw_stride)
        if bpp == 8:
            return self._rows(frame.tobytes(), self.width)

        pixels: Iterable[int] = (
            frame.get_flattened_data() if hasattr(frame, "get_flattened_data") else frame.getdata()
        )
        if bpp == 16:
            raw = bytearray(self.width * self.height * 2)
            offset = 0
            for value in pixels:
                rgb565 = ((value >> 3) << 11) | ((value >> 2) << 5) | (value >> 3)
                raw[offset] = rgb565 & 0xFF
                raw[offset + 1] = rgb565 >> 8
                offset += 2
            return self._rows(bytes(raw), self.width * 2)
        if bpp == 24:
            raw = bytearray(self.width * self.height * 3)
            offset = 0
            for value in pixels:
                raw[offset : offset + 3] = bytes((value, value, value))
                offset += 3
            return self._rows(bytes(raw), self.width * 3)
        if bpp == 32:
            raw = bytearray(self.width * self.height * 4)
            offset = 0
            for value in pixels:
                raw[offset : offset + 4] = bytes((value, value, value, 0xFF))
                offset += 4
            return self._rows(bytes(raw), self.width * 4)
        raise RuntimeError(f"Unsupported framebuffer depth: {bpp} bpp")

    def close(self) -> None:
        try:
            self.memory.close()
        finally:
            os.close(self.fd)
