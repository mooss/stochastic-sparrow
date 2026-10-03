"""Various MIDI constants and minor utilities."""
import io
from pathlib import Path
from typing import IO, Union

import mido

#######################
# Types and constants #

PathLike = Union[str, Path]
FileLike = Union[PathLike, IO]

MIDI_EXTENSIONS = (".mid", ".midi")
MIDRAW_YAML_EXTENSION = ".midraw.yaml"
MIDENSE_YAML_EXTENSION = ".midense.yaml"
MIDI_DEFAULT_TEMPO = 120.0
MIDI_DEFAULT_TIME_SIGNATURE = "4/4"


###########################
# Note <=> key conversion #

_NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note2key(name: str) -> int:
    """Convert a note name to a MIDI key number.

    Uses the convention of middle C as C4, so note_to_key("C4") == 60.
    Accepts names like C4, C#4, Db4.
    """
    s = name.strip()
    if not s:
        raise ValueError("note2key: empty note name")

    letter = s[0].upper()
    if letter not in _NOTE_OFFSETS:
        raise ValueError(f"note2key: invalid note name {name!r}")

    offset = _NOTE_OFFSETS[letter]
    rest = s[1:]

    accidental = 0
    if rest.startswith("#"):
        accidental = 1
        rest = rest[1:]
    elif rest.startswith("b"):
        accidental = -1
        rest = rest[1:]

    try:
        octave = int(rest)
    except ValueError:
        raise ValueError(f"note2key: invalid octave in note name {name!r}") from None

    key = (octave + 1) * 12 + offset + accidental

    if not 0 <= key <= 127:
        raise ValueError(f"note2key: resulting MIDI key {key} is out of range 0-127 for note name {name!r}")

    return key


def key2note(key: int) -> str:
    """Convert a MIDI key number to a note name.

    Uses the convention of middle C as C4, so key_to_note(60) == "C4".
    """
    if not 0 <= key <= 127:
        raise ValueError(f"key2note: key must be in range 0-127, got {key}")

    semitone = _NOTE_NAMES[key % 12]
    octave = key // 12 - 1
    return f"{semitone}{octave}"


###################
# Other functions #

def load_mido(source: Union[PathLike, io.BytesIO]) -> mido.MidiFile:
    """Open a MIDI file and raise ValueError if its type/format is 2."""
    if isinstance(source, (str, Path)):
        midi = mido.MidiFile(str(source))
    else:
        midi = mido.MidiFile(file=source)
    if midi.type == 2:
        raise ValueError("MIDI format/type 2 is not supported")
    return midi
