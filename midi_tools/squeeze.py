"""Extract selected MIDI data."""
import sys

import yaml

from midi_tools.mir import Mir
from midi_tools.utils import key2note


def _keynums_from_track(track):
    """Return positive-velocity key numbers in event-time order."""
    absolute_tick = 0
    notes = []

    for message in track:
        absolute_tick += message.time
        if message.type == "note_on" and message.velocity > 0:
            notes.append((absolute_tick, message.note))

    notes.sort()
    return (keynum for _, keynum in notes)


def squeeze_notes(mir: Mir, track_number: int) -> None:
    """Print the note names from a selected track as a YAML list."""
    if track_number < 0 or track_number >= len(mir.tracks):
        raise ValueError(
            f"track number {track_number} is out of range for a file with "
            f"{len(mir.tracks)} tracks"
        )

    keynums = _keynums_from_track(mir.tracks[track_number])
    yaml.safe_dump(list(map(key2note, keynums)), sys.stdout)
