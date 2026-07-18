"""Desktop configuration window for the local MIDI PianoLED agent."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QPlainTextEdit, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from .esp32 import Esp32Client
from .gui import ManualControlTab
from .key_mapping import (
    KEY_LED_COUNTS, MappingConfig, build_key_ranges, format_key_led_counts,
    load_user_mapping_config, parse_key_led_counts, save_user_mapping_config,
)
from .midi_agent import MidiLedAgent
from .serial_transport import SerialLedClient


class MappingTab(QWidget):
    def __init__(self, on_saved) -> None:  # type: ignore[no-untyped-def]
        super().__init__()
        self._on_saved = on_saved
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.total_leds = QSpinBox(); self.total_leds.setRange(1, 255)
        self.key_count = QSpinBox(); self.key_count.setRange(1, 128)
        self.color_order = QComboBox(); self.color_order.addItems(("RGB", "RBG", "GRB", "GBR", "BRG", "BGR"))
        form.addRow("LEDs totales:", self.total_leds)
        form.addRow("Teclas totales:", self.key_count)
        form.addRow("Orden de color USB:", self.color_order)
        layout.addLayout(form)
        layout.addWidget(QLabel("Un valor por tecla. La suma debe coincidir con el total de LEDs."))
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Tecla 1: 4\nTecla 2: 2")
        layout.addWidget(self.editor)
        self.status = QLabel()
        save = QPushButton("Guardar y aplicar mapeo")
        reset = QPushButton("Restaurar mapeo predeterminado")
        save.clicked.connect(self._save)
        reset.clicked.connect(lambda: self.set_config(MappingConfig()))
        buttons = QHBoxLayout()
        buttons.addWidget(save)
        buttons.addWidget(reset)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        self._last_counts = KEY_LED_COUNTS
        self._updating_dimensions = False
        self.total_leds.valueChanged.connect(self._dimensions_changed)
        self.key_count.valueChanged.connect(self._dimensions_changed)

    def set_config(self, config: MappingConfig) -> None:
        self._updating_dimensions = True
        self.total_leds.setMinimum(config.key_count)
        self.total_leds.setValue(config.total_led_count)
        self.key_count.setValue(config.key_count)
        self.color_order.setCurrentText(config.color_order)
        self.editor.setPlainText(format_key_led_counts(config.counts))
        self._last_counts = config.counts
        self._updating_dimensions = False
        self.status.setText(f"{config.key_count} teclas · {config.total_led_count} LEDs")

    def _save(self) -> None:
        try:
            counts = parse_key_led_counts(self.editor.toPlainText(), None, self.key_count.value())
            if sum(counts) != self.total_leds.value():
                counts = self._rescale_counts(counts, self.total_leds.value())
                self.editor.setPlainText(format_key_led_counts(counts))
            config = MappingConfig(counts, self.total_leds.value(), self.color_order.currentText())
            self._on_saved(config)
            save_user_mapping_config(config)
        except ValueError as error:
            self.status.setText(f"Error: {error}")
            return
        self.status.setText(f"Guardado: {config.key_count} teclas · {config.total_led_count} LEDs")
        self._last_counts = counts

    def _dimensions_changed(self) -> None:
        if self._updating_dimensions:
            return
        self._updating_dimensions = True
        target_keys = self.key_count.value()
        self.total_leds.setMinimum(target_keys)
        counts = self._last_counts
        if target_keys != len(counts):
            counts = self._resample_keys(counts, target_keys)
        counts = self._rescale_counts(counts, self.total_leds.value())
        self._last_counts = counts
        self.editor.setPlainText(format_key_led_counts(counts))
        self.status.setText(f"Mapeo adaptado: {target_keys} teclas · {self.total_leds.value()} LEDs")
        self._updating_dimensions = False

    @staticmethod
    def _rescale_counts(counts: tuple[int, ...], total: int) -> tuple[int, ...]:
        if total < len(counts):
            raise ValueError("el total de LEDs debe ser al menos igual al número de teclas")
        available = total - len(counts)
        weight = sum(counts)
        extras = [available * count / weight for count in counts]
        result = [1 + int(value) for value in extras]
        remainder = total - sum(result)
        for index in sorted(range(len(counts)), key=lambda item: extras[item] - int(extras[item]), reverse=True)[:remainder]:
            result[index] += 1
        return tuple(result)

    @staticmethod
    def _resample_keys(counts: tuple[int, ...], key_count: int) -> tuple[int, ...]:
        return tuple(counts[min(len(counts) - 1, index * len(counts) // key_count)] for index in range(key_count))


class MidiWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        try:
            import mido
        except ImportError as error:
            raise RuntimeError("Falta mido/python-rtmidi. Ejecuta: python -m pip install -e .") from error
        self._mido: Any = mido
        self._agent: MidiLedAgent | None = None
        self._input_port: Any = None
        self._color = QColor("#ffffff")
        try:
            self._mapping_config = load_user_mapping_config()
        except ValueError:
            self._mapping_config = MappingConfig()
        self._key_ranges = build_key_ranges(self._mapping_config.counts)
        self.setWindowTitle("PianoLED")
        self.setMinimumWidth(660)
        self._build_ui()
        self._refresh_ports()
        self._refresh_serial_ports()
        self._refresh_color_button()
        self._transport_changed()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        tabs = QTabWidget()
        midi_tab = QWidget()
        layout = QVBoxLayout(midi_tab)
        self.manual_tab = ManualControlTab(self._mapping_config)
        self.mapping_tab = MappingTab(self._mapping_saved)
        tabs.addTab(midi_tab, "MIDI")
        tabs.addTab(self.manual_tab, "Control manual")
        tabs.addTab(self.mapping_tab, "Configuración")
        root_layout.addWidget(tabs)

        piano_box = QGroupBox("Piano MIDI")
        piano_form = QFormLayout(piano_box)
        port_row = QHBoxLayout()
        self.port_list = QComboBox()
        refresh = QPushButton("Actualizar puertos")
        refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.port_list)
        port_row.addWidget(refresh)
        piano_form.addRow("Entrada MIDI:", port_row)
        layout.addWidget(piano_box)

        device_box = QGroupBox("Tira LED")
        device_form = QFormLayout(device_box)
        self.transport = QComboBox()
        self.transport.addItems(("USB serie (baja latencia)", "Wi-Fi"))
        self.transport.currentIndexChanged.connect(self._transport_changed)
        self.host = QLineEdit("10.42.0.26")
        serial_row = QHBoxLayout()
        self.serial_port = QComboBox()
        self.serial_port.setEditable(True)
        self.serial_port.setPlaceholderText("COM3")
        serial_refresh = QPushButton("Actualizar")
        serial_refresh.clicked.connect(self._refresh_serial_ports)
        serial_row.addWidget(self.serial_port)
        serial_row.addWidget(serial_refresh)
        device_form.addRow("Conexión:", self.transport)
        device_form.addRow("IP del ESP32:", self.host)
        device_form.addRow("Puerto ESP32:", serial_row)
        layout.addWidget(device_box)

        options_box = QGroupBox("Color")
        options_form = QFormLayout(options_box)
        self.color_button = QPushButton()
        self.color_button.clicked.connect(self._choose_color)
        self.brightness = QSlider(Qt.Orientation.Horizontal)
        self.brightness.setRange(1, 255)
        self.brightness.setValue(128)
        self.brightness_label = QLabel()
        self.brightness.valueChanged.connect(self._brightness_changed)
        self.brightness.sliderReleased.connect(self._send_brightness)
        brightness_row = QHBoxLayout()
        brightness_row.addWidget(self.brightness)
        brightness_row.addWidget(self.brightness_label)
        self.sustain = QCheckBox("Mantener las notas mientras el pedal est\u00e1 pulsado")
        self.sustain.setChecked(True)
        self.sustain.toggled.connect(self._sustain_changed)
        self.velocity = QCheckBox("Variar intensidad seg\u00fan la fuerza de la tecla")
        self.velocity.setChecked(False)
        self.velocity.toggled.connect(self._velocity_changed)
        self.midi_effect = QComboBox()
        self.midi_effect.addItem("Iluminar tecla", "direct")
        self.midi_effect.addItem("Onda doble decreciente", "wave")
        self.midi_effect.currentIndexChanged.connect(self._effect_changed)
        self.color_style = QComboBox(); self.color_style.addItem("Color fijo", "static"); self.color_style.addItem("Arcoíris dinámico", "rainbow"); self.color_style.addItem("Gradiente grave → agudo", "gradient"); self.color_style.addItem("Dos manos", "split")
        self.left_hex = QLineEdit("#0096FF")
        self.right_hex = QLineEdit("#FF46AA")
        self.split_key = QSpinBox(); self.split_key.setRange(1, 88); self.split_key.setValue(44)
        self.color_style.currentIndexChanged.connect(self._style_changed)
        self.left_hex.editingFinished.connect(self._style_changed); self.right_hex.editingFinished.connect(self._style_changed); self.split_key.valueChanged.connect(self._style_changed)
        options_form.addRow("Color de las notas:", self.color_button)
        options_form.addRow("Intensidad general:", brightness_row)
        options_form.addRow(self.sustain)
        options_form.addRow(self.velocity)
        options_form.addRow("Efecto MIDI:", self.midi_effect)
        options_form.addRow("Estilo de color:", self.color_style)
        options_form.addRow("Mano izquierda:", self.left_hex)
        options_form.addRow("Mano derecha:", self.right_hex)
        options_form.addRow("Dividir en tecla:", self.split_key)
        layout.addWidget(options_box)

        self.status = QLabel("Elige el piano y pulsa Iniciar.")
        self.start_button = QPushButton("Iniciar MIDI")
        self.start_button.clicked.connect(self._toggle)
        layout.addWidget(self.status)
        layout.addWidget(self.start_button)
        layout.addStretch()
        self._brightness_changed(self.brightness.value())
        self.mapping_tab.set_config(self._mapping_config)

    def _mapping_saved(self, config: MappingConfig) -> None:
        if self._agent:
            raise ValueError("Detén MIDI antes de cambiar el mapeo de teclas.")
        self._mapping_config = config
        self._key_ranges = build_key_ranges(config.counts)
        self.manual_tab.apply_mapping_config(config)
        self.status.setText("Mapeo actualizado; se usará al iniciar MIDI.")

    def _refresh_ports(self) -> None:
        current = self.port_list.currentText()
        self.port_list.clear()
        self.port_list.addItems(self._mido.get_input_names())
        if current:
            index = self.port_list.findText(current)
            if index >= 0:
                self.port_list.setCurrentIndex(index)
        if not self.port_list.count():
            self.status.setText("No se detecta ning\u00fan piano MIDI. Con\u00e9ctalo y pulsa Actualizar puertos.")

    def _refresh_serial_ports(self) -> None:
        current = self.serial_port.currentText()
        self.serial_port.clear()
        try:
            ports = SerialLedClient.available_ports()
        except RuntimeError as error:
            self.status.setText(str(error))
            ports = []
        self.serial_port.addItems(ports)
        if current:
            index = self.serial_port.findText(current)
            if index >= 0:
                self.serial_port.setCurrentIndex(index)
            else:
                self.serial_port.setEditText(current)

    def _transport_changed(self) -> None:
        serial_mode = self.transport.currentIndex() == 0
        available = self._agent is None
        self.host.setEnabled(available and not serial_mode)
        self.serial_port.setEnabled(available and serial_mode)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(self._color, self, "Color de las notas")
        if color.isValid():
            self._color = color
            self._refresh_color_button()
            if self._agent:
                self._agent.set_color(self._rgb())

    def _refresh_color_button(self) -> None:
        self.color_button.setText(self._color.name().upper())
        foreground = "#000" if self._color.lightness() > 150 else "#fff"
        self.color_button.setStyleSheet(f"background:{self._color.name()}; color:{foreground};")

    def _rgb(self) -> tuple[int, int, int]:
        return self._color.red(), self._color.green(), self._color.blue()

    def _brightness_changed(self, value: int) -> None:
        self.brightness_label.setText(f"{round(value * 100 / 255)} %")

    def _send_brightness(self) -> None:
        if self._agent:
            self._agent.client.set_brightness(self.brightness.value())

    def _sustain_changed(self, enabled: bool) -> None:
        if self._agent:
            self._agent.set_sustain_enabled(enabled)

    def _velocity_changed(self, enabled: bool) -> None:
        if self._agent:
            self._agent.set_velocity_sensitive(enabled)

    def _effect_changed(self) -> None:
        if self._agent:
            self._agent.set_effect_mode(self.midi_effect.currentData())

    def _style_changed(self) -> None:
        if self._agent:
            self._agent.set_color_style(self.color_style.currentData(), self._hex(self.left_hex.text()), self._hex(self.right_hex.text()), self.split_key.value())

    @staticmethod
    def _hex(value: str) -> tuple[int, int, int]:
        color = QColor(value)
        return (color.red(), color.green(), color.blue()) if color.isValid() else (255, 255, 255)

    def _toggle(self) -> None:
        if self._agent:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        port_name = self.port_list.currentText()
        host = self.host.text().strip()
        serial_label = self.serial_port.currentText()
        serial_mode = self.transport.currentIndex() == 0
        if not port_name or (serial_mode and not serial_label) or (not serial_mode and not host):
            QMessageBox.warning(self, "PianoLED MIDI", "Selecciona una entrada MIDI y el destino del ESP32.")
            return
        agent: MidiLedAgent | None = None
        try:
            client = SerialLedClient(SerialLedClient.port_name(serial_label), color_order=self._mapping_config.color_order) if serial_mode else Esp32Client(host)
            agent = MidiLedAgent(client, self._rgb(), self._key_ranges, self.midi_effect.currentData())
            agent.state.set_color_style(self.color_style.currentData(), self._hex(self.left_hex.text()), self._hex(self.right_hex.text()), self.split_key.value())
            agent.state.set_sustain_enabled(self.sustain.isChecked())
            agent.state.set_velocity_sensitive(self.velocity.isChecked())
            agent.start()
            agent.client.set_brightness(self.brightness.value())
            self._input_port = self._mido.open_input(port_name, callback=agent.handle_message)
            self._agent = agent
        except Exception as error:
            if agent:
                agent.close()
            QMessageBox.warning(self, "PianoLED MIDI", str(error))
            return
        self.host.setEnabled(False)
        self.transport.setEnabled(False)
        self.port_list.setEnabled(False)
        self.serial_port.setEnabled(False)
        self.status.setText(f"Activo: {port_name}")
        self.start_button.setText("Detener MIDI")

    def _stop(self) -> None:
        if self._input_port:
            self._input_port.close()
            self._input_port = None
        if self._agent:
            self._agent.close()
            self._agent = None
        self.host.setEnabled(True)
        self.transport.setEnabled(True)
        self.port_list.setEnabled(True)
        self._transport_changed()
        self.status.setText("MIDI detenido.")
        self.start_button.setText("Iniciar MIDI")

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._stop()
        self.manual_tab.shutdown()
        event.accept()


def run() -> None:
    app = QApplication.instance() or QApplication([])
    window = MidiWindow()
    window.show()
    app.exec()
