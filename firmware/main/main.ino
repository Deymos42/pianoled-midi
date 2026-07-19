#include "bluetooth.h"
#include "leds.h"
#include "ota.h"
#include "pianoled_connection.h"
#include "serial_control.h"

void setup() {
  serial_control_begin();
  leds_begin();
  pianoled_connection_begin();
  bluetooth_begin();
}

void loop() {
  static bool ota_ready = false;
  if (!ota_ready && pianoled_connection_is_ready()) {
    ota_begin();
    ota_ready = true;
  }
  if (ota_ready) ota_handle();
  serial_control_handle();
  bluetooth_handle();
  leds_animation_handle();
}
