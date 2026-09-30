"""Various MIDI constants and minor utilities."""
import io
from pathlib import Path
from typing import IO, Union

import mido

PathLike = Union[str, Path]
FileLike = Union[PathLike, IO]

MIDI_EXTENSIONS = (".mid", ".midi")
MIDRAW_YAML_EXTENSION = ".midraw.yaml"
MIDENSE_YAML_EXTENSION = ".midense.yaml"
MIDI_DEFAULT_TEMPO = 120.0
MIDI_DEFAULT_TIME_SIGNATURE = "4/4"

def load_mido(source: Union[PathLike, io.BytesIO]) -> mido.MidiFile:
    """Open a MIDI file and raise ValueError if its type/format is 2."""
    if isinstance(source, (str, Path)):
        midi = mido.MidiFile(str(source))
    else:
        midi = mido.MidiFile(file=source)
    if midi.type == 2:
        raise ValueError("MIDI format/type 2 is not supported")
    return midi
