# Dense MIDI Format (`.midense.yaml`)

A compact, human-editable YAML serialization of a MIDI file.
It mirrors a **format-1** MIDI file (the only format supported): one global resolution value plus a list of tracks, where each track is a flat list of one-line event strings.

## File structure

```yaml
ticks_per_beat: 384        # Required; PPQ resolution.
tracks:
- channel: 0               # Required; default mido channel (0–15).
  velocity_on: 100         # Required for tracks with notes; default onset velocity.
  velocity_off: 0          # Optional but should be provided for clarity; defaults to 0.
  events:
  - 0 track_name upper
  - 0 pc 6
  - C4 at 192 !127 for 192 !64
  - 0 eot
```

## Event syntax

Most events use:

```
<delta-time> <command> [args...]
```

 - **delta-time**: nonnegative integer ticks since the previous input event in the same track; `0` means simultaneous.
 - **command**: keyword mapping to a MIDI message (see below).
 - Numeric args are space-separated integers.
 - Text values are taken from the remainder after the command separator.
   Internal text spaces are retained, but separator whitespace is not part of the value.

Note events use the fused note syntax described in [Fused notes](#fused-note-events).

## Channel events

| Command | MIDI message     | Arguments       |
|---------|------------------|-----------------|
| `pt`    | `polytouch`      | `note value`    |
| `cc`    | `control_change` | `control value` |
| `pc`    | `program_change` | `program`       |
| `at`    | `aftertouch`     | `value`         |
| `pw`    | `pitchwheel`     | `pitch`         |

Channels use mido's zero-based numbering: `0`–`15`.
Events use the track's `channel` by default; append `@N` as the last argument to override it for a single event, e.g. `0 cc 7 100 @3`.

Note-on and note-off events are represented by the fused note syntax described below.

## Fused note events

Notes are written as a single fused event that encodes both the note-on and note-off:

```
<NOTE> at <onset_delta> [!<on_velocity>] for <duration> [!<off_velocity>] [@<channel>]
```

 - **NOTE**: uppercase note letter A–G, optionally followed by `#`, then an octave number (e.g. `C4`, `F#3`, `Db4`).
   The resulting MIDI key must be in the range 0–127, corresponding to C-1 through G9.
 - **onset_delta**: nonnegative integer ticks from the preceding input event's onset/time.
 - **on_velocity** (optional): note-on velocity.
   If omitted, uses the track's `velocity_on` default.
   Must be between 1 and 127.
 - **duration**: nonnegative integer ticks between note-on and note-off.
 - **off_velocity** (optional): note-off velocity.
   If omitted, uses the track's `velocity_off` default (which defaults to `0`).
   Must be between 0 and 127.
 - **channel** (optional): override the track's default `channel` for this note.

Track-level defaults can be set with `velocity_on` and `velocity_off` keys:

```yaml
tracks:
- channel: 0
  velocity_on: 100
  velocity_off: 64
  events:
  - C4 at 0 for 480
```

Additional notes:
 - Fused note events do not start with a delta time, unlike all other events.
   Their `onset_delta` is the third token, after `at`.
 - A fused note's duration does not advance the input-event timing cursor.
   The timing cursor is advanced by the value of `onset_delta`.
   For instance the event `C4 at 20 for 480` advances the timing cursor of 20, not of 480 and not of 500.
 - Parsing expands fused notes into MIDI messages and sorts the resulting messages by time.
 - Fused notes always use note names, never key numbers (like `127`), even on drum tracks.

## Meta events

 - `eot`: end of track
 - `sx <b0> <b1> ...`: SysEx, bytes as space-separated integers
 - **Text** (remainder of the line): `text`, `copyright`, `lyrics`, `marker`, `cue`
 - **String meta** (remainder of the line): `track_name`, `instrument_name`, `device_name`, `key_signature` (e.g. `0 key_signature C`)
 - **Integer meta** (fixed argument lists):
   - `set_tempo <tempo>`: microseconds per quarter note
   - `time_signature <num> <den> <clocks_per_click> <notated_32nds>`: e.g. `0 time_signature 4 4 18 8`
   - `smpte_offset <frame_rate> <hours> <minutes> <seconds> <frames> <sub_frames>`
   - `sequence_number <n>`, `channel_prefix <ch>`, `midi_port <port>` (or the alias `port <n>`)
 - `sequencer_specific <b0> <b1> ...`

## Practical notes

 - **Editing timing:** since times are deltas, inserting or removing an event means adjusting the following event's delta; simultaneous events (chords) chain with `0`.
   For fused notes, `onset_delta` is relative to the preceding input event's onset/time, and `duration` is independent; the note-off does not advance the input-event timing cursor.
 - **YAML quoting:** quote any event string containing `:` or leading/trailing spaces.
 - **Typical track layout:** track 0 is a conductor track with `time_signature` / `set_tempo`; each instrument track starts with `track_name`, `pc`, `instrument_name`, `key_signature`, then fused notes, and ends with `eot`.
   Set `velocity_on` / `velocity_off` defaults to shorten fused note events and for clarity.
 - **Validation and note pairing:** deltas and durations must be nonnegative.
   Unknown commands, wrong argument counts, and non-integer values trigger an error.
   An unmatched note-off is an error.
   An unmatched note-on is closed at an `end_of_track` event, with a warning; if there is no such event, it is an error.
