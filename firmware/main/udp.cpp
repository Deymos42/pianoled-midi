#include "udp.h"

#include <WiFiUdp.h>

#include "config.h"
#include "leds.h"

namespace {
constexpr uint8_t CMD_SET_LED = 0x01;
constexpr uint8_t CMD_CLEAR = 0x02;
constexpr uint8_t CMD_FILL = 0x03;
constexpr uint8_t CMD_PING = 0x04;
constexpr uint8_t RESP_PONG = 0x05;
constexpr uint8_t CMD_INFO = 0x06;
constexpr uint8_t RESP_INFO = 0x07;
constexpr uint8_t CMD_SET_RANGE = 0x08;
constexpr uint8_t CMD_SET_FRAME = 0x09;
constexpr uint8_t CMD_SHOW_RANGE = 0x0A;
constexpr uint8_t CMD_START_SWEEP = 0x0B;
constexpr uint8_t CMD_STOP_ANIMATION = 0x0C;
constexpr uint8_t CMD_START_RAINBOW = 0x0D;
constexpr uint8_t CMD_SET_BRIGHTNESS = 0x0E;
constexpr uint8_t RESP_ACK = 0x0F;
constexpr uint8_t CMD_BEGIN_REALTIME_SESSION = 0x10;
constexpr uint8_t CMD_SHOW_RANGE_REALTIME = 0x11;
constexpr uint8_t CMD_SET_FRAME_REALTIME = 0x12;
constexpr uint8_t CMD_SET_RANGES_REALTIME = 0x13;
constexpr uint8_t CMD_SET_LED_COUNT = 0x14;
constexpr uint8_t CMD_START_CENTER_WAVE = 0x15;
constexpr uint8_t CMD_START_NOTE_WAVE = 0x16;
constexpr size_t MAX_PACKET_SIZE = 600;

WiFiUDP server;
uint16_t realtime_session = 0;
uint16_t last_realtime_sequence = 0;
bool realtime_session_active = false;
bool realtime_sequence_seen = false;

bool sequence_is_new(uint16_t sequence) {
  return !realtime_sequence_seen || static_cast<int16_t>(sequence - last_realtime_sequence) > 0;
}

void reply(const uint8_t* data, size_t size) {
  server.beginPacket(server.remoteIP(), server.remotePort());
  server.write(data, size);
  server.endPacket();
}

void send_info() {
  const char* hostname = DEVICE_HOSTNAME;
  const size_t host_length = strnlen(hostname, 32);
  uint8_t response[5 + 32] = {RESP_INFO, FIRMWARE_VERSION, 0, 0, leds_brightness()};
  const uint16_t count = leds_count();
  response[2] = count >> 8;
  response[3] = count & 0xFF;
  memcpy(response + 5, hostname, host_length);
  reply(response, 5 + host_length);
}
}

void udp_begin() { server.begin(UDP_PORT); }

void udp_handle() {
  const int received = server.parsePacket();
  if (received <= 0) return;

  uint8_t packet[MAX_PACKET_SIZE];
  const size_t length = server.read(packet, min(received, static_cast<int>(MAX_PACKET_SIZE)));
  if (length == 0) return;

  switch (packet[0]) {
    case CMD_SET_LED:
      if (length == 5) { leds_stop_animation(); leds_set(packet[1], packet[2], packet[3], packet[4]); }
      break;
    case CMD_CLEAR:
      if (length == 1) { leds_stop_animation(); leds_clear(); }
      break;
    case CMD_FILL:
      if (length == 4) { leds_stop_animation(); leds_fill(packet[1], packet[2], packet[3]); }
      break;
    case CMD_PING:
      if (length == 1) { const uint8_t pong[] = {RESP_PONG}; reply(pong, sizeof(pong)); }
      break;
    case CMD_INFO:
      if (length == 1) send_info();
      break;
    case CMD_SET_RANGE:
      if (length == 6) { leds_stop_animation(); leds_set_range(packet[1], packet[2], packet[3], packet[4], packet[5]); }
      break;
    case CMD_SET_FRAME:
      if (length == 1 + leds_count() * 3) { leds_stop_animation(); leds_set_frame(packet + 1, leds_count()); }
      break;
    case CMD_SHOW_RANGE:
      if (length == 6) {
        leds_stop_animation();
        leds_show_range(packet[1], packet[2], packet[3], packet[4], packet[5]);
        const uint8_t ack[] = {RESP_ACK, CMD_SHOW_RANGE};
        reply(ack, sizeof(ack));
      }
      break;
    case CMD_START_SWEEP:
      if (length == 6) leds_start_sweep(packet[1], packet[2], packet[3], (packet[4] << 8) | packet[5]);
      break;
    case CMD_STOP_ANIMATION:
      if (length == 1) leds_stop_animation();
      break;
    case CMD_START_RAINBOW:
      if (length == 3) leds_start_rainbow((packet[1] << 8) | packet[2]);
      break;
    case CMD_SET_BRIGHTNESS:
      if (length == 2) leds_set_brightness(packet[1]);
      break;
    case CMD_BEGIN_REALTIME_SESSION:
      if (length == 3) {
        realtime_session = (packet[1] << 8) | packet[2];
        realtime_session_active = true;
        realtime_sequence_seen = false;
      }
      break;
    case CMD_SHOW_RANGE_REALTIME:
      if (length == 10) {
        const uint16_t session = (packet[1] << 8) | packet[2];
        const uint16_t sequence = (packet[3] << 8) | packet[4];
        if (realtime_session_active && session == realtime_session && sequence_is_new(sequence)) {
          realtime_sequence_seen = true;
          last_realtime_sequence = sequence;
          leds_stop_animation();
          leds_show_range(packet[5], packet[6], packet[7], packet[8], packet[9]);
        }
      }
      break;
    case CMD_SET_FRAME_REALTIME:
      if (length == 5 + leds_count() * 3) {
        const uint16_t session = (packet[1] << 8) | packet[2];
        const uint16_t sequence = (packet[3] << 8) | packet[4];
        if (realtime_session_active && session == realtime_session && sequence_is_new(sequence)) {
          realtime_sequence_seen = true;
          last_realtime_sequence = sequence;
          leds_stop_animation();
          leds_set_frame(packet + 5, leds_count());
        }
      }
      break;
    case CMD_SET_RANGES_REALTIME:
      if (length >= 10 && (length - 5) % 5 == 0) {
        const uint16_t session = (packet[1] << 8) | packet[2];
        const uint16_t sequence = (packet[3] << 8) | packet[4];
        if (realtime_session_active && session == realtime_session && sequence_is_new(sequence)) {
          realtime_sequence_seen = true;
          last_realtime_sequence = sequence;
          leds_stop_animation();
          leds_set_ranges(packet + 5, (length - 5) / 5);
        }
      }
      break;
    case CMD_SET_LED_COUNT:
      if (length == 2) leds_set_count(packet[1]);
      break;
    case CMD_START_CENTER_WAVE:
      if (length == 3) leds_start_center_wave((packet[1] << 8) | packet[2]);
      break;
    case CMD_START_NOTE_WAVE:
      if (length == 5) leds_start_note_wave(packet[1], packet[2], packet[3], packet[4]);
      break;
  }
}
