#pragma once

#include <Arduino.h>

void leds_begin();
void leds_set(uint8_t index, uint8_t red, uint8_t green, uint8_t blue);
void leds_set_range(uint8_t start, uint8_t count, uint8_t red, uint8_t green, uint8_t blue);
void leds_set_ranges(const uint8_t* ranges, uint8_t range_count);
void leds_show_range(uint8_t start, uint8_t count, uint8_t red, uint8_t green, uint8_t blue);
void leds_set_frame(const uint8_t* rgb, uint16_t pixel_count);
void leds_set_count(uint8_t count);
void leds_start_sweep(uint8_t red, uint8_t green, uint8_t blue, uint16_t interval_ms);
void leds_start_rainbow(uint16_t interval_ms);
void leds_start_center_wave(uint16_t interval_ms);
void leds_start_note_wave(uint8_t start, uint8_t red, uint8_t green, uint8_t blue, uint16_t interval_ms = 14);
void leds_start_note_fade(uint8_t start, uint8_t count, uint8_t red, uint8_t green, uint8_t blue, uint16_t duration_ms);
void leds_stop_animation();
void leds_animation_handle();
void leds_set_brightness(uint8_t brightness);
void leds_clear();
void leds_fill(uint8_t red, uint8_t green, uint8_t blue);
uint16_t leds_count();
uint8_t leds_brightness();
