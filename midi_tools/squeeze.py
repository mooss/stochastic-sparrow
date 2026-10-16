"""Extract selected MIDI data."""
import sys
from collections import Counter
from typing import Any, Iterator

import yaml

from midi_tools.mir import Mir
from midi_tools.utils import key2note


def _track_for_number(mir: Mir, track_number: int) -> list[Any]:
    """Return a selected track, or raise if its number is out of range."""
    if track_number < 0 or track_number >= len(mir.tracks):
        raise ValueError(
            f"track number {track_number} is out of range for a file with {len(mir.tracks)} tracks"
        )
    return mir.tracks[track_number]


def _keynums_from_track(track: list[Any]) -> Iterator[int]:
    """Return positive-velocity key numbers in event-time order."""
    absolute_tick = 0
    notes = []

    for message in track:
        absolute_tick += message.time
        if message.type == "note_on" and message.velocity > 0:
            notes.append((absolute_tick, message.note))

    notes.sort()
    return (keynum for _, keynum in notes)


def _interval_text(window: list[int]) -> str:
    """Return the space-separated intervals for a window of key numbers."""
    return " ".join(str(right - left) for left, right in zip(window, window[1:]))


def _count_for_window(keynums: list[int], window_size: int) -> Counter[str]:
    """Count interval windows of a given size in a list of key numbers."""
    counts: Counter[str] = Counter()
    for start in range(len(keynums) - window_size):
        window = keynums[start : start + window_size + 1]
        key = _interval_text(window)
        counts[key] += 1
    return counts


def squeeze_notes(mir: Mir, track_number: int) -> None:
    """Print the note names from a selected track as a YAML list."""
    keynums = _keynums_from_track(_track_for_number(mir, track_number))
    yaml.safe_dump(list(map(key2note, keynums)), sys.stdout)


def squeeze_intervals(mir: Mir, track_number: int, window_size: int) -> None:
    """Print counts of note intervals in sliding windows sorted by decreasing count."""
    if window_size < 1:
        raise ValueError("window size must be at least 1")

    keynums = list(_keynums_from_track(_track_for_number(mir, track_number)))
    counts = _count_for_window(keynums, window_size)

    sorted_counts = dict(counts.most_common())
    yaml.safe_dump(sorted_counts, sys.stdout, sort_keys=False)


def squeeze_multi_intervals(mir: Mir, track_number: int, max_window_size: int) -> None:
    """Print counts+weight for all window sizes 1..max_window_size sorted by decreasing weight."""
    if max_window_size < 1:
        raise ValueError("max window size must be at least 1")

    keynums = list(_keynums_from_track(_track_for_number(mir, track_number)))

    stats: dict[str, dict[str, int]] = {}
    for window_size in range(1, max_window_size + 1):
        counts = _count_for_window(keynums, window_size)
        for interval, occurences in counts.items():
            if occurences < 3: continue
            stats[interval] = {"occurrences": occurences, "weight": occurences * (window_size - 1)}

    sorted_stats = dict(sorted(stats.items(), key=lambda kv: kv[1]["weight"], reverse=True))
    yaml.safe_dump(sorted_stats, sys.stdout, sort_keys=False)
