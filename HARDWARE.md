# Hardware

## Montaje actual

- ESP32 Dev Module.
- Tira WS2812B / NeoPixel de 5 V conectada al pin de datos definido en `firmware/main/config.h`.
- Fuente de 5 V dimensionada para la cantidad de LEDs instalada.
- Masa (GND) común entre la fuente, la tira y el ESP32.

## Recomendaciones para un montaje definitivo

1. Alimenta la tira directamente desde una fuente de 5 V; no desde el USB del ESP32.
2. Añade un condensador electrolítico de al menos 1000 µF entre 5 V y GND al inicio de la tira.
3. Añade una resistencia de 330–470 Ω en serie con la línea de datos, cerca de la tira.
4. Para mayor fiabilidad, usa un conversor de nivel lógico de 3,3 V a 5 V (por ejemplo 74AHCT125).
5. Inyecta alimentación en más de un punto para tiras largas, usando cable adecuado y respetando polaridades.

Desconecta la alimentación antes de modificar el cableado. Comprueba siempre que la masa sea común antes de encender la tira.
