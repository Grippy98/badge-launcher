"""Dependency-free framing for the BadgeBeam Bluetooth receiver."""

from __future__ import annotations


class FrameAccumulator:
    """Accumulate arbitrary chunks into exact, consecutive frames."""

    def __init__(self, frame_bytes: int) -> None:
        if frame_bytes <= 0:
            raise ValueError("frame_bytes must be positive")
        self.frame_bytes = frame_bytes
        self.buffer = bytearray()

    def push(self, chunk: bytes) -> list[bytes]:
        self.buffer.extend(chunk)
        frames: list[bytes] = []
        while len(self.buffer) >= self.frame_bytes:
            frames.append(bytes(self.buffer[: self.frame_bytes]))
            del self.buffer[: self.frame_bytes]
        return frames


__all__ = ["FrameAccumulator"]
