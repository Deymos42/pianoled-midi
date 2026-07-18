"""Binary wire protocol shared by the Python app and ESP32 firmware."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum


class Command(IntEnum):
    SET_LED = 0x01
    CLEAR = 0x02
    FILL = 0x03
    PING = 0x04
    PONG = 0x05
    INFO = 0x06
    INFO_RESPONSE = 0x07
    SET_RANGE = 0x08
    SET_FRAME = 0x09
    SHOW_RANGE = 0x0A
    START_SWEEP = 0x0B
    STOP_ANIMATION = 0x0C
    START_RAINBOW = 0x0D
    SET_BRIGHTNESS = 0x0E
    ACK = 0x0F
    BEGIN_REALTIME_SESSION = 0x10
    SHOW_RANGE_REALTIME = 0x11
    SET_FRAME_REALTIME = 0x12
    SET_RANGES_REALTIME = 0x13
    SET_LED_COUNT = 0x14
    START_CENTER_WAVE = 0x15
    START_NOTE_WAVE = 0x16


@dataclass(frozen=True)
class DeviceInfo:
    firmware_version: int
    led_count: int
    brightness: int
    hostname: str


def _byte(value: int, name: str) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"{name} must be between 0 and 255")
    return value


def set_led(index: int, red: int, green: int, blue: int) -> bytes:
    return bytes((Command.SET_LED, _byte(index, "index"), _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue")))


def set_range(start: int, count: int, red: int, green: int, blue: int) -> bytes:
    if count == 0:
        raise ValueError("count must be at least 1")
    return bytes((Command.SET_RANGE, _byte(start, "start"), _byte(count, "count"), _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue")))


def show_range(start: int, count: int, red: int, green: int, blue: int) -> bytes:
    if count == 0:
        raise ValueError("count must be at least 1")
    return bytes((Command.SHOW_RANGE, _byte(start, "start"), _byte(count, "count"), _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue")))


def start_sweep(red: int, green: int, blue: int, interval_ms: int) -> bytes:
    if not 15 <= interval_ms <= 65535:
        raise ValueError("interval_ms must be between 15 and 65535")
    return bytes((Command.START_SWEEP, _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue"), interval_ms >> 8, interval_ms & 0xFF))


def stop_animation() -> bytes:
    return bytes((Command.STOP_ANIMATION,))


def start_rainbow(interval_ms: int) -> bytes:
    if not 8 <= interval_ms <= 65535:
        raise ValueError("interval_ms must be between 8 and 65535")
    return bytes((Command.START_RAINBOW, interval_ms >> 8, interval_ms & 0xFF))


def set_brightness(brightness: int) -> bytes:
    return bytes((Command.SET_BRIGHTNESS, _byte(brightness, "brightness")))


def set_led_count(count: int) -> bytes:
    if not 1 <= count <= 255:
        raise ValueError("count must be between 1 and 255")
    return bytes((Command.SET_LED_COUNT, count))


def start_center_wave(interval_ms: int) -> bytes:
    if not 8 <= interval_ms <= 65535:
        raise ValueError("interval_ms must be between 8 and 65535")
    return bytes((Command.START_CENTER_WAVE, interval_ms >> 8, interval_ms & 0xFF))


def start_note_wave(start: int, red: int, green: int, blue: int) -> bytes:
    return bytes((Command.START_NOTE_WAVE, _byte(start, "start"), _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue")))


def begin_realtime_session(session: int) -> bytes:
    if not 1 <= session <= 65535:
        raise ValueError("session must be between 1 and 65535")
    return bytes((Command.BEGIN_REALTIME_SESSION, session >> 8, session & 0xFF))


def show_range_realtime(session: int, sequence: int, start: int, count: int, red: int, green: int, blue: int) -> bytes:
    if not 1 <= session <= 65535:
        raise ValueError("session must be between 1 and 65535")
    if not 0 <= sequence <= 65535:
        raise ValueError("sequence must be between 0 and 65535")
    if count == 0:
        raise ValueError("count must be at least 1")
    return bytes((Command.SHOW_RANGE_REALTIME, session >> 8, session & 0xFF, sequence >> 8, sequence & 0xFF, _byte(start, "start"), _byte(count, "count"), _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue")))


def set_frame_realtime(session: int, sequence: int, pixels: Sequence[tuple[int, int, int]]) -> bytes:
    if not 1 <= session <= 65535:
        raise ValueError("session must be between 1 and 65535")
    if not 0 <= sequence <= 65535:
        raise ValueError("sequence must be between 0 and 65535")
    packet = bytearray((Command.SET_FRAME_REALTIME, session >> 8, session & 0xFF, sequence >> 8, sequence & 0xFF))
    for index, (red, green, blue) in enumerate(pixels):
        packet.extend((_byte(red, f"pixels[{index}].red"), _byte(green, f"pixels[{index}].green"), _byte(blue, f"pixels[{index}].blue")))
    return bytes(packet)


def set_ranges_realtime(session: int, sequence: int, ranges: Sequence[tuple[int, int, int, int, int]]) -> bytes:
    if not 1 <= session <= 65535:
        raise ValueError("session must be between 1 and 65535")
    if not 0 <= sequence <= 65535:
        raise ValueError("sequence must be between 0 and 65535")
    if not ranges:
        raise ValueError("at least one range is required")
    packet = bytearray((Command.SET_RANGES_REALTIME, session >> 8, session & 0xFF, sequence >> 8, sequence & 0xFF))
    for index, (start, count, red, green, blue) in enumerate(ranges):
        if count == 0:
            raise ValueError(f"ranges[{index}].count must be at least 1")
        packet.extend((_byte(start, f"ranges[{index}].start"), _byte(count, f"ranges[{index}].count"), _byte(red, f"ranges[{index}].red"), _byte(green, f"ranges[{index}].green"), _byte(blue, f"ranges[{index}].blue")))
    return bytes(packet)


def set_frame(pixels: Sequence[tuple[int, int, int]]) -> bytes:
    if not pixels:
        raise ValueError("a frame must contain at least one pixel")
    packet = bytearray((Command.SET_FRAME,))
    for index, (red, green, blue) in enumerate(pixels):
        packet.extend((_byte(red, f"pixels[{index}].red"), _byte(green, f"pixels[{index}].green"), _byte(blue, f"pixels[{index}].blue")))
    return bytes(packet)


def clear() -> bytes:
    return bytes((Command.CLEAR,))


def fill(red: int, green: int, blue: int) -> bytes:
    return bytes((Command.FILL, _byte(red, "red"), _byte(green, "green"), _byte(blue, "blue")))


def ping() -> bytes:
    return bytes((Command.PING,))


def info() -> bytes:
    return bytes((Command.INFO,))


def parse_info(packet: bytes) -> DeviceInfo:
    if len(packet) < 5 or packet[0] != Command.INFO_RESPONSE:
        raise ValueError("invalid INFO response")
    return DeviceInfo(packet[1], (packet[2] << 8) | packet[3], packet[4], packet[5:].decode("utf-8", errors="strict"))
