"""PySide6 desktop control panel for PianoLED."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGridLayout, QGroupBox,
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSlider, QSpinBox, QToolButton, QVBoxLayout, QWidget, QColorDialog,
)

from .effects import rainbow_color
from .key_mapping import MappingConfig, build_key_ranges
from .serial_transport import SerialLedClient


class Signals(QObject):
    error = Signal(str)
    connected = Signal(object)
    connection_ready = Signal(object, object)


class VirtualPianoDialog(QDialog):
    def __init__(self, key_ranges, play_key, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._play_key = play_key
        self._buttons: dict[int, QToolButton] = {}
        self._black_keys: dict[int, bool] = {}
        self.setWindowTitle("Piano virtual")
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.keys_widget = QWidget()
        self.keys_layout = QHBoxLayout(self.keys_widget)
        self.keys_layout.setContentsMargins(8, 8, 8, 8)
        self.keys_layout.setSpacing(0)
        scroll.setWidget(self.keys_widget)
        layout.addWidget(scroll)
        self.set_mapping(key_ranges)

    @staticmethod
    def _style(black: bool, active: bool = False) -> str:
        color = "#e33b3b" if active else ("#12151c" if black else "#edf1fa")
        text = "white" if black or active else "#1a1d24"
        return f"QToolButton {{ background:{color}; color:{text}; border:1px solid #303846; border-radius:0 0 4px 4px; font-size:8px; }}"

    def set_mapping(self, key_ranges) -> None:  # type: ignore[no-untyped-def]
        while self.keys_layout.count():
            item = self.keys_layout.takeAt(0)
            if widget := item.widget(): widget.deleteLater()
        self._buttons.clear()
        self._black_keys.clear()
        for key_range in key_ranges:
            black = key_range.midi_note % 12 in {1, 3, 6, 8, 10}
            button = QToolButton()
            button.setText(str(key_range.key))
            button.setFixedWidth(22 if not black else 14)
            button.setFixedHeight(142 if not black else 88)
            button.setStyleSheet(self._style(black))
            button.clicked.connect(lambda checked=False, item=key_range, is_black=black, target=button: self._pressed(item, is_black, target))
            self.keys_layout.addWidget(button)
            self._buttons[key_range.key] = button
            self._black_keys[key_range.key] = black
        self.keys_layout.addStretch()
        self.resize(min(1800, max(500, len(key_ranges) * 22 + 40)), 210)

    def _pressed(self, key_range, black: bool, button: QToolButton) -> None:  # type: ignore[no-untyped-def]
        for key, item in self._buttons.items():
            item.setStyleSheet(self._style(self._black_keys[key]))
        button.setStyleSheet(self._style(black, True))
        self._play_key(key_range.led_start, key_range.led_count)


class ManualControlTab(QWidget):
    def __init__(self, mapping_config: MappingConfig = MappingConfig()) -> None:
        super().__init__()
        self.setMinimumWidth(620)
        self._client: SerialLedClient | None = None
        self._color = QColor("#ffffff")
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._signals = Signals()
        self._signals.connected.connect(self._show_connected)
        self._signals.connection_ready.connect(self._connected)
        self._signals.error.connect(self._show_error)
        self._effect_timer = QTimer(self)
        self._effect_timer.timeout.connect(self._effect_tick)
        self._effect_index = 0
        self._effect_name: str | None = None
        self._effect_future = None
        self._mapping_config = mapping_config
        self._key_ranges = build_key_ranges(mapping_config.counts)
        self._build_ui()
        self._refresh_color_button()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        device_box = QGroupBox("Controlador ESP32 (USB o Bluetooth)")
        device_layout = QGridLayout(device_box)
        self.serial_port = QComboBox()
        self.serial_port.setEditable(True)
        self.serial_port.setPlaceholderText("COM3")
        self.status = QLabel("Sin conectar")
        self.status.setObjectName("status")
        scan = QPushButton("Actualizar puertos")
        scan.clicked.connect(self._refresh_serial_ports)
        self.connect_button = QPushButton("Conectar")
        self.connect_button.clicked.connect(self._toggle_connection)
        device_layout.addWidget(QLabel("Puerto COM:"), 0, 0)
        device_layout.addWidget(self.serial_port, 0, 1, 1, 2)
        device_layout.addWidget(scan, 0, 3)
        device_layout.addWidget(self.status, 1, 0, 1, 3)
        device_layout.addWidget(self.connect_button, 1, 3)
        layout.addWidget(device_box)
        controls = QGridLayout()
        controls.setHorizontalSpacing(14)
        controls.setVerticalSpacing(14)
        layout.addLayout(controls)

        color_box = QGroupBox("Color activo")
        color_layout = QFormLayout(color_box)
        self.led_span_label = QLabel("1 LED")
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._choose_color)
        self.brightness = QSlider(Qt.Orientation.Horizontal); self.brightness.setRange(1, 255); self.brightness.setValue(255)
        self.brightness_label = QLabel("100 %")
        self.brightness.valueChanged.connect(self._update_brightness_label)
        self.brightness.sliderReleased.connect(self._set_brightness)
        brightness_layout = QHBoxLayout(); brightness_layout.addWidget(self.brightness); brightness_layout.addWidget(self.brightness_label)
        color_layout.addRow("Color:", self.color_button)
        color_layout.addRow("Intensidad:", brightness_layout)
        controls.addWidget(color_box, 0, 0)

        single_box = QGroupBox("LED único")
        single = QFormLayout(single_box)
        self.single_index = QSpinBox(); self.single_index.setRange(0, 197)
        set_led = QPushButton("Encender solo este LED")
        set_led.clicked.connect(self._set_single_led)
        single.addRow("Índice LED:", self.single_index)
        single.addRow(set_led)
        controls.addWidget(single_box, 0, 1)

        range_box = QGroupBox("Rango de LEDs")
        range_control = QFormLayout(range_box)
        self.range_start = QSpinBox(); self.range_start.setRange(0, 197)
        self.led_span = QSlider(Qt.Orientation.Horizontal); self.led_span.setRange(1, 198); self.led_span.setValue(1)
        self.led_span.valueChanged.connect(self._update_span_label)
        span_layout = QHBoxLayout(); span_layout.addWidget(self.led_span); span_layout.addWidget(self.led_span_label)
        set_range = QPushButton("Encender rango")
        set_range.clicked.connect(self._set_range)
        range_control.addRow("LED inicial:", self.range_start)
        range_control.addRow("Cantidad:", span_layout)
        range_control.addRow(set_range)
        controls.addWidget(range_box, 1, 0)

        piano_box = QGroupBox("Piano virtual")
        piano_layout = QVBoxLayout(piano_box)
        piano_layout.addWidget(QLabel("Abre un teclado visual ajustado a la configuración actual."))
        open_piano = QPushButton("Abrir piano virtual")
        open_piano.clicked.connect(self._open_virtual_piano)
        piano_layout.addWidget(open_piano)
        controls.addWidget(piano_box, 1, 1)

        strip_box = QGroupBox("Toda la tira")
        strip = QHBoxLayout(strip_box)
        fill = QPushButton("Rellenar tira")
        fill.clicked.connect(self._fill)
        clear = QPushButton("Apagar todo")
        clear.clicked.connect(self._clear)
        strip.addWidget(fill); strip.addWidget(clear)
        controls.addWidget(strip_box, 2, 0, 1, 2)

        effects_box = QGroupBox("Efectos")
        effects = QHBoxLayout(effects_box)
        rainbow = QPushButton("Rainbow")
        rainbow.clicked.connect(lambda: self._start_effect("rainbow"))
        sweep = QPushButton("Barrido")
        sweep.clicked.connect(lambda: self._start_effect("sweep"))
        stop = QPushButton("Detener")
        stop.clicked.connect(self._stop_effect)
        effects.addWidget(rainbow); effects.addWidget(sweep); effects.addWidget(stop)
        controls.addWidget(effects_box, 3, 0, 1, 2)
        layout.addStretch()
        self.apply_mapping_config(self._mapping_config)
        self._refresh_serial_ports()

    def _run(self, action, callback=None):
        future = self._executor.submit(action)
        def done(task):
            try:
                result = task.result()
            except Exception as error:  # network errors are shown to the user
                self._signals.error.emit(str(error))
            else:
                if callback:
                    callback(result)
        future.add_done_callback(done)
        return future

    def _refresh_serial_ports(self) -> None:
        current = self.serial_port.currentText()
        self.serial_port.clear()
        self.serial_port.addItems(SerialLedClient.available_ports())
        self.serial_port.setEditText(current)

    def _toggle_connection(self) -> None:
        if self._client is not None:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        label = self.serial_port.currentText()
        if not label:
            self._show_error("Selecciona el puerto COM del ESP32.")
            return
        client = SerialLedClient(SerialLedClient.port_name(label), color_order=self._mapping_config.color_order)
        self.status.setText("Conectando por serie…")
        self.connect_button.setEnabled(False)
        self._signals.connection_ready.emit(client, None)

    def _connected(self, client: SerialLedClient, info) -> None:  # type: ignore[no-untyped-def]
        self._client = client
        self.apply_mapping_config(self._mapping_config)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Desconectar")
        self._signals.connected.emit(info)

    def apply_mapping_config(self, config: MappingConfig) -> None:
        self._mapping_config = config
        self._key_ranges = build_key_ranges(config.counts)
        maximum = config.total_led_count - 1
        self.single_index.setMaximum(maximum)
        self.range_start.setMaximum(maximum)
        self.led_span.setMaximum(config.total_led_count)
        if hasattr(self, "_piano_dialog") and self._piano_dialog is not None:
            self._piano_dialog.set_mapping(self._key_ranges)
        if self._client is not None:
            self._run(lambda: self._client.set_led_count(config.total_led_count))

    def _open_virtual_piano(self) -> None:
        if not hasattr(self, "_piano_dialog") or self._piano_dialog is None:
            self._piano_dialog = VirtualPianoDialog(self._key_ranges, self._play_key, self)
        self._piano_dialog.show()
        self._piano_dialog.raise_()
        self._piano_dialog.activateWindow()

    def _play_key(self, start: int, count: int) -> None:
        if client := self._require_client():
            self._stop_effect()
            color = self._device_rgb(*self._rgb())
            self._run(lambda: client.show_range(start, count, *color))

    def _disconnect(self) -> None:
        self._stop_effect()
        self._client = None
        self.connect_button.setText("Conectar")
        self.status.setText("Desconectado")

    def _show_connected(self, info) -> None:  # type: ignore[no-untyped-def]
        self.status.setText(f"Serie conectada: {self._mapping_config.total_led_count} LEDs")

    def _show_error(self, message: str) -> None:
        self.status.setText("Error de conexión")
        self.connect_button.setEnabled(True)
        QMessageBox.warning(self, "PianoLED", message)

    def _require_client(self) -> SerialLedClient | None:
        if self._client is None:
            QMessageBox.information(self, "PianoLED", "Conéctate primero al controlador ESP32.")
        return self._client

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Elige un color")
        if color.isValid():
            self._color = color
            self._refresh_color_button()

    def _refresh_color_button(self) -> None:
        self.color_button.setText(self._color.name().upper())
        self.color_button.setStyleSheet(f"background: {self._color.name()}; color: {'#000' if self._color.lightness() > 150 else '#fff'};")

    def _rgb(self) -> tuple[int, int, int]:
        return self._color.red(), self._color.green(), self._color.blue()

    @staticmethod
    def _device_rgb(red: int, green: int, blue: int) -> tuple[int, int, int]:
        """FastLED's configured BGR order performs the physical conversion."""
        return red, green, blue

    def _update_span_label(self, value: int) -> None:
        self.led_span_label.setText(f"{value} LED" if value == 1 else f"{value} LEDs")

    def _update_brightness_label(self, value: int) -> None:
        self.brightness_label.setText(f"{round(value * 100 / 255)} %")

    def _set_brightness(self) -> None:
        if client := self._require_client():
            brightness = self.brightness.value()
            self._run(lambda: client.set_brightness(brightness))

    @staticmethod
    def _paint_range(client: SerialLedClient, start: int, count: int, maximum: int, color: tuple[int, int, int]) -> None:
        """Atomically illuminate a range and clear all remaining LEDs."""
        client.show_range(start, min(count, maximum + 1 - start), *color)

    def _set_single_led(self) -> None:
        if client := self._require_client():
            self._stop_effect()
            index, color = self.single_index.value(), self._device_rgb(*self._rgb())
            self._run(lambda: client.show_range(index, 1, *color))

    def _set_range(self) -> None:
        if client := self._require_client():
            self._stop_effect()
            start, count = self.range_start.value(), self.led_span.value()
            color, maximum = self._device_rgb(*self._rgb()), self.range_start.maximum()
            self._run(lambda: self._paint_range(client, start, count, maximum, color))

    def _fill(self) -> None:
        if client := self._require_client():
            self._stop_effect()
            color = self._device_rgb(*self._rgb())
            self._run(lambda: client.fill(*color))

    def _clear(self) -> None:
        self._stop_effect()
        if client := self._require_client():
            def clear_stably() -> None:
                client.clear()
                time.sleep(0.08)
                client.clear()
            self._run(clear_stably)

    def _start_effect(self, name: str) -> None:
        client = self._require_client()
        if client is None:
            return
        self._stop_effect()
        self._effect_name, self._effect_index, self._effect_future = name, 0, None
        if name == "sweep":
            color = self._device_rgb(*self._rgb())
            self._effect_future = self._run(lambda: client.start_sweep(*color, 50))
        elif name == "rainbow":
            self._effect_future = self._run(lambda: client.start_rainbow(30))
        else:
            self._effect_timer.start(30)

    def _stop_effect(self) -> None:
        self._effect_timer.stop()
        if self._effect_name in ("sweep", "rainbow") and self._client is not None:
            self._run(self._client.stop_animation)
        self._effect_name = None

    def _effect_tick(self) -> None:
        client = self._client
        if client is None:
            self._stop_effect()
            return
        if self._effect_future is not None and not self._effect_future.done():
            return
        count = self.range_start.maximum() + 1
        if self._effect_name == "rainbow":
            frame = tuple(self._device_rgb(*rainbow_color(self._effect_index + pixel, count)) for pixel in range(count))
            self._effect_future = self._run(lambda: client.set_frame(frame))
            self._effect_index = (self._effect_index + 1) % count

    def shutdown(self) -> None:
        self._stop_effect()
        self._executor.shutdown(wait=False, cancel_futures=True)


def run() -> None:
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet("QWidget { background: #171a20; color: #e7eaf0; font-size: 14px; } QGroupBox { border: 1px solid #394150; border-radius: 6px; margin-top: 12px; padding: 10px; font-weight: bold; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; } QPushButton, QLineEdit, QSpinBox, QComboBox { border: 1px solid #4b5568; border-radius: 4px; padding: 6px; background: #252b35; } QPushButton:hover { background: #344055; } #status { color: #8bd5a2; }")
    window = ManualControlTab()
    window.setWindowTitle("PianoLED — Control manual")
    window.show()
    app.exec()
