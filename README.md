# PianoLED MIDI

Aplicación de escritorio Windows para visualizar un piano MIDI en una tira de LEDs WS2812B. El ordenador recibe MIDI por USB, decide los colores y efectos, y envía los comandos al ESP32 por USB serie o Wi-Fi.

![Logotipo de PianoLED MIDI](assets/pianoled-logo.png)

## Características

- Entrada MIDI por USB y salida al ESP32 por USB serie o Wi-Fi.
- Mapeo editable de teclas a segmentos LED.
- Colores estáticos, por manos, arcoíris y gradiente de graves a agudos.
- Efectos de desvanecimiento y onda al pulsar notas.
- Control manual, piano virtual y configuración de orden RGB.

## Inicio rápido

### 1. Firmware ESP32

1. Copia `firmware/main/config.example.h` como `firmware/main/config.h`.
2. Edita esa copia con tu Wi-Fi y la configuración física de tu tira.
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

## Estructura

```
firmware/   Código Arduino para el ESP32
program/    Aplicación de escritorio y pruebas Python
HARDWARE.md Guía de montaje y mejoras de hardware previstas
```

Consulta [HARDWARE.md](HARDWARE.md) antes de conectar una fuente externa a la tira.

## Licencia

Este proyecto se distribuye bajo [GNU GPL v3.0](LICENSE).
