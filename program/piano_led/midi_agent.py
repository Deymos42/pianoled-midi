"""Low-latency MIDI-to-PianoLED agent, intended to run beside the USB piano."""

from __future__ import annotations

import argparse
import threading
import time
import colorsys
from collections.abc import Iterable
from typing import Any

from .key_mapping import KEY_RANGES, KeyRange
from .serial_transport import SerialLedClient

FIRST_MIDI_NOTE = 21  # A0
LAST_MIDI_NOTE = 108  # C8
LED_COUNT = 198
CHORD_COALESCE_SECONDS = 0.001
STATE_RESYNC_SECONDS = 0.025


def parse_color(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError("el color debe tener formato RRGGBB, por ejemplo FFFFFF")
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as error:
        raise argparse.ArgumentTypeError("el color debe ser hexadecimal") from error


class MidiLedState:
    """Keeps a complete LED frame so chords and sustain remain coherent."""

    def __init__(self, color: tuple[int, int, int], velocity_sensitive: bool = False, key_ranges: tuple[KeyRange, ...] = KEY_RANGES) -> None:
        self.color = color
        self.velocity_sensitive = velocity_sensitive
        self.sustain_enabled = True
        self.color_style = "static"
        self.left_color = (0, 150, 255)
        self.right_color = (255, 70, 170)
        self.split_key = 44
        self.key_ranges = key_ranges
        self._pixels: list[tuple[int, int, int]] = [(0, 0, 0)] * key_ranges[-1].led_end
        self._active_notes: dict[int, int] = {}
        self._sustained_notes: set[int] = set()
        self.sustain_down = False

    def is_piano_note(self, note: int) -> bool:
        return FIRST_MIDI_NOTE <= note < FIRST_MIDI_NOTE + len(self.key_ranges)

    def _paint_note(self, note: int, velocity: int) -> None:
        key_range = self._range_for_note(note)
        level = (max(1, min(127, velocity)) / 127) ** 2 if self.velocity_sensitive else 1
        color = tuple(round(channel * level) for channel in self._note_color(note))
        for led in range(key_range.led_start, key_range.led_end):
            self._pixels[led] = color

    def range_update(self, note: int) -> tuple[int, int, int, int, int]:
        """Return the compact LED update for one MIDI note's physical key."""
        key_range = self._range_for_note(note)
        velocity = self._active_notes.get(note)
        if velocity is None:
            color = (0, 0, 0)
        else:
            level = (max(1, min(127, velocity)) / 127) ** 2 if self.velocity_sensitive else 1
            color = tuple(round(channel * level) for channel in self._note_color(note))
        return key_range.led_start, key_range.led_end - key_range.led_start, *color

    def _clear_note(self, note: int) -> None:
        key_range = self._range_for_note(note)
        for led in range(key_range.led_start, key_range.led_end):
            self._pixels[led] = (0, 0, 0)

    def note_on(self, note: int, velocity: int) -> bool:
        if not self.is_piano_note(note):
            return False
        self._sustained_notes.discard(note)
        self._active_notes[note] = velocity
        self._paint_note(note, velocity)
        return True

    def note_off(self, note: int) -> bool:
        if not self.is_piano_note(note):
            return False
        if self.sustain_enabled and self.sustain_down:
            self._sustained_notes.add(note)
            return True
        self._active_notes.pop(note, None)
        self._clear_note(note)
        return True

    def set_sustain(self, down: bool) -> bool:
        if not self.sustain_enabled:
            return False
        if self.sustain_down == down:
            return False
        self.sustain_down = down
        if not down:
            for note in tuple(self._sustained_notes):
                self._active_notes.pop(note, None)
                self._clear_note(note)
            self._sustained_notes.clear()
        return True

    def set_color(self, color: tuple[int, int, int]) -> None:
        self.color = color
        self._repaint_active_notes()

    def set_color_style(self, style: str, left_color: tuple[int, int, int], right_color: tuple[int, int, int], split_key: int) -> None:
        self.color_style, self.left_color, self.right_color = style, left_color, right_color
        self.split_key = split_key
        self._repaint_active_notes()

    def _note_color(self, note: int) -> tuple[int, int, int]:
        key = note - FIRST_MIDI_NOTE + 1
        position = (key - 1) / max(1, len(self.key_ranges) - 1)
        if self.color_style == "rainbow":
            red, green, blue = colorsys.hsv_to_rgb((time.monotonic() * 0.08 + position) % 1, 0.9, 1)
            return round(red * 255), round(green * 255), round(blue * 255)
        if self.color_style == "split":
            return self.left_color if key <= self.split_key else self.right_color
        return self.color

    def set_velocity_sensitive(self, enabled: bool) -> None:
        self.velocity_sensitive = enabled
        self._repaint_active_notes()

    def set_sustain_enabled(self, enabled: bool) -> None:
        self.sustain_enabled = enabled
        if not enabled:
            self.sustain_down = False
            for note in tuple(self._sustained_notes):
                self._active_notes.pop(note, None)
                self._clear_note(note)
            self._sustained_notes.clear()

    def _repaint_active_notes(self) -> None:
        self._pixels = [(0, 0, 0)] * self.led_count
        for note, velocity in self._active_notes.items():
            self._paint_note(note, velocity)

    def _range_for_note(self, note: int) -> KeyRange:
        return self.key_ranges[note - FIRST_MIDI_NOTE]

    @property
    def led_count(self) -> int:
        return len(self._pixels)

    def frame(self) -> tuple[tuple[int, int, int], ...]:
        return tuple(self._pixels)


class MidiLedAgent:
    def __init__(self, client: SerialLedClient, color: tuple[int, int, int], key_ranges: tuple[KeyRange, ...] = KEY_RANGES, effect_mode: str = "direct") -> None:
        self.client = client
        self.state = MidiLedState(color, key_ranges=key_ranges)
        self.effect_mode = effect_mode
        self.fade_duration_ms = 700
        self.wave_interval_ms = 18
        self._lock = threading.Lock()
        self._frame_ready = threading.Event()
        self._pending_ranges: dict[int, tuple[int, int, int, int, int]] = {}
        self._pending_waves: list[tuple[int, int, int, int]] = []
        self._pending_fades: list[tuple[int, int, int, int, int, int]] = []
        self._midi_through: Any | None = None
        self._full_frame_pending = False
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._send_frames, name="pianoled-midi-output", daemon=True)

    def start(self) -> None:
        self.client.info()  # Establishes the real-time session before playing.
        self.client.set_led_count(self.state.led_count)
        self.client.start_center_wave()
        time.sleep(((self.state.led_count + 1) // 2) * 0.012 + 0.05)
        self.client.clear()
        self._worker.start()

    def close(self) -> None:
        self._stop.set()
        self._frame_ready.set()
        if self._worker.is_alive():
            self._worker.join(timeout=1)
        self.client.clear()
        self.client.close()

    def handle_message(self, message: Any) -> None:
        # Keep the music available to a DAW while PianoLED reacts to it.
        if self._midi_through is not None:
            try:
                self._midi_through.send(message)
            except Exception:
                # A disconnected DAW route must never interrupt LED playback.
                pass
        changed = False
        changed_note: int | None = None
        requires_full_frame = False
        with self._lock:
            previous_update: tuple[int, int, int, int, int] | None = None
            if message.type == "note_on":
                if message.velocity == 0:
                    previous_update = self.state.range_update(message.note) if self.state.is_piano_note(message.note) else None
                    changed = self.state.note_off(message.note)
                else:
                    changed = self.state.note_on(message.note, message.velocity)
                changed_note = message.note
            elif message.type == "note_off":
                previous_update = self.state.range_update(message.note) if self.state.is_piano_note(message.note) else None
                changed = self.state.note_off(message.note)
                changed_note = message.note
            elif message.type == "control_change" and message.control == 64:
                changed = self.state.set_sustain(message.value >= 64)
                requires_full_frame = changed
            if changed:
                if changed_note is not None and self.state.is_piano_note(changed_note):
                    update = self.state.range_update(changed_note)
                    if self.effect_mode == "wave" and message.type == "note_on" and message.velocity > 0:
                        self._pending_waves.append((update[0] + update[1] // 2, update[2], update[3], update[4]))
                    elif self.effect_mode == "constellation" and message.type == "note_on" and message.velocity > 0:
                        # Main key is immediate; two dim neighbouring sparks fade locally.
                        self._pending_ranges[update[0]] = update
                        red, green, blue = (channel // 3 for channel in update[2:])
                        if update[0] > 0:
                            self._pending_fades.append((update[0] - 1, 1, red, green, blue, self.fade_duration_ms))
                        right = update[0] + update[1]
                        if right < self.state.led_count:
                            self._pending_fades.append((right, 1, red, green, blue, self.fade_duration_ms))
                    elif self.effect_mode == "fade":
                        if previous_update and update[2:] == (0, 0, 0) and previous_update[2:] != (0, 0, 0):
                            self._pending_fades.append((*previous_update, self.fade_duration_ms))
                        else:
                            # The key must be visible at note-on; only note-off fades.
                            self._pending_ranges[update[0]] = update
                    elif self.effect_mode in {"direct", "constellation"}:
                        self._pending_ranges[update[0]] = update
                if requires_full_frame:
                    self._full_frame_pending = True
                self._frame_ready.set()

    def set_color(self, color: tuple[int, int, int]) -> None:
        with self._lock:
            self.state.set_color(color)
            self._full_frame_pending = True
            self._frame_ready.set()

    def set_velocity_sensitive(self, enabled: bool) -> None:
        with self._lock:
            self.state.set_velocity_sensitive(enabled)
            self._full_frame_pending = True
            self._frame_ready.set()

    def set_sustain_enabled(self, enabled: bool) -> None:
        with self._lock:
            self.state.set_sustain_enabled(enabled)
            self._full_frame_pending = True
            self._frame_ready.set()

    def set_effect_mode(self, effect_mode: str) -> None:
        if effect_mode not in {"direct", "fade", "wave", "constellation"}:
            raise ValueError("modo de efecto no válido")
        with self._lock:
            self.effect_mode = effect_mode
            self._pending_waves.clear()
            self._pending_fades.clear()
            self._full_frame_pending = effect_mode in {"direct", "fade", "constellation"}
            self._frame_ready.set()

    def set_midi_through(self, output: Any | None) -> None:
        self._midi_through = output

    def set_fade_duration(self, duration_ms: int) -> None:
        with self._lock:
            self.fade_duration_ms = max(100, min(5000, duration_ms))

    def set_wave_interval(self, interval_ms: int) -> None:
        with self._lock:
            self.wave_interval_ms = max(8, min(200, interval_ms))

    def set_color_style(self, style: str, left_color: tuple[int, int, int], right_color: tuple[int, int, int], split_key: int) -> None:
        with self._lock:
            self.state.set_color_style(style, left_color, right_color, split_key)
            self._full_frame_pending = True
            self._frame_ready.set()

    def _send_frames(self) -> None:
        """Send immediate serial deltas; USB is ordered and does not lose packets."""
        resync_at: float | None = None
        while not self._stop.is_set():
            timeout = None if resync_at is None else max(0, resync_at - time.monotonic())
            changed = self._frame_ready.wait(timeout)
            if self._stop.is_set():
                return
            if changed:
                self._frame_ready.clear()
                # MIDI messages in a chord are normally delivered back-to-back. Combining
                # them avoids one 6 ms WS2812 refresh for every key in that chord.
                time.sleep(CHORD_COALESCE_SECONDS)
                with self._lock:
                    if self._full_frame_pending:
                        frame = self.state.frame()
                        self._full_frame_pending = False
                        self._pending_ranges.clear()
                        ranges = ()
                        waves = ()
                        fades = ()
                    else:
                        frame = ()
                        ranges = tuple(self._pending_ranges.values())
                        self._pending_ranges.clear()
                        waves = tuple(self._pending_waves)
                        self._pending_waves.clear()
                        fades = tuple(self._pending_fades)
                        self._pending_fades.clear()
                if frame:
                    self.client.set_frame_realtime(frame)
                    resync_at = None
                elif ranges:
                    self.client.set_ranges_realtime(ranges)
                    # A later full snapshot would erase local spark/fade animations.
                    resync_at = None if fades else (time.monotonic() + STATE_RESYNC_SECONDS if getattr(self.client, "requires_state_resync", True) else None)
                for start, red, green, blue in waves:
                    self.client.start_note_wave(start, red, green, blue, self.wave_interval_ms)
                for start, count, red, green, blue, duration in fades:
                    self.client.start_note_fade(start, count, red, green, blue, duration)
                continue

            # Kept for transports that request a periodic state snapshot.
            with self._lock:
                frame = self.state.frame()
            self.client.set_frame_realtime(frame)
            resync_at = None


def choose_port(ports: Iterable[str], requested: str | None) -> str:
    ports = list(ports)
    if requested:
        matches = [port for port in ports if requested.lower() in port.lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"no se encontró un puerto MIDI que contenga: {requested}")
        raise ValueError(f"la búsqueda '{requested}' coincide con varios puertos: {matches}")
    if len(ports) == 1:
        return ports[0]
    if not ports:
        raise ValueError("no se detectó ningún puerto MIDI de entrada")
    raise ValueError("hay varios puertos MIDI; usa --port con parte de su nombre: " + ", ".join(ports))


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente MIDI local de PianoLED")
    parser.add_argument("--list-ports", action="store_true", help="Mostrar entradas MIDI disponibles y salir")
    parser.add_argument("--port", help="Nombre, o parte del nombre, de la entrada MIDI")
    parser.add_argument("--serial-port", help="Puerto COM del ESP32, por ejemplo COM3")
    parser.add_argument("--color", type=parse_color, default=(255, 255, 255), help="Color RRGGBB, por defecto FFFFFF")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin interfaz gr\u00e1fica")
    args = parser.parse_args()

    if not args.list_ports and not args.headless:
        from .midi_gui import run
        run()
        return

    try:
        import mido
    except ImportError as error:
        raise SystemExit("Falta mido/python-rtmidi. Ejecuta: pip install -e .") from error

    ports = mido.get_input_names()
    if args.list_ports:
        print("\n".join(ports) if ports else "No se detectaron entradas MIDI.")
        return
    try:
        port_name = choose_port(ports, args.port)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    if not args.serial_port:
        raise SystemExit("Indica el ESP32 con --serial-port COM3")
    agent = MidiLedAgent(SerialLedClient(args.serial_port), args.color)
    agent.start()
    print(f"PianoLED MIDI conectado a: {port_name}")
    print("Pulsa Ctrl+C para detenerlo.")
    try:
        with mido.open_input(port_name, callback=agent.handle_message):
            threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        agent.close()


if __name__ == "__main__":
    main()
