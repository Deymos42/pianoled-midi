# PianoLED MIDI

Aplicación de escritorio Windows para visualizar un piano MIDI en una tira de LEDs WS2812B. El ordenador recibe MIDI por USB, decide los colores y efectos, y envía los comandos al ESP32 por USB serie.

![Logotipo de PianoLED MIDI](assets/pianoled-logo.png)

## Características

- Entrada MIDI por USB y salida al ESP32 por USB serie de baja latencia.
- Mapeo editable de teclas a segmentos LED.
- Colores estáticos, por manos, arcoíris y gradiente de graves a agudos.
- Efectos de desvanecimiento y onda al pulsar notas.
- Control manual, piano virtual y configuración de orden RGB.

## Inicio rápido

### 1. Firmware ESP32

1. Copia `firmware/main/config.example.h` como `firmware/main/config.h`.
2. Edita esa copia con la configuración física de tu tira. Las credenciales Wi-Fi sólo se usan opcionalmente para actualizaciones OTA.
3. Abre `firmware/main/main.ino` en Arduino IDE.
4. Instala la biblioteca **FastLED**, selecciona **ESP32 Dev Module** y sube el firmware por USB.

`config.h` contiene datos privados y no se incluye en Git.

### 2. Programa Windows

Requiere Python 3.10–3.12.

```powershell
cd program
py -m pip install -e .
piano-led-midi-gui
```

En la pestaña MIDI selecciona el piano y el ESP32. Se recomienda USB serie para obtener la menor latencia.

### Bluetooth (opcional)

Los ESP32 clásicos pueden exponer **PianoLED MIDI** como Bluetooth serie (SPP). Tras subir el firmware, en Windows ve a **Configuración > Bluetooth y dispositivos > Agregar dispositivo > Bluetooth**, selecciona `PianoLED MIDI` e introduce el PIN `1234` (puedes cambiarlo en `config.h`). Windows creará un puerto COM; pulsa **Actualizar puertos** en la aplicación y selecciónalo.

Bluetooth es práctico sin cable, pero para interpretar MIDI rápido se recomienda el COM USB por su latencia más estable. Las variantes ESP32-C3, C6 y S3 no proporcionan Bluetooth clásico SPP; en ellas esta función se desactiva automáticamente.

## Estructura

```
firmware/   Código Arduino para el ESP32
program/    Aplicación de escritorio y pruebas Python
HARDWARE.md Guía de montaje y mejoras de hardware previstas
```

Consulta [HARDWARE.md](HARDWARE.md) antes de conectar una fuente externa a la tira.

## Licencia

Este proyecto se distribuye bajo [GNU GPL v3.0](LICENSE).
