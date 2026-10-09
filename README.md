# Stochastic sparrow: learning music composition from examples

## Python setup

Run `scripts/setup-venv.sh` to create a virtual environment and install dependencies.

Activate the environment:
```
source .venv/bin/activate
```

## MIDI <-> YAML conversion

`midi.py` converts from MIDI to YAML and vice-versa, giving some mean to visualize MIDI data as text.

Usage:
- `midi.py conv input.midi output.yaml`
- `midi.py conv input.yaml output.midi`
- `midi.py conv input.midi output.midi --format 0`  # convert MIDI to MIDI with format 0
- `midi.py roundtrip input_file`   # verifies roundtrip conversion

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
