import pytest
import yaml

from midi_tools.mir import Mir
from midi_tools.squeeze import squeeze_intervals, squeeze_notes


def test_squeeze_notes_track_zero(partition, capsys):
    mir = Mir.from_dict(partition)

    squeeze_notes(mir, 1)

    notes = yaml.safe_load(capsys.readouterr().out)
    assert notes[:10] == [
        "C4",
        "E4",
        "G4",
        "E4",
        "C4",
        "A#4",
        "G4",
        "A4",
        "C4",
        "F4",
    ]


def test_squeeze_notes_track_one(partition, capsys):
    mir = Mir.from_dict(partition)

    squeeze_notes(mir, 2)

    notes = yaml.safe_load(capsys.readouterr().out)
    assert notes[:2] == ["C2", "C3"]


@pytest.mark.parametrize("track_number", [-1, "track_count"])
def test_squeeze_notes_rejects_invalid_track(partition, track_number):
    mir = Mir.from_dict(partition)
    if track_number == "track_count":
        track_number = len(mir.tracks)

    with pytest.raises(ValueError, match="out of range"):
        squeeze_notes(mir, track_number)


def test_squeeze_intervals_output_is_sorted(partition, capsys):
    mir = Mir.from_dict(partition)

    squeeze_intervals(mir, 1, 2)

    intervals = yaml.safe_load(capsys.readouterr().out)
    counts = list(intervals.values())
    assert counts == sorted(counts, reverse=True)


@pytest.mark.parametrize("window_size", [0, -1])
def test_squeeze_intervals_rejects_invalid_window_size(partition, window_size):
    mir = Mir.from_dict(partition)

    with pytest.raises(ValueError, match="window size"):
        squeeze_intervals(mir, 1, window_size)


@pytest.mark.parametrize("track_number", [-1, "track_count"])
def test_squeeze_intervals_rejects_invalid_track(partition, track_number):
    mir = Mir.from_dict(partition)
    if track_number == "track_count":
        track_number = len(mir.tracks)

    with pytest.raises(ValueError, match="out of range"):
        squeeze_intervals(mir, track_number, 2)
