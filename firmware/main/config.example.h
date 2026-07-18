#pragma once

// Copy this file to config.h. config.h is deliberately excluded from Git.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

#define DEVICE_HOSTNAME "pianoled"
#define OTA_PASSWORD "change-this-password"

#define LED_PIN 25
#define LED_COUNT 198
#define MAX_LED_COUNT 255
#define LED_BRIGHTNESS 255
// Use GRB for a standard WS2812B; set RGB only if your installed strip needs it.
#define LED_COLOR_ORDER BGR
#define FIRMWARE_VERSION 13
#define UDP_PORT 4210
#define SERIAL_BAUD 921600
