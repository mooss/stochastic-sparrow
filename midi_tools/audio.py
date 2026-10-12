from pathlib import Path
import subprocess
import tempfile

from .mir import Mir, MirDialect

SOUNDFONT_PATH = "/usr/share/soundfonts/FluidR3_GM.sf2"


def _raise_command_error(command, exc) -> None:
    raise RuntimeError(f"command failed ({' '.join(command)}): {exc}") from exc


def _run_command(*command: str) -> None:
    """Run a command, translating execution failures into CLI-friendly errors."""
    try:
        subprocess.run(command, check=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout.decode(errors="replace"), end="")
        _raise_command_error(command, exc)
    except OSError as exc:
        _raise_command_error(command, exc)


def _midi2wav(midi_input, wav_output):
    _run_command("fluidsynth", "--quiet", "-F", str(wav_output), SOUNDFONT_PATH, str(midi_input))

def render_audio(
    input_path: Path,
    output_path: Path,
    input_dialect: MirDialect,
) -> None:
    """Render a MIDI or YAML input to WAV or OGG using external audio tools."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)

        if input_dialect is MirDialect.MIDI:
            midi_path = input_path
        else:
            midi_path = temporary_path / "input.mid"
            Mir.from_disk(input_path).to_mido().save(str(midi_path))

        if output_path.suffix.lower() == ".wav":
            _midi2wav(midi_path, output_path)
            return

        wav_path = temporary_path / "output.wav"
        _midi2wav(midi_path, wav_path)
        _run_command("ffmpeg", "-y", "-i", str(wav_path), "-acodec", "libvorbis", str(output_path), "-q:a", "5")
