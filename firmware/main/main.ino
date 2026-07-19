#include "bluetooth.h"
#include "leds.h"
#include "serial_control.h"

void setup() {
  serial_control_begin();
  leds_begin();
  bluetooth_begin();
}

void loop() {
  serial_control_handle();
  bluetooth_handle();
  leds_animation_handle();
}
