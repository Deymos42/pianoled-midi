#include "ota.h"

#include <ArduinoOTA.h>

#include "config.h"

void ota_begin() {
  ArduinoOTA.setHostname(DEVICE_HOSTNAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.begin();
}

void ota_handle() { ArduinoOTA.handle(); }
