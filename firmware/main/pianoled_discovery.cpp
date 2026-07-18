#include "pianoled_discovery.h"

#include <ESPmDNS.h>

#include "config.h"

void pianoled_discovery_begin() {
  if (!MDNS.begin(DEVICE_HOSTNAME)) {
    Serial.println("mDNS unavailable");
    return;
  }
  MDNS.addService("pianoled", "udp", UDP_PORT);
  Serial.print("mDNS ready: ");
  Serial.print(DEVICE_HOSTNAME);
  Serial.println(".local");
}
