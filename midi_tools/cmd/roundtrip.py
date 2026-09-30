"""Roundtrip conversion command."""
from ..mir import Mir, MirDialect, path_to_dialect
from ..utils import load_mido

import yaml

def _load_mir_and_baseline(path):
    dialect = path_to_dialect(path)
    if dialect is None:
        raise ValueError(f"cannot deduce Mir format from filename: {path}")

    if dialect == MirDialect.MIDI:
        midi = load_mido(path)
        return Mir.from_mido(midi), midi, dialect

    with open(path) as f:
        baseline = yaml.safe_load(f)

    if dialect == MirDialect.DENSEYAML:
        return Mir.from_dense(baseline), baseline, dialect
    if dialect == MirDialect.RAWYAML:
        return Mir.from_dict(baseline), baseline, dialect

    raise ValueError(f"unsupported dialect: {dialect}")


def _roundtrip_via(mir, target):
    if target == MirDialect.MIDI:
        return Mir.from_mido(mir.to_mido())
    if target == MirDialect.DENSEYAML:
        return Mir.from_dense(mir.to_dense())
    if target == MirDialect.RAWYAML:
        return Mir.from_dict(mir.to_dict())
    raise ValueError(f"unsupported roundtrip target: {target}")


def _mir_to_source_repr(mir, dialect):
    if dialect == MirDialect.MIDI:
        return mir.to_mido()
    if dialect == MirDialect.DENSEYAML:
        return mir.to_dense()
    if dialect == MirDialect.RAWYAML:
        return mir.to_dict()
    raise ValueError(f"unsupported source dialect: {dialect}")


def _assert_midi_equal(actual, expected):
    if actual.type != expected.type or actual.ticks_per_beat != expected.ticks_per_beat:
        raise RuntimeError("MIDI metadata differs")
    if len(actual.tracks) != len(expected.tracks):
        raise RuntimeError("MIDI track count differs")

    for actual_track, expected_track in zip(actual.tracks, expected.tracks):
        if len(actual_track) != len(expected_track):
            raise RuntimeError("MIDI track message count differs")
        for actual_msg, expected_msg in zip(actual_track, expected_track):
            if actual_msg.dict() != expected_msg.dict():
                raise RuntimeError(
                    f"MIDI message differs: {actual_msg!r} != {expected_msg!r}"
                )


def _assert_deep_equal(actual, expected, path="<root>"):
    """Recursively compare two dict/list/scalar structures, reporting the exact
    location and values of the first difference found."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in expected:
            if key not in actual:
                raise RuntimeError(
                    f"{path}.{key}: missing key '{key}', expected value '{expected[key]!r}'"
                )
            _assert_deep_equal(actual[key], expected[key], f"{path}.{key}")
        for key in actual:
            if key not in expected:
                raise RuntimeError(
                    f"{path}.{key}: unexpected key '{key}', got value '{actual[key]!r}'"
                )
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            raise RuntimeError(
                f"{path}: length differs, expected {len(expected)} but got {len(actual)}"
            )
        for index, (a, e) in enumerate(zip(actual, expected)):
            _assert_deep_equal(a, e, f"{path}[{index}]")
    else:
        if type(actual) is not type(expected):
            raise RuntimeError(
                f"{path}: type differs, expected {type(expected).__name__} "
                f"but got {type(actual).__name__}"
            )
        if actual != expected:
            raise RuntimeError(f"{path}: expected {expected!r} but got {actual!r}")


def _assert_source_equal(actual, expected, dialect):
    if dialect == MirDialect.MIDI:
        _assert_midi_equal(actual, expected)
    else:
        _assert_deep_equal(actual, expected)


def roundtrip(input_file):
    source_mir, baseline, source_dialect = _load_mir_and_baseline(input_file)

    for target in (MirDialect.MIDI, MirDialect.DENSEYAML, MirDialect.RAWYAML):
        if target == source_dialect:
            roundtrip_mir = source_mir
        else:
            roundtrip_mir = _roundtrip_via(source_mir, target)

        actual_source_repr = _mir_to_source_repr(roundtrip_mir, source_dialect)
        _assert_source_equal(actual_source_repr, baseline, source_dialect)
        print(f"{target.name}: ok")
