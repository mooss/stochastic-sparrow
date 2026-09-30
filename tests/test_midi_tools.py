import mido
import pytest
import yaml

from midi_tools.conversion import convert
from midi_tools.mir import Mir

###################
# Roundtrip tests #
###################

def test_yaml_manual_roundtrip(partition):
    """YAML -> MIDI -> YAML must preserve the data exactly."""
    midi = Mir.from_dict(partition).to_mido()
    roundtrip_data = Mir.from_mido(midi).to_dict()
    assert roundtrip_data == partition

###############
# Stats tests #
###############

def test_stats_format_and_tracks(partition, tmp_path):
    """Stats should report format 1 and 2 tracks (excluding control track)."""
    # Convert YAML to MIDI and save to temp file
    midi = Mir.from_dict(partition).to_mido()
    midi_path = tmp_path / "test.mid"
    midi.save(str(midi_path))

    stats = Mir.from_disk(midi_path).stats()
    assert stats["format"] == 1
    assert stats["ntracks"] == 2


def test_stats_tempo_and_time_signature(partition, tmp_path):
    """Stats should contain tempo 60 BPM and time signature 4/4."""
    midi = Mir.from_dict(partition).to_mido()
    midi_path = tmp_path / "test.mid"
    midi.save(str(midi_path))

    stats = Mir.from_disk(midi_path).stats()
    assert stats["bpm"] == [60.0]  # 60,000,000 / 1,000,000
    assert stats["time_signatures"] == ["4/4"]


def test_stats_track_info(partition, tmp_path):
    """Track names and program names should be correct."""
    midi = Mir.from_dict(partition).to_mido()
    midi_path = tmp_path / "test.mid"
    midi.save(str(midi_path))

    stats = Mir.from_disk(midi_path).stats()
    tracks = stats["tracks"]
    assert len(tracks) == 2
    assert tracks[0]["name"] == "upper"
    assert tracks[0]["program"] == 6
    assert tracks[0]["program_name"] == "Harpsichord"
    assert tracks[1]["name"] == "lower"
    assert tracks[1]["program"] == 6
    assert tracks[1]["program_name"] == "Harpsichord"
    assert tracks[0]["has_percussions"] == False
    assert tracks[1]["has_percussions"] == False


def test_stats_percussion_track_info(tmp_path):
    """Channel-10 notes should flag the track as having percussions."""
    midi = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="drums", time=0))
    track.append(mido.Message("note_on", note=38, velocity=100, time=0, channel=9))
    track.append(mido.Message("note_on", note=35, velocity=100, time=0, channel=9))
    track.append(mido.Message("note_off", note=35, velocity=0, time=10, channel=9))
    track.append(mido.Message("note_off", note=38, velocity=0, time=10, channel=9))
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)

    midi_path = tmp_path / "drums.mid"
    midi.save(str(midi_path))

    stats = Mir.from_disk(midi_path).stats()
    assert stats["tracks"][0]["has_percussions"] == True


def test_stats_defaults_without_meta(tmp_path):
    """Missing tempo/time-signature meta should use documented defaults."""
    midi = mido.MidiFile(type=0)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="test", time=0))
    track.append(mido.Message("note_on", note=60, velocity=100, time=0, channel=0))
    track.append(mido.Message("note_off", note=60, velocity=64, time=100, channel=0))
    track.append(mido.MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)

    midi_path = tmp_path / "simple.mid"
    midi.save(str(midi_path))

    stats = Mir.from_mido(midi).stats()
    assert stats["bpm"] == [120.0]
    assert stats["time_signatures"] == ["4/4"]
    assert stats["format"] == 0
    assert stats["ntracks"] == 1


def test_stats_rejects_type_2(tmp_path):
    """Type 2 MIDI files are unsupported and should raise ValueError."""
    midi = mido.MidiFile(type=2)
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name="async", time=0))
    track.append(mido.MetaMessage("end_of_track", time=1))
    midi.tracks.append(track)

    midi_path = tmp_path / "async.mid"
    midi.save(str(midi_path))

    with pytest.raises(ValueError):
        Mir.from_mido(midi).stats()


####################
# Conversion tests #
####################

def test_convert_yaml_to_midi_and_back(partition, tmp_path):
    """Convert YAML->MIDI and MIDI->YAML should produce identical YAML."""
    yaml_path = tmp_path / "input.midraw.yaml"
    midi_path = tmp_path / "output.mid"
    yaml_out_path = tmp_path / "output.midraw.yaml"

    # Write YAML data to file
    with open(yaml_path, "w") as f:
        yaml.safe_dump(partition, f)

    # YAML -> MIDI
    mir = Mir.from_disk(yaml_path)
    mir.to_mido().save(str(midi_path))

    # MIDI -> YAML
    mir2 = Mir.from_disk(midi_path)
    with open(yaml_out_path, "w") as f:
        yaml.safe_dump(mir2.to_dict(), f)

    # Compare YAML contents
    with open(yaml_out_path) as f:
        result = yaml.safe_load(f)
    assert result == partition


def test_convert_midi_to_midi_format_0(partition, tmp_path):
    """MIDI -> MIDI conversion should be able to change format to 0."""
    yaml_path = tmp_path / "input.midraw.yaml"
    midi_path = tmp_path / "output.mid"
    midi0_path = tmp_path / "output0.mid"

    with open(yaml_path, "w") as f:
        yaml.safe_dump(partition, f)

    mir = Mir.from_disk(yaml_path)
    mir.to_mido().save(str(midi_path))

    mir2 = Mir.from_disk(midi_path)
    mir2.midi_format = 0
    mir2.to_mido().save(str(midi0_path))

    midi = mido.MidiFile(str(midi0_path))
    assert midi.type == 0
    assert len(midi.tracks) == 1


###############
# Merge tests #
###############

def test_partition_to_midi_format_0_merges_tracks(partition):
    """Requesting format 0 should produce a single merged track."""
    midi = Mir.from_dict(partition).set_midi_format(0).to_mido()
    assert midi.type == 0
    assert len(midi.tracks) == 1


def test_merge_tracks_meta_before_note_at_same_time():
    """At the same absolute tick, meta events must precede note events."""
    control = mido.MidiTrack()
    control.append(mido.MetaMessage("track_name", name="control", time=0))
    control.append(mido.MetaMessage("set_tempo", tempo=500000, time=10))
    control.append(mido.MetaMessage("end_of_track", time=0))

    notes = mido.MidiTrack()
    notes.append(mido.MetaMessage("track_name", name="notes", time=0))
    notes.append(mido.Message("note_on", note=60, velocity=100, time=10, channel=0))
    notes.append(mido.Message("note_off", note=60, velocity=64, time=10, channel=0))
    notes.append(mido.MetaMessage("end_of_track", time=0))

    mir = Mir(midi_format=1, ticks_per_beat=480, tracks=[control, notes])
    merged = mir.merge_tracks().tracks[0]

    abs_time = 0
    seen = []
    for msg in merged:
        abs_time += msg.time
        seen.append((abs_time, msg.type))

    tempo_index = seen.index((10, "set_tempo"))
    note_on_index = seen.index((10, "note_on"))
    assert tempo_index < note_on_index

#############
# Mir tests #
#############

def test_mir_rejects_unknown_extension(tmp_path):
    """Unsupported input extensions should raise ValueError."""
    input_path = tmp_path / "input.txt"
    input_path.write_text("not midi")

    with pytest.raises(ValueError):
        Mir.from_disk(input_path)


def test_mir_rejects_plain_yaml_extension(tmp_path):
    """Generic .yaml is not a dialect; the extension must be .midraw.yaml/.midense.yaml."""
    path = tmp_path / "input.yaml"
    path.write_text("ticks_per_beat: 480\n")
    with pytest.raises(ValueError):
        Mir.from_disk(path)


################
# Dense tests #
################

def test_dense_roundtrip_stable(partition):
    """dense -> Mir -> dense must be stable."""
    dense = Mir.from_dict(partition).to_dense()
    assert Mir.from_dense(dense).to_dense() == dense


def test_dense_unknown_command_raises():
    dense = {"ticks_per_beat": 480, "tracks": [{"channel": 0, "events": ["0 foo 1"]}]}
    with pytest.raises(ValueError, match="unknown event command"):
        Mir.from_dense(dense)


def test_dense_rejects_non_format_1(partition):
    mir = Mir.from_dict(partition).set_midi_format(0)
    with pytest.raises(ValueError, match="format 1"):
        mir.to_dense()


def test_convert_raw_to_dense(partition, tmp_path):
    raw_path = tmp_path / "song.midraw.yaml"
    dense_path = tmp_path / "song.midense.yaml"
    with open(raw_path, "w") as f:
        yaml.safe_dump(partition, f)
    original = Mir.from_disk(raw_path)
    convert(str(raw_path), str(dense_path))
    assert Mir.from_disk(dense_path).to_dense() == original.to_dense()


def test_dense_port_event_roundtrip():
    """A midi_port meta event should survive a dense roundtrip."""
    raw = {
        "midi_format": 1,
        "ticks_per_beat": 480,
        "tracks": [
            [
                {"type": "midi_port", "port": 3, "time": 0},
                {"type": "end_of_track", "time": 0},
            ],
            [
                {"type": "track_name", "name": "Test", "time": 0},
                {"type": "end_of_track", "time": 0},
            ],
        ],
    }

    mir = Mir.from_dict(raw)
    dense = mir.to_dense()
    assert Mir.from_dense(dense).to_dict() == raw
