#include "serial_control.h"

#include <Arduino.h>

#include "config.h"
#include "leds.h"

namespace {
constexpr uint8_t FRAME_START = 0xA5;
constexpr uint8_t CMD_SET_RANGES = 0x21;
constexpr uint8_t CMD_SET_BRIGHTNESS = 0x22;
constexpr uint8_t CMD_CLEAR = 0x23;
constexpr uint8_t CMD_SET_LED_COUNT = 0x25;
constexpr uint8_t CMD_START_CENTER_WAVE = 0x26;
constexpr uint8_t CMD_START_NOTE_WAVE = 0x27;
constexpr uint8_t CMD_START_NOTE_FADE = 0x28;
constexpr uint8_t CMD_START_SWEEP = 0x29;
constexpr uint8_t CMD_START_RAINBOW = 0x2A;
constexpr uint8_t CMD_STOP_ANIMATION = 0x2B;
constexpr uint8_t MAX_PAYLOAD_SIZE = 250;

enum class ParseState : uint8_t { WaitStart, Command, Length, Payload, Checksum };
ParseState state = ParseState::WaitStart;
uint8_t command = 0;
uint8_t length = 0;
uint8_t payload[MAX_PAYLOAD_SIZE];
uint8_t position = 0;
uint8_t checksum = 0;

void reset_parser() { state = ParseState::WaitStart; }

void execute_frame() {
  switch (command) {
    case CMD_SET_RANGES:
      if (length > 0 && length % 5 == 0) {
        leds_stop_animation();
        leds_set_ranges(payload, length / 5);
      }
      break;
    case CMD_SET_BRIGHTNESS:
      if (length == 1) leds_set_brightness(payload[0]);
      break;
    case CMD_CLEAR:
      if (length == 0) {
        leds_stop_animation();
        leds_clear();
      }
      break;
    case CMD_SET_LED_COUNT:
      if (length == 1) leds_set_count(payload[0]);
      break;
    case CMD_START_CENTER_WAVE:
      if (length == 2) leds_start_center_wave((payload[0] << 8) | payload[1]);
      break;
    case CMD_START_NOTE_WAVE:
      if (length == 4) leds_start_note_wave(payload[0], payload[1], payload[2], payload[3]);
      else if (length == 6) leds_start_note_wave(payload[0], payload[1], payload[2], payload[3], (payload[4] << 8) | payload[5]);
      break;
    case CMD_START_NOTE_FADE:
      if (length == 7) leds_start_note_fade(payload[0], payload[1], payload[2], payload[3], payload[4], (payload[5] << 8) | payload[6]);
      break;
    case CMD_START_SWEEP:
      if (length == 5) leds_start_sweep(payload[0], payload[1], payload[2], (payload[3] << 8) | payload[4]);
      break;
    case CMD_START_RAINBOW:
      if (length == 2) leds_start_rainbow((payload[0] << 8) | payload[1]);
      break;
    case CMD_STOP_ANIMATION:
      if (length == 0) leds_stop_animation();
      break;
  }
}
}

void serial_control_begin() { Serial.begin(SERIAL_BAUD); }

void serial_control_handle() { serial_control_handle_stream(Serial); }

void serial_control_handle_stream(Stream& stream) {
  while (stream.available() > 0) {
    const uint8_t value = static_cast<uint8_t>(stream.read());
    switch (state) {
      case ParseState::WaitStart:
        if (value == FRAME_START) state = ParseState::Command;
        break;
      case ParseState::Command:
        command = value;
        checksum = value;
        state = ParseState::Length;
        break;
      case ParseState::Length:
        length = value;
        position = 0;
        checksum += value;
        if (length > MAX_PAYLOAD_SIZE) {
          reset_parser();
        } else {
          state = length == 0 ? ParseState::Checksum : ParseState::Payload;
        }
        break;
      case ParseState::Payload:
        payload[position++] = value;
        checksum += value;
        if (position == length) state = ParseState::Checksum;
        break;
      case ParseState::Checksum:
        if (value == checksum) execute_frame();
        reset_parser();
        break;
    }
  }
}
