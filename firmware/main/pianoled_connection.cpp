#include "pianoled_connection.h"

#include <WiFi.h>

#include "config.h"

void pianoled_connection_begin() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(DEVICE_HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

bool pianoled_connection_is_ready() { return WiFi.status() == WL_CONNECTED; }
