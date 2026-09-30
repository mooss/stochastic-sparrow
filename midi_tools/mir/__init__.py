"""MIDI Intermediate Representation (Mir)."""
from enum import Enum
from pathlib import Path
from typing import Any, Dict, IO, List, Optional

import mido
import yaml

from midi_tools.constants import MIDI_PROGRAMS
from midi_tools.mir.dense import dense_to_raw, raw_to_dense
from midi_tools.utils import (
    MIDI_DEFAULT_TEMPO,
    MIDI_DEFAULT_TIME_SIGNATURE,
    MIDI_EXTENSIONS,
    MIDENSE_YAML_EXTENSION,
    MIDRAW_YAML_EXTENSION,
    FileLike,
    PathLike,
    load_mido,
)

# MIDI channel 10 is 1-based; mido channel numbers are 0-based.
PERCUSSION_CHANNEL = 9


class MirDialect(Enum):
    MIDI = 1
    RAWYAML = 2
    DENSEYAML = 3


def path_to_dialect(path: PathLike) -> Optional[MirDialect]:
    """Return the Mir dialect implied by the file name, or None if unknown."""
    name = Path(path).name.lower()
    if name.endswith(MIDENSE_YAML_EXTENSION):
        return MirDialect.DENSEYAML
    if name.endswith(MIDRAW_YAML_EXTENSION):
        return MirDialect.RAWYAML
    if Path(path).suffix.lower() in MIDI_EXTENSIONS:
        return MirDialect.MIDI
    return None


def save_midi(data: mido.MidiFile, destination: FileLike) -> None:
    """Save a MidiFile to a path or file-like object."""
    if isinstance(destination, (str, Path)):
        data.save(str(destination))
    else:
        data.save(file=destination)


def save_midyaml(data: Dict[str, Any], destination: FileLike) -> None:
    """Save a Mir dictionary as YAML to a path or file-like object."""
    if isinstance(destination, (str, Path)):
        with open(str(destination), "w") as f:
            yaml.safe_dump(data, f)
    else:
        yaml.safe_dump(data, destination)


class Mir:
    """Canonical in-memory MIDI representation used by all operations."""

    @property
    def midi_format(self) -> int:
        """Return the MIDI file format (0 or 1)."""
        return self._midi_format

    @midi_format.setter
    def midi_format(self, value: int) -> None:
        """Set the MIDI file format, converting tracks when changing to format 0."""
        if value == 2: raise ValueError("MIDI format/type 2 is not supported")
        if value not in (0, 1): raise ValueError(f"Invalid MIDI format {value}, only 0 and 1 are valid and supported")

        previous = getattr(self, "_midi_format", None)
        if previous == value:
            return
        if previous == 1 and value == 0:
            self.tracks = self.merge_tracks().tracks
        elif previous == 0 and value == 1:
            raise NotImplementedError("conversion from MIDI format 0 to format 1 is not implemented")
        self._midi_format = value

    def set_midi_format(self, value: int) -> "Mir":
        """Set the MIDI format and return this Mir for chaining."""
        self.midi_format = value
        return self

    def __init__(
        self,
        midi_format: int,
        ticks_per_beat: int,
        tracks: List[List[Any]],
    ) -> None:
        self.midi_format = midi_format
        self.ticks_per_beat = ticks_per_beat
        self.tracks = tracks

    ##########################
    # from_... class methods #

    @classmethod
    def from_disk(cls, path: PathLike) -> "Mir":
        """Load a Mir from a MIDI or YAML file on disk."""
        match path_to_dialect(path):
            case MirDialect.MIDI:
                return Mir.from_mido(load_mido(path))
            case MirDialect.RAWYAML:
                with open(path) as f:
                    return Mir.from_dict(yaml.safe_load(f))
            case MirDialect.DENSEYAML:
                with open(path) as f:
                    return Mir.from_dense(yaml.safe_load(f))

        raise ValueError(f"from_disk: cannot deduce Mir format from filename: {path}")


    @classmethod
    def from_mido(cls, midi: mido.MidiFile) -> "Mir":
        """Create a Mir from a mido.MidiFile."""
        tracks = [[msg.copy() for msg in track] for track in midi.tracks]
        return cls(midi.type, midi.ticks_per_beat, tracks)


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mir":
        """Create a Mir from a dictionary representation."""
        tracks = []
        for track_data in data["tracks"]:
            track = []
            for msg_dict in track_data:
                try:
                    track.append(mido.Message(**msg_dict))
                except LookupError:
                    track.append(mido.MetaMessage(**msg_dict))
            tracks.append(track)
        return cls(data.get("midi_format", 1), data["ticks_per_beat"], tracks)

    @classmethod
    def from_dense(cls, data: Dict[str, Any]) -> "Mir":
        """Create a Mir from a dense dictionary representation."""
        return cls.from_dict(dense_to_raw(data))

    ##################
    # to_... methods #

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of this Mir."""
        return {
            "midi_format": self.midi_format,
            "ticks_per_beat": self.ticks_per_beat,
            "tracks": [[msg.dict() for msg in track] for track in self.tracks],
        }

    def to_dense(self) -> Dict[str, Any]:
        """Return a dense dictionary representation of this Mir."""
        return raw_to_dense(self.to_dict())


    def to_mido(self) -> mido.MidiFile:
        """Return a mido.MidiFile representation of this Mir."""
        midi = mido.MidiFile(type=self.midi_format, ticks_per_beat=self.ticks_per_beat)
        midi.tracks = [self._to_midi_track(track) for track in self.tracks]
        return midi


    def to_disk(self, path: PathLike) -> None:
        """Write this Mir to disk as MIDI or YAML based on the file extension."""
        match path_to_dialect(path):
            case MirDialect.MIDI:
                save_midi(self.to_mido(), path)
            case MirDialect.RAWYAML:
                save_midyaml(self.to_dict(), path)
            case MirDialect.DENSEYAML:
                save_midyaml(self.to_dense(), path)
            case _:
                raise ValueError(f"to_disk: cannot deduce Mir format from filename: {path}")


    def to_io(self, file: IO, dialect: MirDialect) -> None:
        """Write this Mir to a file-like object in the given dialect."""
        match dialect:
            case MirDialect.MIDI:
                save_midi(self.to_mido(), file)
            case MirDialect.RAWYAML:
                save_midyaml(self.to_dict(), file)
            case MirDialect.DENSEYAML:
                save_midyaml(self.to_dense(), file)

    ##############
    # Operations #

    def merge_tracks(self) -> "Mir":
        """Return a new Mir with all tracks merged into one, sorted by tick.
        """
        if not self.tracks:
            return Mir(0, self.ticks_per_beat, [[]])
        if len(self.tracks) == 1:
            return Mir(self.midi_format, self.ticks_per_beat, [self.tracks[0]])

        events = []
        max_end_time = 0

        for track_index, track in enumerate(self.tracks):
            abs_time = 0
            for msg in track:
                abs_time += msg.time
                if msg.type == "end_of_track":
                    max_end_time = max(max_end_time, abs_time)
                else:
                    events.append((abs_time, track_index, msg))

        events.sort(key=lambda item: (item[0], 0 if item[2].is_meta else 1, item[1]))

        merged = []
        current_time = 0
        for abs_time, _, msg in events:
            merged.append(msg.copy(time=abs_time - current_time))
            current_time = abs_time

        end_time = max(0, max_end_time - current_time)
        merged.append(mido.MetaMessage("end_of_track", time=end_time))
        return Mir(0, self.ticks_per_beat, [merged])


    def stats(self) -> Dict[str, Any]:
        """Compute statistics entirely from this Mir."""
        tempos = []
        time_signatures = []

        for msg in self.merge_tracks().tracks[0]:
            if msg.type == "set_tempo":
                tempos.append(round(60_000_000 / msg.tempo, 2))
            elif msg.type == "time_signature":
                ts = f"{msg.numerator}/{msg.denominator}"
                if ts not in time_signatures:
                    time_signatures.append(ts)

        tracks = self.tracks
        if self.midi_format == 1:
            tracks = tracks[1:]
        ntracks = len(tracks)

        return {
            "format": self.midi_format,
            "ntracks": ntracks,
            "duration": self.to_mido().length,
            "bpm": tempos or [MIDI_DEFAULT_TEMPO],
            "time_signatures": time_signatures or [MIDI_DEFAULT_TIME_SIGNATURE],
            "tracks": [self._track_info(track) for track in tracks],
        }

    ######################
    # Private workhorses #

    @staticmethod
    def _track_info(track: List[Any]) -> Dict[str, Any]:
        """Return the name, program, program name, and percussion for a track."""
        name = None
        program = None
        has_percussions = False
        for msg in track:
            if msg.type == "track_name" and name is None:
                name = msg.name
            elif msg.type == "program_change" and program is None:
                program = msg.program
            elif msg.type == "note_on" and getattr(msg, "channel", None) == PERCUSSION_CHANNEL:
                has_percussions = True
        return {
            "name": name,
            "program": program,
            "program_name": MIDI_PROGRAMS.get(program) if program is not None else None,
            "has_percussions": has_percussions,
        }


    @staticmethod
    def _to_midi_track(track: List[Any]) -> mido.MidiTrack:
        """Convert a list of messages into a mido.MidiTrack."""
        midi_track = mido.MidiTrack()
        for msg in track:
            midi_track.append(msg.copy())
        return midi_track
