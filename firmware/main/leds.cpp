#include "leds.h"

#include <FastLED.h>
#include <Preferences.h>

#include "config.h"

namespace {
CRGB pixels[MAX_LED_COUNT];
uint8_t active_led_count = LED_COUNT;
uint8_t current_brightness = LED_BRIGHTNESS;
enum class Animation : uint8_t { None, Sweep, Rainbow, CenterWave };
Animation active_animation = Animation::None;
uint8_t sweep_red = 0;
uint8_t sweep_green = 0;
uint8_t sweep_blue = 0;
uint16_t sweep_index = 0;
uint16_t sweep_interval_ms = 55;
uint32_t sweep_last_step_ms = 0;
uint8_t rainbow_hue = 0;
uint16_t wave_left = 0;
uint16_t wave_right = 0;
constexpr uint8_t MAX_NOTE_WAVES = 8;
uint16_t note_wave_step_ms = 14;
constexpr uint8_t NOTE_WAVE_FADE_STEP = 2;
struct NoteWave { bool active; int16_t left; int16_t right; uint8_t red; uint8_t green; uint8_t blue; uint8_t step; };
NoteWave note_waves[MAX_NOTE_WAVES] = {};
uint32_t note_wave_last_step_ms = 0;
constexpr uint8_t MAX_NOTE_FADES = 16;
struct NoteFade { bool active; uint8_t start; uint8_t count; uint8_t red; uint8_t green; uint8_t blue; uint32_t started_ms; uint16_t duration_ms; };
NoteFade note_fades[MAX_NOTE_FADES] = {};

void cancel_note_fades(uint8_t start, uint8_t count) {
  const uint16_t end = static_cast<uint16_t>(start) + count;
  for (NoteFade& fade : note_fades) {
    if (!fade.active) continue;
    const uint16_t fade_end = static_cast<uint16_t>(fade.start) + fade.count;
    if (start < fade_end && fade.start < end) fade.active = false;
  }
}
}

void leds_begin() {
  Preferences preferences;
  preferences.begin("pianoled", true);
  active_led_count = preferences.getUChar("led_count", LED_COUNT);
  preferences.end();
  if (active_led_count == 0 || active_led_count > MAX_LED_COUNT) active_led_count = LED_COUNT;
  FastLED.addLeds<WS2812B, LED_PIN, LED_COLOR_ORDER>(pixels, MAX_LED_COUNT);
  FastLED.setBrightness(current_brightness);
  leds_clear();
}

void leds_set(uint8_t index, uint8_t red, uint8_t green, uint8_t blue) {
  if (index >= active_led_count) return;
  pixels[index] = CRGB(red, green, blue);
  FastLED.show();
}

void leds_set_range(uint8_t start, uint8_t count, uint8_t red, uint8_t green, uint8_t blue) {
  if (start >= active_led_count || count == 0) return;
  cancel_note_fades(start, count);
  const uint16_t requested_end = static_cast<uint16_t>(start) + count;
  const uint16_t end = requested_end > active_led_count ? active_led_count : requested_end;
  for (uint16_t index = start; index < end; ++index) {
    pixels[index] = CRGB(red, green, blue);
  }
  FastLED.show();
}

void leds_set_ranges(const uint8_t* ranges, uint8_t range_count) {
  for (uint8_t range_index = 0; range_index < range_count; ++range_index) {
    const uint8_t* range = ranges + range_index * 5;
    const uint8_t start = range[0];
    const uint8_t count = range[1];
    if (start >= active_led_count || count == 0) continue;
    cancel_note_fades(start, count);
    const uint16_t requested_end = static_cast<uint16_t>(start) + count;
    const uint16_t end = requested_end > active_led_count ? active_led_count : requested_end;
    for (uint16_t index = start; index < end; ++index) {
      pixels[index] = CRGB(range[2], range[3], range[4]);
    }
  }
  FastLED.show();
}

void leds_show_range(uint8_t start, uint8_t count, uint8_t red, uint8_t green, uint8_t blue) {
  fill_solid(pixels, MAX_LED_COUNT, CRGB::Black);
  if (start < active_led_count && count > 0) {
    const uint16_t requested_end = static_cast<uint16_t>(start) + count;
    const uint16_t end = requested_end > active_led_count ? active_led_count : requested_end;
    for (uint16_t index = start; index < end; ++index) {
      pixels[index] = CRGB(red, green, blue);
    }
  }
  FastLED.show();
}

void leds_set_frame(const uint8_t* rgb, uint16_t pixel_count) {
  if (pixel_count != active_led_count) return;
  for (NoteFade& fade : note_fades) fade.active = false;
  for (uint16_t index = 0; index < active_led_count; ++index) {
    const uint16_t offset = index * 3;
    pixels[index] = CRGB(rgb[offset], rgb[offset + 1], rgb[offset + 2]);
  }
  FastLED.show();
}

void leds_set_count(uint8_t count) {
  if (count == 0 || count > MAX_LED_COUNT) return;
  active_led_count = count;
  Preferences preferences;
  preferences.begin("pianoled", false);
  preferences.putUChar("led_count", count);
  preferences.end();
  fill_solid(pixels, MAX_LED_COUNT, CRGB::Black);
  FastLED.show();
}

void leds_start_sweep(uint8_t red, uint8_t green, uint8_t blue, uint16_t interval_ms) {
  sweep_red = red;
  sweep_green = green;
  sweep_blue = blue;
  sweep_interval_ms = interval_ms < 8 ? 8 : interval_ms;
  sweep_index = 0;
  sweep_last_step_ms = 0;
  active_animation = Animation::Sweep;
}

void leds_start_rainbow(uint16_t interval_ms) {
  sweep_interval_ms = interval_ms < 8 ? 8 : interval_ms;
  rainbow_hue = 0;
  sweep_last_step_ms = 0;
  active_animation = Animation::Rainbow;
}

void leds_start_center_wave(uint16_t interval_ms) {
  sweep_interval_ms = interval_ms < 8 ? 8 : interval_ms;
  wave_left = (active_led_count - 1) / 2;
  wave_right = active_led_count / 2;
  sweep_last_step_ms = 0;
  active_animation = Animation::CenterWave;
}

void leds_start_note_wave(uint8_t start, uint8_t red, uint8_t green, uint8_t blue, uint16_t interval_ms) {
  uint8_t selected = 0;
  for (uint8_t index = 0; index < MAX_NOTE_WAVES; ++index) {
    if (!note_waves[index].active) { selected = index; break; }
    if (note_waves[index].step > note_waves[selected].step) selected = index;
  }
  note_waves[selected] = {true, start, start, red, green, blue, 0};
  note_wave_step_ms = interval_ms < 8 ? 8 : interval_ms;
  note_wave_last_step_ms = 0;
}

void leds_start_note_fade(uint8_t start, uint8_t count, uint8_t red, uint8_t green, uint8_t blue, uint16_t duration_ms) {
  if (start >= active_led_count || count == 0) return;
  uint8_t selected = 0;
  for (uint8_t index = 0; index < MAX_NOTE_FADES; ++index) {
    if (!note_fades[index].active) { selected = index; break; }
    if (note_fades[index].started_ms < note_fades[selected].started_ms) selected = index;
  }
  note_fades[selected] = {true, start, count, red, green, blue, millis(), duration_ms < 50 ? 50 : duration_ms};
}

void leds_stop_animation() { active_animation = Animation::None; }

void leds_animation_handle() {
  const uint32_t now = millis();
  bool has_note_wave = false;
  for (const NoteWave& wave : note_waves) has_note_wave = has_note_wave || wave.active;
  if (has_note_wave && now - note_wave_last_step_ms >= note_wave_step_ms) {
    note_wave_last_step_ms = now;
    fill_solid(pixels, active_led_count, CRGB::Black);
    for (NoteWave& wave : note_waves) {
      if (!wave.active) continue;
      const uint16_t reduction = wave.step * NOTE_WAVE_FADE_STEP;
      const uint8_t brightness = reduction >= 255 ? 0 : 255 - reduction;
      const CRGB color((wave.red * brightness) / 255, (wave.green * brightness) / 255, (wave.blue * brightness) / 255);
      if (wave.left >= 0) pixels[wave.left] += color;
      if (wave.right < active_led_count) pixels[wave.right] += color;
      --wave.left;
      ++wave.right;
      ++wave.step;
      if (wave.left < 0 && wave.right >= active_led_count) wave.active = false;
    }
    FastLED.show();
    bool waves_remaining = false;
    for (const NoteWave& wave : note_waves) waves_remaining = waves_remaining || wave.active;
    if (!waves_remaining) leds_clear();
    return;
  }
  bool fade_changed = false;
  for (NoteFade& fade : note_fades) {
    if (!fade.active) continue;
    const uint32_t elapsed = now - fade.started_ms;
    const uint8_t level = elapsed >= fade.duration_ms ? 0 : 255 - (elapsed * 255UL) / fade.duration_ms;
    uint16_t end = static_cast<uint16_t>(fade.start) + fade.count;
    if (end > active_led_count) end = active_led_count;
    for (uint16_t index = fade.start; index < end; ++index) {
      pixels[index] = CRGB((fade.red * level) / 255, (fade.green * level) / 255, (fade.blue * level) / 255);
    }
    if (elapsed >= fade.duration_ms) fade.active = false;
    fade_changed = true;
  }
  if (fade_changed) {
    FastLED.show();
    return;
  }
  if (active_animation == Animation::None) return;
  if (now - sweep_last_step_ms < sweep_interval_ms) return;

  sweep_last_step_ms = now;
  if (active_animation == Animation::Sweep) {
    leds_show_range(sweep_index, 2, sweep_red, sweep_green, sweep_blue);
    sweep_index = active_led_count < 2 || sweep_index >= active_led_count - 2 ? 0 : sweep_index + 1;
  } else if (active_animation == Animation::Rainbow) {
    fill_rainbow(pixels, active_led_count, rainbow_hue, 255 / active_led_count);
    FastLED.show();
    ++rainbow_hue;
  } else {
    fill_solid(pixels, active_led_count, CRGB::Black);
    pixels[wave_left] = CRGB::White;
    pixels[wave_right] = CRGB::White;
    FastLED.show();
    if (wave_left == 0 && wave_right == active_led_count - 1) {
      active_animation = Animation::None;
      leds_clear();
    } else {
      if (wave_left > 0) --wave_left;
      if (wave_right < active_led_count - 1) ++wave_right;
    }
  }
}

void leds_clear() {
  fill_solid(pixels, MAX_LED_COUNT, CRGB::Black);
  FastLED.show();
}

void leds_fill(uint8_t red, uint8_t green, uint8_t blue) {
  fill_solid(pixels, active_led_count, CRGB(red, green, blue));
  FastLED.show();
}

uint16_t leds_count() { return active_led_count; }
void leds_set_brightness(uint8_t brightness) {
  current_brightness = brightness;
  FastLED.setBrightness(current_brightness);
  FastLED.show();
}

uint8_t leds_brightness() { return current_brightness; }
