import pytest
import yaml

from midi_tools.mir import Mir
from midi_tools.squeeze import squeeze_notes


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
