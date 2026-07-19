import unittest

from piano_led.key_mapping import range_for_key
from piano_led.midi_agent import CHORD_COALESCE_SECONDS, FIRST_MIDI_NOTE, STATE_RESYNC_SECONDS, MidiLedAgent, MidiLedState


class MidiLedStateTests(unittest.TestCase):
    def test_latency_guardrails_are_short(self):
        self.assertLessEqual(CHORD_COALESCE_SECONDS, 0.002)
        self.assertLessEqual(STATE_RESYNC_SECONDS, 0.03)

    def test_note_on_paints_its_key_range(self):
        state = MidiLedState((255, 255, 255))
        state.note_on(FIRST_MIDI_NOTE, 127)
        frame = state.frame()
        first_key = range_for_key(1)
        self.assertTrue(all(frame[index] == (255, 255, 255) for index in range(first_key.led_start, first_key.led_end)))
        self.assertEqual(frame[first_key.led_end], (0, 0, 0))

    def test_default_color_is_uniform_across_a_key(self):
        state = MidiLedState((80, 160, 240))
        state.note_on(FIRST_MIDI_NOTE, 20)
        key = range_for_key(1)
        self.assertTrue(all(state.frame()[index] == (80, 160, 240) for index in range(key.led_start, key.led_end)))

    def test_velocity_mode_is_optional(self):
        state = MidiLedState((255, 255, 255), velocity_sensitive=True)
        state.note_on(FIRST_MIDI_NOTE, 64)
        self.assertEqual(state.frame()[range_for_key(1).led_start], (65, 65, 65))

    def test_range_update_only_covers_the_note_key(self):
        state = MidiLedState((10, 20, 30))
        state.note_on(FIRST_MIDI_NOTE, 127)
        first_key = range_for_key(1)
        self.assertEqual(state.range_update(FIRST_MIDI_NOTE), (first_key.led_start, 4, 10, 20, 30))
        state.note_off(FIRST_MIDI_NOTE)
        self.assertEqual(state.range_update(FIRST_MIDI_NOTE), (first_key.led_start, 4, 0, 0, 0))

    def test_start_runs_the_center_wave_and_clears_the_strip(self):
        class Client:
            requires_state_resync = False

            def __init__(self): self.led_count = None; self.wave = False; self.cleared = False
            def info(self): pass
            def set_led_count(self, count): self.led_count = count
            def start_center_wave(self): self.wave = True
            def clear(self): self.cleared = True
            def close(self): pass

        client = Client()
        agent = MidiLedAgent(client, (255, 255, 255))
        agent.start()
        self.assertEqual(client.led_count, 198)
        self.assertTrue(client.wave)
        self.assertTrue(client.cleared)
        agent.close()

    def test_wave_mode_queues_a_wave_for_a_pressed_note(self):
        class Client:
            requires_state_resync = False

        agent = MidiLedAgent(Client(), (255, 255, 255), effect_mode="wave")
        class Message:
            type = "note_on"
            note = FIRST_MIDI_NOTE
            velocity = 100
        agent.handle_message(Message())
        self.assertTrue(agent._pending_waves)

    def test_midi_through_forwards_before_led_processing(self):
        class Output:
            def __init__(self): self.messages = []
            def send(self, message): self.messages.append(message)

        class Message:
            type = "note_on"
            note = FIRST_MIDI_NOTE
            velocity = 100

        output = Output()
        agent = MidiLedAgent(object(), (255, 255, 255))
        agent.set_midi_through(output)
        message = Message()
        agent.handle_message(message)
        self.assertEqual(output.messages, [message])

    def test_chord_keeps_both_notes_lit(self):
        state = MidiLedState((255, 255, 255))
        state.note_on(60, 127)
        state.note_on(64, 127)
        state.note_off(60)
        frame = state.frame()
        self.assertEqual(frame[range_for_key(60 - FIRST_MIDI_NOTE + 1).led_start], (0, 0, 0))
        self.assertEqual(frame[range_for_key(64 - FIRST_MIDI_NOTE + 1).led_start], (255, 255, 255))

    def test_sustain_holds_then_releases_note(self):
        state = MidiLedState((255, 255, 255))
        state.note_on(60, 127)
        state.set_sustain(True)
        state.note_off(60)
        key = range_for_key(60 - FIRST_MIDI_NOTE + 1)
        self.assertEqual(state.frame()[key.led_start], (255, 255, 255))
        state.set_sustain(False)
        self.assertEqual(state.frame()[key.led_start], (0, 0, 0))
