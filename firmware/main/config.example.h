#pragma once

// Copy this file to config.h. config.h is deliberately excluded from Git.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

#define DEVICE_HOSTNAME "pianoled"
#define OTA_PASSWORD "change-this-password"

// Bluetooth Classic SPP. Windows exposes the paired device as a COM port.
#define BLUETOOTH_DEVICE_NAME "PianoLED MIDI"
#define BLUETOOTH_PIN "1234"

#define LED_PIN 25
#define LED_COUNT 198
#define MAX_LED_COUNT 255
#define LED_BRIGHTNESS 255
// Use GRB for a standard WS2812B; set RGB only if your installed strip needs it.
#define LED_COLOR_ORDER BGR
#define FIRMWARE_VERSION 13
#define SERIAL_BAUD 921600
