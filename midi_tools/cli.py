"""MIDI tools command-line interface."""
import argparse
import sys
import yaml
from typing import Optional, Sequence

from .conversion import convert
from .mir import Mir
from .cmd.roundtrip import roundtrip
from .squeeze import squeeze_intervals, squeeze_notes

################
# Registration #

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Convert MIDI <-> YAML.")
    sub = parser.add_subparsers(dest="command", required=True)

    register_conv(sub)
    register_squeeze(sub)
    register_others(sub)

    return parser


def register_conv(sub):
    p_conv = sub.add_parser("conv", help="Convert between MIDI and YAML based on file extensions")
    p_conv.add_argument("input_file")
    p_conv.add_argument("output_file")
    p_conv.add_argument("--format", type=int, choices=[0, 1], default=1,
                        help="MIDI format/type of the output MIDI file (default: 1, 2 is not supported)")


def register_squeeze(sub):
    p_squeeze = sub.add_parser("squeeze", help="Extract selected MIDI data")
    squeeze_sub = p_squeeze.add_subparsers(dest="squeeze_command", required=True)

    p_notes = squeeze_sub.add_parser("notes", help="Output notes from one track")
    p_notes.add_argument("--from", dest="input_file", required=True,
                         help="Input MIDI, .midraw.yaml, or .midense.yaml file")
    p_notes.add_argument("--track", type=int, required=True,
                         help="Zero-based track number")

    p_intervals = squeeze_sub.add_parser("intervals", help="Output counts of note intervals from one track")
    p_intervals.add_argument("--from", dest="input_file", required=True,
                             help="Input MIDI, .midraw.yaml, or .midense.yaml file")
    p_intervals.add_argument("--track", type=int, required=True,
                             help="Zero-based track number")
    p_intervals.add_argument("--window-size", "-s", type=int, required=True,
                             help="Number of intervals in each interval window")


def register_others(sub):
    p_stats = sub.add_parser("stats", help="Show statistics for a MIDI file")
    p_stats.add_argument("input_file")

    p_test = sub.add_parser("_test", help=argparse.SUPPRESS)
    test_sub = p_test.add_subparsers(dest="test_command", required=True)
    p_test_conv = test_sub.add_parser("conv", help="Run roundtrip conversion tests")
    p_test_conv.add_argument("input_file")


############
# Dispatch #

def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI, returning a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        if args.command == "conv":
            convert(args.input_file, args.output_file, midi_format=args.format)
        elif args.command == "stats":
            print(yaml.safe_dump(Mir.from_disk(args.input_file).stats()))
        elif args.command == "_test":
            if args.test_command == "conv":
                roundtrip(args.input_file)
        elif args.command == "squeeze":
            if args.squeeze_command == "notes":
                squeeze_notes(Mir.from_disk(args.input_file), args.track)
            elif args.squeeze_command == "intervals":
                squeeze_intervals(Mir.from_disk(args.input_file), args.track, args.window_size)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0
