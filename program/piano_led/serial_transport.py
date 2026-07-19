"""Low-latency USB serial transport for a directly connected ESP32."""

from __future__ import annotations

from collections.abc import Sequence

FRAME_START = 0xA5
CMD_SET_RANGES = 0x21
CMD_SET_BRIGHTNESS = 0x22
CMD_CLEAR = 0x23
CMD_SET_LED_COUNT = 0x25
CMD_START_CENTER_WAVE = 0x26
CMD_START_NOTE_WAVE = 0x27
CMD_START_NOTE_FADE = 0x28
CMD_START_SWEEP = 0x29
CMD_START_RAINBOW = 0x2A
CMD_STOP_ANIMATION = 0x2B
MAX_RANGES_PER_PACKET = 50


def make_frame(command: int, payload: bytes = b"") -> bytes:
    if len(payload) > 250:
        raise ValueError("serial payload is too large")
    checksum = (command + len(payload) + sum(payload)) & 0xFF
    return bytes((FRAME_START, command, len(payload))) + payload + bytes((checksum,))


class SerialLedClient:
    """USB serial transport for the ESP32 controller."""

    requires_state_resync = False

    @staticmethod
    def _to_strip_rgb(red: int, green: int, blue: int) -> tuple[int, int, int]:
        return red, green, blue

    def __init__(self, port: str, baudrate: int = 921600, color_order: str = "BRG") -> None:
        try:
            import serial
        except ImportError as error:
            raise RuntimeError("Falta pyserial. Ejecuta: python -m pip install -e .") from error
        self._serial = serial.Serial(port, baudrate=baudrate, timeout=0, write_timeout=0.2)
        self.set_color_order(color_order)

    def set_color_order(self, color_order: str) -> None:
        if color_order not in {"RGB", "RBG", "GRB", "GBR", "BRG", "BGR"}:
            raise ValueError("orden de color no válido")
        self.color_order = color_order

    def _to_strip_color(self, red: int, green: int, blue: int) -> tuple[int, int, int]:
        channels = {"R": red, "G": green, "B": blue}
        return tuple(channels[channel] for channel in self.color_order)  # type: ignore[return-value]

    @staticmethod
    def available_ports() -> list[str]:
        try:
            from serial.tools import list_ports
        except ImportError as error:
            raise RuntimeError("Falta pyserial. Ejecuta: python -m pip install -e .") from error
        return [f"{port.device} — {port.description}" for port in list_ports.comports()]

    @staticmethod
    def port_name(label: str) -> str:
        return label.split(" — ", 1)[0]

    def _write(self, command: int, payload: bytes = b"") -> None:
        self._serial.write(make_frame(command, payload))

    def info(self) -> None:
        """Kept for compatibility with MidiLedAgent; serial needs no handshake."""

    def set_ranges_realtime(self, ranges: Sequence[tuple[int, int, int, int, int]]) -> None:
        for offset in range(0, len(ranges), MAX_RANGES_PER_PACKET):
            payload = bytearray()
            for start, count, red, green, blue in ranges[offset:offset + MAX_RANGES_PER_PACKET]:
                payload.extend((start, count, *self._to_strip_color(red, green, blue)))
            self._write(CMD_SET_RANGES, bytes(payload))

    def set_frame_realtime(self, pixels: Sequence[tuple[int, int, int]]) -> None:
        ranges: list[tuple[int, int, int, int, int]] = []
        start = 0
        while start < len(pixels):
            color = pixels[start]
            end = start + 1
            while end < len(pixels) and pixels[end] == color and end - start < 255:
                end += 1
            ranges.append((start, end - start, *color))
            start = end
        self.set_ranges_realtime(ranges)

    def set_brightness(self, brightness: int) -> None:
        self._write(CMD_SET_BRIGHTNESS, bytes((brightness,)))

    def clear(self) -> None:
        self._write(CMD_CLEAR)

    def show_range(self, start: int, count: int, red: int, green: int, blue: int) -> None:
        self.clear()
        self.set_ranges_realtime(((start, count, red, green, blue),))

    def fill(self, red: int, green: int, blue: int) -> None:
        self.set_ranges_realtime(((0, 255, red, green, blue),))

    def start_sweep(self, red: int, green: int, blue: int, interval_ms: int) -> None:
        self._write(CMD_START_SWEEP, bytes((*self._to_strip_color(red, green, blue), interval_ms >> 8, interval_ms & 0xFF)))

    def start_rainbow(self, interval_ms: int) -> None:
        self._write(CMD_START_RAINBOW, bytes((interval_ms >> 8, interval_ms & 0xFF)))

    def stop_animation(self) -> None:
        self._write(CMD_STOP_ANIMATION)

    def set_led_count(self, count: int) -> None:
        if not 1 <= count <= 255:
            raise ValueError("el modo USB serie admite entre 1 y 255 LEDs")
        self._write(CMD_SET_LED_COUNT, bytes((count,)))

    def start_center_wave(self, interval_ms: int = 12) -> None:
        self._write(CMD_START_CENTER_WAVE, bytes((interval_ms >> 8, interval_ms & 0xFF)))

    def start_note_wave(self, start: int, red: int, green: int, blue: int, interval_ms: int | None = None) -> None:
        payload = bytes((start, *self._to_strip_color(red, green, blue)))
        if interval_ms is not None:
            payload += bytes((interval_ms >> 8, interval_ms & 0xFF))
        self._write(CMD_START_NOTE_WAVE, payload)

    def start_note_fade(self, start: int, count: int, red: int, green: int, blue: int, duration_ms: int) -> None:
        self._write(CMD_START_NOTE_FADE, bytes((start, count, *self._to_strip_color(red, green, blue), duration_ms >> 8, duration_ms & 0xFF)))

    def close(self) -> None:
        self._serial.close()
