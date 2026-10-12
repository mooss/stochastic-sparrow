# Stochastic sparrow: learning music composition from examples

## Python setup

Run `make setup` to create a virtual environment and install dependencies.

Activate the environment:
```
source .venv/bin/activate
```

## MIDI <-> YAML conversion

`midi.py conv` converts between MIDI and YAML and vice-versa, giving some means to visualize MIDI data as text.
The conversion direction is deduced from the file extensions of the input and output files.

Recognized extensions:

- `.mid`, `.midi`: MIDI
- `.midraw.yaml`: raw YAML, one entry per MIDI message
- `.midense.yaml`: dense YAML, a compact human-editable form (see `docs/dense-format.md`)

Usage:
- `midi.py conv input.midi output.midraw.yaml`: MIDI to raw YAML.
- `midi.py conv input.midraw.yaml output.midi`: raw YAML to MIDI.
- `midi.py conv input.midi output.midi --format 0`: convert MIDI to MIDI with format 0.
- `midi.py _test conv input_file`: verify roundtrip conversion.

Conversion can be achieved from and to all the 3 formats (MIDI, raw and dense).

`--format` selects the MIDI format of the output file, accepts `0` or `1`, and defaults to `1`.
MIDI format 2 is not supported.
Converting from format 1 to format 0 merges all tracks into a single track; the reverse conversion, from format 0 to format 1, is not implemented.

## MIDI/YAML to audio

Audio conversion is one-way: MIDI and YAML inputs can be rendered to WAV or OGG. WAV and OGG are output formats only; they are not supported as inputs.

Examples:
- `midi.py conv input.midi output.wav`
- `midi.py conv input.midraw.yaml output.ogg`
- `midi.py conv input.middense.yaml output.wav`

Audio rendering requires:
- `fluidsynth`
- `ffmpeg` with `libvorbis` support (for OGG output)
- The soundfont at `/usr/share/soundfonts/FluidR3_GM.sf2`
