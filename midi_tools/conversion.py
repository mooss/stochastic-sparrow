"""Conversion functions between MIDI, YAML, and rendered audio representations."""
from pathlib import Path

from .audio import render_audio
from .mir import Mir, path_to_dialect
from .utils import PathLike

def convert(input_path: PathLike, output_path: PathLike, midi_format: int = 1) -> None:
    """Convert between MIDI/YAML or render MIDI/YAML to WAV/OGG."""
    in_path = Path(input_path)
    out_path = Path(output_path)
    if in_path.resolve() == out_path.resolve():
        raise ValueError("Input and output files must be different")

    input_dialect = path_to_dialect(in_path)
    if input_dialect is None:
        raise ValueError(
            f"Conversion from WAV/OGG or other unsupported input formats is not supported: "
            f"{in_path}"
        )

    if out_path.suffix.lower() in (".wav", ".ogg"):
        render_audio(in_path, out_path, input_dialect)
        return

    Mir.from_disk(in_path).set_midi_format(midi_format).to_disk(out_path)
