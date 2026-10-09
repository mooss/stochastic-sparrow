import pytest

from midi_tools.mir.dense import raw_to_dense


def _raw_data(*messages):
    return {
        "midi_format": 1,
        "ticks_per_beat": 480,
        "tracks": [list(messages)],
    }


def test_note_on_and_off_are_fused():
    dense = raw_to_dense({
        "midi_format": 1,
        "ticks_per_beat": 480,
        "tracks": [[
            {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
            {"type": "note_off", "time": 480, "channel": 0, "note": 60, "velocity": 0},
            {"type": "end_of_track", "time": 0},
        ]],
    })

    assert dense["tracks"][0]["events"] == [
        "C4 at 0 for 480",
        "480 eot",
    ]


def test_fused_note_keeps_nondefault_velocity_and_channel():
    dense = raw_to_dense({
        "midi_format": 1,
        "ticks_per_beat": 480,
        "tracks": [[
            {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
            {"type": "note_off", "time": 120, "channel": 0, "note": 60, "velocity": 0},
            {"type": "note_on", "time": 0, "channel": 1, "note": 62, "velocity": 90},
            {"type": "note_off", "time": 120, "channel": 1, "note": 62, "velocity": 12},
            {"type": "end_of_track", "time": 0},
        ]],
    })

    assert dense["tracks"][0]["events"] == [
        "C4 at 0 for 120",
        "D4 at 120 !90 for 120 !12 @1",
        "120 eot",
    ]


def test_overlapping_same_pitch_notes_pair_in_fifo_order():
    dense = raw_to_dense(_raw_data(
        {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
        {"type": "note_on", "time": 10, "channel": 0, "note": 60, "velocity": 64},
        {"type": "note_off", "time": 10, "channel": 0, "note": 60, "velocity": 0},
        {"type": "note_off", "time": 10, "channel": 0, "note": 60, "velocity": 0},
        {"type": "end_of_track", "time": 0},
    ))

    assert dense["tracks"][0]["events"] == [
        "C4 at 0 for 20",
        "C4 at 10 for 20",
        "20 eot",
    ]


def test_zero_velocity_note_on_is_fused_as_note_off():
    dense = raw_to_dense(_raw_data(
        {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
        {"type": "note_on", "time": 480, "channel": 0, "note": 60, "velocity": 0},
        {"type": "end_of_track", "time": 0},
    ))

    assert dense["tracks"][0]["events"] == [
        "C4 at 0 for 480",
        "480 eot",
    ]


def test_same_pitch_notes_on_different_channels_pair_independently():
    dense = raw_to_dense(_raw_data(
        {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
        {"type": "note_on", "time": 0, "channel": 1, "note": 60, "velocity": 64},
        {"type": "note_off", "time": 100, "channel": 1, "note": 60, "velocity": 0},
        {"type": "note_off", "time": 0, "channel": 0, "note": 60, "velocity": 0},
        {"type": "end_of_track", "time": 0},
    ))

    assert dense["tracks"][0]["events"] == [
        "C4 at 0 for 100",
        "C4 at 0 for 100 @1",
        "100 eot",
    ]


def test_unmatched_note_off_raises():
    with pytest.raises(ValueError, match="unmatched note offset"):
        raw_to_dense(_raw_data(
            {"type": "note_off", "time": 0, "channel": 0, "note": 60, "velocity": 0},
        ))


def test_unmatched_note_on_raises():
    with pytest.raises(ValueError, match="unmatched note onset"):
        raw_to_dense(_raw_data(
            {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
        ))
