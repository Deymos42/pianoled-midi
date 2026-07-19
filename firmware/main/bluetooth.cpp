#include "bluetooth.h"

#include <Arduino.h>

#if defined(CONFIG_BT_ENABLED) && defined(CONFIG_BLUEDROID_ENABLED)
#include <BluetoothSerial.h>

#include "config.h"
#include "serial_control.h"

namespace {
BluetoothSerial bluetooth_serial;
#ifndef BLUETOOTH_DEVICE_NAME
#define BLUETOOTH_DEVICE_NAME "PianoLED MIDI"
#endif
#ifndef BLUETOOTH_PIN
#define BLUETOOTH_PIN "1234"
#endif
}

void bluetooth_begin() {
  bluetooth_serial.begin(BLUETOOTH_DEVICE_NAME);
  bluetooth_serial.setPin(BLUETOOTH_PIN);
  Serial.print("Bluetooth SPP ready: ");
  Serial.println(BLUETOOTH_DEVICE_NAME);
}

void bluetooth_handle() { serial_control_handle_stream(bluetooth_serial); }
bool bluetooth_available() { return true; }

#else

void bluetooth_begin() { Serial.println("Bluetooth Classic is not available on this ESP32 variant"); }
void bluetooth_handle() {}
bool bluetooth_available() { return false; }

#endif
