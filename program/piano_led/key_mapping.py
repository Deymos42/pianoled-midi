"""Physical mapping between the 88 piano keys and the LED strip."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


# Number of physical LEDs directly below each key, from A0 (key 1) to C8 (key 88).
KEY_LED_COUNTS: tuple[int, ...] = (
    4, 2, 2, 3, 2, 2, 3, 2, 2, 2,
    2, 2, 3, 2, 2, 2, 3, 2, 2, 2,
    3, 2, 2, 2, 2, 2, 2, 3, 2, 2,
    2, 3, 2, 2, 2, 3, 2, 2, 2, 2,
    2, 3, 2, 2, 3, 2, 2, 2, 2, 2,
    2, 3, 2, 2, 2, 2, 3, 2, 2, 3,
    2, 2, 2, 2, 2, 2, 2, 3, 2, 3,
    2, 2, 2, 2, 3, 2, 2, 2, 2, 2,
    3, 2, 2, 2, 2, 3, 2, 4,
)


@dataclass(frozen=True)
class KeyRange:
    key: int
    midi_note: int
    led_start: int
    led_count: int

    @property
    def led_end(self) -> int:
        """Exclusive final LED index."""
        return self.led_start + self.led_count


def build_key_ranges(counts: tuple[int, ...] = KEY_LED_COUNTS, midi_first_note: int = 21) -> tuple[KeyRange, ...]:
    if not counts:
        raise ValueError("el mapeo debe contener al menos una tecla")
    start = 0
    ranges: list[KeyRange] = []
    for key, count in enumerate(counts, start=1):
        if count < 1:
            raise ValueError(f"la tecla {key} debe tener al menos un LED")
        ranges.append(KeyRange(key, midi_first_note + key - 1, start, count))
        start += count
    return tuple(ranges)


KEY_RANGES = build_key_ranges()
MAPPED_LED_COUNT = sum(KEY_LED_COUNTS)


def range_for_key(key: int) -> KeyRange:
    if not 1 <= key <= len(KEY_RANGES):
        raise ValueError("key must be between 1 and 88")
    return KEY_RANGES[key - 1]


def format_key_led_counts(counts: tuple[int, ...] = KEY_LED_COUNTS) -> str:
    return "\n".join(f"Tecla {key}: {count}" for key, count in enumerate(counts, start=1))


def parse_key_led_counts(text: str, expected_led_count: int | None = MAPPED_LED_COUNT, key_count: int = 88) -> tuple[int, ...]:
    values: dict[int, int] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"Tecla\s+(\d+)\s*:\s*(\d+)", line, re.IGNORECASE)
        if not match:
            raise ValueError(f"línea {line_number}: usa el formato 'Tecla N: LEDs'")
        key, count = (int(value) for value in match.groups())
        if not 1 <= key <= key_count:
            raise ValueError(f"línea {line_number}: la tecla debe estar entre 1 y {key_count}")
        if key in values:
            raise ValueError(f"la tecla {key} aparece más de una vez")
        values[key] = count
    if set(values) != set(range(1, key_count + 1)):
        missing = [str(key) for key in range(1, key_count + 1) if key not in values]
        raise ValueError("faltan teclas: " + ", ".join(missing))
    counts = tuple(values[key] for key in range(1, key_count + 1))
    ranges = build_key_ranges(counts)
    if expected_led_count is not None and ranges[-1].led_end != expected_led_count:
        raise ValueError(f"el total debe ser {expected_led_count} LEDs, pero es {ranges[-1].led_end}")
    return counts


def user_mapping_path() -> Path:
    return Path.home() / ".pianoled" / "key_mapping.txt"


def user_settings_path() -> Path:
    return Path.home() / ".pianoled" / "settings.json"


@dataclass(frozen=True)
class MappingConfig:
    counts: tuple[int, ...] = KEY_LED_COUNTS
    total_led_count: int = MAPPED_LED_COUNT
    color_order: str = "BRG"

    @property
    def key_count(self) -> int:
        return len(self.counts)


def load_user_key_led_counts() -> tuple[int, ...]:
    path = user_mapping_path()
    return parse_key_led_counts(path.read_text(encoding="utf-8")) if path.exists() else KEY_LED_COUNTS


def save_user_key_led_counts(counts: tuple[int, ...]) -> None:
    path = user_mapping_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_key_led_counts(counts) + "\n", encoding="utf-8")


def load_user_mapping_config() -> MappingConfig:
    settings_path = user_settings_path()
    settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    key_count = int(settings.get("key_count", 88))
    total_led_count = int(settings.get("total_led_count", MAPPED_LED_COUNT))
    color_order = str(settings.get("color_order", "BRG"))
    if color_order not in {"RGB", "RBG", "GRB", "GBR", "BRG", "BGR"}:
        raise ValueError("orden de color no válido")
    path = user_mapping_path()
    counts = parse_key_led_counts(path.read_text(encoding="utf-8"), total_led_count, key_count) if path.exists() else KEY_LED_COUNTS
    if len(counts) != key_count or sum(counts) != total_led_count:
        raise ValueError("el mapeo guardado no coincide con la configuración")
    return MappingConfig(counts, total_led_count, color_order)


def save_user_mapping_config(config: MappingConfig) -> None:
    if config.color_order not in {"RGB", "RBG", "GRB", "GBR", "BRG", "BGR"}:
        raise ValueError("orden de color no válido")
    if sum(config.counts) != config.total_led_count:
        raise ValueError("la suma del mapeo no coincide con el total de LEDs")
    save_user_key_led_counts(config.counts)
    user_settings_path().write_text(json.dumps({
        "key_count": config.key_count,
        "total_led_count": config.total_led_count,
        "color_order": config.color_order,
    }, indent=2) + "\n", encoding="utf-8")
