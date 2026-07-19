#include "bluetooth.h"
#include "leds.h"
#include "ota.h"
#include "pianoled_connection.h"
#include "serial_control.h"

void setup() {
  serial_control_begin();
  delay(250);
  Serial.println();
  Serial.println("PianoLED booting");
  leds_begin();
  leds_startup_sequence();
  pianoled_connection_begin();
  bluetooth_begin();

  Serial.println("USB serial ready");
  Serial.println("Wi-Fi is optional and reserved for OTA updates");
}

void loop() {
  static bool ota_ready = false;
  if (!ota_ready && pianoled_connection_is_ready()) {
    ota_begin();
    ota_ready = true;
    Serial.println("OTA ready");
  }
  if (ota_ready) ota_handle();
  serial_control_handle();
  bluetooth_handle();
  leds_animation_handle();
}
