"""Roundtrip conversion command."""
from ..mir import MirDialect, path_to_dialect, DIALECT_DISPATCH


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
    source_dialect = path_to_dialect(input_file)
    if source_dialect is None:
        raise ValueError(f"cannot deduce Mir format from filename: {input_file}")

    source_load, source_parse, source_serialize, _ = DIALECT_DISPATCH[source_dialect]
    baseline = source_load(input_file)
    source_mir = source_parse(baseline)

    for target in (MirDialect.MIDI, MirDialect.DENSEYAML, MirDialect.RAWYAML):
        if target == source_dialect:
            roundtrip_mir = source_mir
        else:
            _, target_parse, target_serialize, _ = DIALECT_DISPATCH[target]
            roundtrip_mir = target_parse(target_serialize(source_mir))

        actual_source_repr = source_serialize(roundtrip_mir)
        _assert_source_equal(actual_source_repr, baseline, source_dialect)
        print(f"{target.name}: ok")
