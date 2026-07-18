#include "leds.h"
#include "ota.h"
#include "pianoled_connection.h"
#include "pianoled_discovery.h"
#include "serial_control.h"
#include "udp.h"

#include <WiFi.h>

void setup() {
  serial_control_begin();
  delay(250);
  Serial.println();
  Serial.println("PianoLED booting");
  leds_begin();
  leds_startup_sequence();
  pianoled_connection_begin();

  Serial.print("Connecting to Wi-Fi");
  while (!pianoled_connection_is_ready()) {
    Serial.print('.');
    delay(1000);
  }
  Serial.println();
  Serial.print("Wi-Fi connected. IP: ");
  Serial.println(WiFi.localIP());

  ota_begin();
  udp_begin();
  pianoled_discovery_begin();
  Serial.println("UDP listening on port 4210");
  Serial.println("OTA ready");
}

void loop() {
  ota_handle();
  serial_control_handle();
  udp_handle();
  leds_animation_handle();
}
