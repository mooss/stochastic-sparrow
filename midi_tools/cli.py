"""MIDI tools command-line interface."""
import argparse
import sys
import yaml
from typing import Optional, Sequence

from .conversion import convert
from .mir import Mir
from .cmd.roundtrip import roundtrip
from .notes import notes_intervals, notes_multi_intervals, notes_single

################
# Registration #

def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Convert MIDI <-> YAML.")
    sub = parser.add_subparsers(dest="command", required=True)

    register_conv(sub)
    register_notes(sub)
    register_others(sub)

    return parser


def register_conv(sub):
    p_conv = sub.add_parser("conv", help="Convert between MIDI and YAML based on file extensions")
    p_conv.add_argument("input_file")
    p_conv.add_argument("output_file")
    p_conv.add_argument("--format", type=int, choices=[0, 1], default=1,
                        help="MIDI format/type of the output MIDI file (default: 1, 2 is not supported)")


def register_notes(sub):
    p_notes = sub.add_parser("notes", help="Extract note data from MIDI")
    notes_sub = p_notes.add_subparsers(dest="notes_command", required=True)

    p_notes = notes_sub.add_parser("single", help="Sequentially prints notes")
    p_notes.add_argument("--from", dest="input_file", required=True,
                         help="Input MIDI, .midraw.yaml, or .midense.yaml file")
    p_notes.add_argument("--track", type=int, required=True,
                         help="Zero-based track number")

    p_intervals = notes_sub.add_parser("intervals", help="Print sorted counts of note intervals")
    p_intervals.add_argument("--from", dest="input_file", required=True,
                             help="Input MIDI, .midraw.yaml, or .midense.yaml file")
    p_intervals.add_argument("--track", type=int, required=True,
                             help="Zero-based track number")
    p_intervals.add_argument("--window-size", "-s", type=int, required=True,
                             help="Number of intervals in each interval window")

    p_multinters = notes_sub.add_parser("multi-intervals", help="Print sorted counts of note intervals for all window sizes up to max")
    p_multinters.add_argument("--from", dest="input_file", required=True,
                              help="Input MIDI, .midraw.yaml, or .midense.yaml file")
    p_multinters.add_argument("--track", type=int, required=True,
                              help="Zero-based track number")
    p_multinters.add_argument("--max-window-size", "-s", type=int, required=True,
                              help="Maximum number of intervals in each interval window")


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
        elif args.command == "notes":
            if args.notes_command == "single":
                notes_single(Mir.from_disk(args.input_file), args.track)
            elif args.notes_command == "intervals":
                notes_intervals(Mir.from_disk(args.input_file), args.track, args.window_size)
            elif args.notes_command == "multi-intervals":
                notes_multi_intervals(Mir.from_disk(args.input_file), args.track, args.max_window_size)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0
