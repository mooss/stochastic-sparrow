import pytest

from midi_tools.mir.dense import _raw_to_dense_track


def test_unclosed_note_is_closed_at_end_of_track_with_warning():
    track = [
        {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
        {"type": "end_of_track", "time": 24},
    ]

    with pytest.warns(RuntimeWarning, match=r"end_of_track at tick 24 implicitly closed 1 pending note\(s\)"):
        dense_track = _raw_to_dense_track(track)

    assert dense_track["events"] == ["C4 at 0 for 24", "24 eot"]


def test_multiple_pending_notes_are_closed_at_same_end_of_track():
    track = [
        {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
        {"type": "note_on", "time": 10, "channel": 0, "note": 62, "velocity": 64},
        {"type": "end_of_track", "time": 20},
    ]

    with pytest.warns(RuntimeWarning, match=r"end_of_track at tick 30 implicitly closed 2 pending note\(s\)"):
        dense_track = _raw_to_dense_track(track)

    assert dense_track["events"] == [
        "C4 at 0 for 30",
        "D4 at 10 for 20",
        "20 eot",
    ]


def test_unclosed_note_without_end_of_track_still_raises_value_error():
    track = [
        {"type": "note_on", "time": 0, "channel": 0, "note": 60, "velocity": 64},
    ]

    with pytest.raises(ValueError, match="unmatched note onset"):
        _raw_to_dense_track(track)
