"""UDP client for a single PianoLED ESP32 device."""

from __future__ import annotations

import socket
import secrets
import threading
from collections.abc import Sequence
from . import protocol

DeviceInfo = protocol.DeviceInfo


class Esp32Client:
    requires_state_resync = True

    def __init__(self, host: str, port: int = 4210, timeout: float = 0.5) -> None:
        self.address = (host, port)
        self.timeout = timeout
        self._realtime_session = secrets.randbelow(65535) + 1
        self._realtime_sequence = 0
        self._realtime_session_started = False
        self._realtime_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._realtime_lock = threading.Lock()

    def _send(self, packet: bytes) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(packet, self.address)

    def _send_realtime_range(self, packet: bytes) -> None:
        """Duplicate immediately; firmware keeps only the newest sequence."""
        with self._realtime_lock:
            if not self._realtime_session_started:
                session = protocol.begin_realtime_session(self._realtime_session)
                self._realtime_socket.sendto(session, self.address)
                self._realtime_socket.sendto(session, self.address)
                self._realtime_session_started = True
            self._realtime_socket.sendto(packet, self.address)
            self._realtime_socket.sendto(packet, self.address)

    def _next_realtime_sequence(self) -> int:
        self._realtime_sequence = (self._realtime_sequence + 1) & 0xFFFF
        return self._realtime_sequence

    def _request(self, packet: bytes) -> bytes:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(packet, self.address)
            response, _ = sock.recvfrom(64)
            return response

    def _send_with_ack(self, packet: bytes, command: protocol.Command, attempts: int = 3) -> None:
        expected = bytes((protocol.Command.ACK, command))
        for _ in range(attempts):
            try:
                if self._request(packet) == expected:
                    return
            except socket.timeout:
                continue
        raise TimeoutError(f"no acknowledgement for {command.name} after {attempts} attempts")

    def set_led(self, index: int, red: int, green: int, blue: int) -> None:
        self._send(protocol.set_led(index, red, green, blue))

    def set_range(self, start: int, count: int, red: int, green: int, blue: int) -> None:
        self._send(protocol.set_range(start, count, red, green, blue))

    def show_range(self, start: int, count: int, red: int, green: int, blue: int) -> None:
        packet = protocol.show_range_realtime(self._realtime_session, self._next_realtime_sequence(), start, count, red, green, blue)
        self._send_realtime_range(packet)

    def set_frame_realtime(self, pixels: Sequence[tuple[int, int, int]]) -> None:
        packet = protocol.set_frame_realtime(self._realtime_session, self._next_realtime_sequence(), pixels)
        self._send_realtime_range(packet)

    def set_ranges_realtime(self, ranges: Sequence[tuple[int, int, int, int, int]]) -> None:
        packet = protocol.set_ranges_realtime(self._realtime_session, self._next_realtime_sequence(), ranges)
        self._send_realtime_range(packet)

    def start_sweep(self, red: int, green: int, blue: int, interval_ms: int) -> None:
        self._send(protocol.start_sweep(red, green, blue, interval_ms))

    def stop_animation(self) -> None:
        self._send(protocol.stop_animation())

    def start_rainbow(self, interval_ms: int) -> None:
        self._send(protocol.start_rainbow(interval_ms))

    def set_brightness(self, brightness: int) -> None:
        self._send(protocol.set_brightness(brightness))

    def set_led_count(self, count: int) -> None:
        self._send(protocol.set_led_count(count))

    def start_center_wave(self, interval_ms: int = 12) -> None:
        self._send(protocol.start_center_wave(interval_ms))

    def start_note_wave(self, start: int, red: int, green: int, blue: int, interval_ms: int | None = None) -> None:
        self._send(protocol.start_note_wave(start, red, green, blue, interval_ms))

    def start_note_fade(self, start: int, count: int, red: int, green: int, blue: int, duration_ms: int) -> None:
        self._send(protocol.start_note_fade(start, count, red, green, blue, duration_ms))

    def set_frame(self, pixels: Sequence[tuple[int, int, int]]) -> None:
        self._send(protocol.set_frame(pixels))

    def clear(self) -> None:
        self._send(protocol.clear())

    def fill(self, red: int, green: int, blue: int) -> None:
        self._send(protocol.fill(red, green, blue))

    def ping(self) -> bool:
        return self._request(protocol.ping()) == bytes((protocol.Command.PONG,))

    def info(self) -> DeviceInfo:
        device = protocol.parse_info(self._request(protocol.info()))
        if not self._realtime_session_started:
            self._send(protocol.begin_realtime_session(self._realtime_session))
            self._realtime_session_started = True
        return device

    def close(self) -> None:
        self._realtime_socket.close()
