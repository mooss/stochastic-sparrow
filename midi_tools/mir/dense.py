"""Dense YAML representation: compact, human-readable MIDI serialization."""

from collections import Counter, defaultdict, deque
from types import SimpleNamespace
from typing import Any, Dict, List

from ..utils import note2key, key2note

# Dense meta event name -> mido meta attributes, in value order.
# One attribute is stored as a scalar, several as a list.
META_ATTRS = {
    "sequence_number": ("number",),
    "text": ("text",),
    "copyright": ("text",),
    "track_name": ("name",),
    "instrument_name": ("name",),
    "lyrics": ("text",),
    "marker": ("text",),
    "cue_marker": ("text",),
    "device_name": ("name",),
    "channel_prefix": ("channel",),
    "midi_port": ("port",),
    "set_tempo": ("tempo",),
    "smpte_offset": ("frame_rate", "hours", "minutes", "seconds", "frames", "sub_frames"),
    "time_signature": ("numerator", "denominator", "clocks_per_click", "notated_32nd_notes_per_beat"),
    "key_signature": ("key",),
    "sequencer_specific": ("data",),
}

# Meta types whose single attribute is a string value.
STRING_META_TYPES = {
    "text", "copyright", "track_name", "instrument_name", "lyrics",
    "marker", "cue_marker", "device_name", "key_signature",
}

# Dense event command -> (mido message type, attribute names).
# The dense command is a short code (e.g., "cc" for control_change), and the tuple contains the
# corresponding mido message type and the order of dense attributes.
CHANNEL_EVENTS_CMDS = {
    "pt": ("polytouch", ("note", "value")),
    "cc": ("control_change", ("control", "value")),
    "pc": ("program_change", ("program",)),
    "at": ("aftertouch", ("value",)),
    "pw": ("pitchwheel", ("pitch",)),
}
# Reverse mapping: mido channel message type -> dense event command.
CMD_BY_TYPE = {msg_type: cmd for cmd, (msg_type, _) in CHANNEL_EVENTS_CMDS.items()}

# Dense event command -> meta type for text-based messages.
TEXT_CMDS = {
    "text": "text",
    "copyright": "copyright",
    "lyrics": "lyrics",
    "marker": "marker",
    "cue": "cue_marker",
}
# Reverse mapping: meta type -> dense event command.
CMD_BY_TEXT_TYPE = {meta_type: cmd for cmd, meta_type in TEXT_CMDS.items()}

# Dense event command -> meta type whose single integer attribute is stored verbatim.
INTEGER_CMDS = {
    "port": "midi_port",
}
# Reverse mapping: integer meta type -> dense event command.
VALUE_CMD_BY_TYPE = {meta_type: cmd for cmd, meta_type in INTEGER_CMDS.items()}

NOTE_MESSAGE_TYPES = {"note_on", "note_off"}


def _int(token: str, event: str) -> int:
    try:
        return int(token)
    except ValueError:
        raise ValueError(f"dense: expected an integer, got {token!r} in event {event!r}") from None


def _format_meta_event(time: int, msg: Dict[str, Any]) -> str:
    meta_type = msg["type"]
    attrs = META_ATTRS[meta_type]
    if meta_type in STRING_META_TYPES:
        return f"{time} {meta_type} {msg[attrs[0]]}"
    if meta_type == "sequencer_specific":
        data = " ".join(str(b) for b in msg["data"])
        return f"{time} sequencer_specific {data}" if data else f"{time} sequencer_specific"
    values = [msg[a] for a in attrs]
    return f"{time} {meta_type} " + " ".join(str(v) for v in values)


############################
# Internal parse functions #

def _parse_value_cmd(cmd: str, args: List[str], time: int, event: Any) -> Dict[str, Any]:
    if len(args) != 1:
        raise ValueError(f"dense: command {cmd!r} takes one integer value in event {event!r}")
    attr = META_ATTRS[INTEGER_CMDS[cmd]][0]
    return {"type": INTEGER_CMDS[cmd], attr: _int(args[0], event), "time": time}


def _parse_meta_cmd(cmd: str, rest: str, args: List[str], time: int, event: Any) -> Dict[str, Any]:
    attrs = META_ATTRS[cmd]
    if cmd in STRING_META_TYPES:
        return {"type": cmd, attrs[0]: rest, "time": time}
    if cmd == "sequencer_specific":
        return {"type": cmd, "data": [_int(a, event) for a in args], "time": time}
    if len(args) != len(attrs):
        raise ValueError(
            f"dense: command {cmd!r} takes {len(attrs)} values ({', '.join(attrs)}) in event {event!r}"
        )
    values = [_int(a, event) for a in args]
    return {"type": cmd, "time": time, **dict(zip(attrs, values))}


def _parse_channel_cmd(
    cmd: str,
    args: List[str],
    time: int,
    event: Any,
    default_channel: int,
) -> Dict[str, Any]:
    channel = default_channel
    if args and args[-1].startswith("@"):
        channel = _int(args[-1][1:], event)
        args = args[:-1]

    msg_type, attrs = CHANNEL_EVENTS_CMDS[cmd]
    if len(args) != len(attrs):
        raise ValueError(f"dense: command {cmd!r} takes {' and '.join(attrs)} in event {event!r}")

    values = [_int(arg, event) for arg in args]
    return {"type": msg_type, "time": time, "channel": channel, **dict(zip(attrs, values))}


def _parse_fused_note(
    event: Any,
    default_channel: int,
    default_velocity_on: int | None,
    default_velocity_off: int | None,
) -> Dict[str, Any]:
    """Parse a fused note event and return its note, delta, duration, and attributes."""
    tokens = str(event).split()
    if len(tokens) < 5:
        raise ValueError(
            f"dense: invalid fused note event {event!r}, expected "
            "'<NOTE> at <onset_delta> [!<on_velocity>] for <duration> [!<off_velocity>] [@<channel>]'"
        )

    #####################################################
    # First 3 required tokens (<NOTE> at <onset_delta>) #
    note = note2key(tokens[0])
    if tokens[1] != "at":
        raise ValueError(f"dense: expected 'at' after note in event {event!r}")
    onset_delta = _int(tokens[2], event)

    ###############################################
    # Optional attack velocity ([!<on_velocity>]) #
    index = 3
    on_velocity = default_velocity_on
    if index < len(tokens) and tokens[index].startswith("!"):
        if len(tokens[index]) == 1:
            raise ValueError(f"dense: missing onset velocity after ! in event {event!r}")
        on_velocity = _int(tokens[index][1:], event)
        index += 1
    elif default_velocity_on is None:
        raise ValueError(f"dense: fused note {event!r} has no onset velocity or track default")

    if on_velocity == 0:
        raise ValueError(
            f"dense: onset velocity must be greater than zero in fused note event {event!r}"
        )

    ###########################################
    # Next 2 required tokens (for <duration>) #
    if index >= len(tokens) or tokens[index] != "for":
        raise ValueError(f"dense: expected 'for' after onset in event {event!r}")
    index += 1

    if index >= len(tokens):
        raise ValueError(f"dense: missing duration in event {event!r}")
    duration = _int(tokens[index], event)
    index += 1

    if duration < 0:
        raise ValueError(f"dense: negative duration {duration} in fused note event {event!r}")

    ######################################################################
    # Optional off velocity and channel ([!<off_velocity>] [@<channel>]) #
    off_velocity = 0 if default_velocity_off is None else default_velocity_off
    if index < len(tokens) and tokens[index].startswith("!"):
        if len(tokens[index]) == 1:
            raise ValueError(f"dense: missing offset velocity in event {event!r}")
        off_velocity = _int(tokens[index][1:], event)
        index += 1

    channel = default_channel
    if index < len(tokens) and tokens[index].startswith("@"):
        channel = _int(tokens[index][1:], event)
        index += 1

    ################
    # Final result #
    if index != len(tokens):
        raise ValueError(f"dense: unexpected token {tokens[index]!r} in fused note event {event!r}")

    return {
        "note": note,
        "onset_delta": onset_delta,
        "duration": duration,
        "on_velocity": on_velocity,
        "off_velocity": off_velocity,
        "channel": channel,
    }


def _parse_dense_event(
    event: Any,
    default_channel: int,
) -> Dict[str, Any]:
    """Parse one time-first dense event string into a raw message dict."""
    tokens = str(event).split(None, 2)
    if len(tokens) < 2:
        raise ValueError(f"dense: invalid event {event!r}, expected '<time> <command> [args...]'")
    time = _int(tokens[0], event)
    cmd = tokens[1].lower()
    rest = tokens[2] if len(tokens) > 2 else ""
    args = rest.split()

    if cmd == "eot":
        return {"type": "end_of_track", "time": time}
    if cmd == "sx":
        return {"type": "sysex", "data": [_int(a, event) for a in args], "time": time}
    if cmd in TEXT_CMDS:
        return {"type": TEXT_CMDS[cmd], "text": rest, "time": time}

    if cmd in INTEGER_CMDS:
        return _parse_value_cmd(cmd, args, time, event)

    if cmd in META_ATTRS:
        return _parse_meta_cmd(cmd, rest, args, time, event)

    if cmd in CHANNEL_EVENTS_CMDS:
        return _parse_channel_cmd(cmd, args, time, event, default_channel)

    raise ValueError(f"dense: unknown event command {cmd!r} in {event!r}")


def _is_fused_note_event(event: Any) -> bool:
    text = str(event)
    return bool(text) and "A" <= text[0] <= "G"


def _parse_dense_track(
    track: Dict[str, Any],
    default_channel: int,
    default_velocity_on: int | None,
    default_velocity_off: int | None,
) -> List[Dict[str, Any]]:
    """Parse a dense track, expand fused notes, and recalculate MIDI delta times."""
    absolute_time = 0
    position = 0
    ordered_messages = [] # 3-uple (time of event, position in sequence, raw event dict).

    for event in track.get("events") or []:
        if _is_fused_note_event(event):
            fused = _parse_fused_note(
                event,
                default_channel,
                default_velocity_on,
                default_velocity_off,
            )
            absolute_time += fused["onset_delta"]
            onset_time = absolute_time
            note_on = {
                "type": "note_on",
                "time": onset_time,
                "channel": fused["channel"],
                "note": fused["note"],
                "velocity": fused["on_velocity"],
            }
            note_off = {
                "type": "note_off",
                "time": onset_time + fused["duration"],
                "channel": fused["channel"],
                "note": fused["note"],
                "velocity": fused["off_velocity"],
            }
            ordered_messages.append((onset_time, position, note_on))
            position += 1
            ordered_messages.append((onset_time + fused["duration"], position, note_off))
            position += 1
            continue

        msg = _parse_dense_event(event, default_channel)
        absolute_time += msg["time"]
        msg["time"] = absolute_time
        ordered_messages.append((absolute_time, position, msg))
        position += 1

    ordered_messages.sort(key=lambda entry: (entry[0], entry[1]))

    messages = []
    previous_time = 0
    for absolute_tick, _, msg in ordered_messages:
        msg["time"] = absolute_tick - previous_time
        previous_time = absolute_tick
        messages.append(msg)

    return messages


##############
# Conversion #

def dense_to_raw(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a dense dictionary into a raw dictionary (see Mir.to_dict)."""
    if "ticks_per_beat" not in data:
        raise ValueError("dense: missing required key 'ticks_per_beat'")

    tracks = []
    for track in data.get("tracks") or []:
        if not isinstance(track, dict):
            raise ValueError("dense: each entry of 'tracks' must be a mapping")
        if "channel" not in track:
            raise ValueError("dense: missing required key 'channel' in track")
        default_channel = track["channel"]
        default_velocity_on = track.get("velocity_on")
        default_velocity_off = track.get("velocity_off", 0)
        tracks.append(_parse_dense_track(
            track,
            default_channel,
            default_velocity_on,
            default_velocity_off))

    return {
        "midi_format": 1,
        "ticks_per_beat": data["ticks_per_beat"],
        "tracks": tracks,
    }


def raw_to_dense(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw dictionary (see Mir.to_dict) into a dense dictionary."""
    if data.get("midi_format", 1) != 1:
        raise ValueError(
            f"dense: only MIDI format 1 can be saved as dense, got {data.get('midi_format')}"
        )

    tracks = data.get("tracks") or []
    return {
        "ticks_per_beat": data["ticks_per_beat"],
        "tracks": [_raw_to_dense_track(track) for track in tracks],
    }


def _raw_to_dense_track(track: List[Dict[str, Any]]) -> Dict[str, Any]:
    default_channel = 0
    for msg in track:
        if msg["type"] in CMD_BY_TYPE or msg["type"] in NOTE_MESSAGE_TYPES:
            default_channel = msg["channel"]
            break
    velocities = SimpleNamespace(note_on=Counter(), note_off=Counter())

    for msg in track:
        msg_type = msg["type"]
        if msg_type not in NOTE_MESSAGE_TYPES:
            continue

        velocity = msg["velocity"]
        if velocity == 0 and msg_type == "note_on":
            msg_type = "note_off"

        getattr(velocities, msg_type)[velocity] += 1

    default_velocity_on = velocities.note_on.most_common(1)[0][0] if velocities.note_on else None
    default_velocity_off = velocities.note_off.most_common(1)[0][0] if velocities.note_off else 0

    absolute_messages = []
    absolute_time = 0
    for index, msg in enumerate(track):
        absolute_time += msg["time"]
        absolute_messages.append((index, absolute_time, msg))

    pending = defaultdict(deque)
    paired_notes = {}
    offset_indices = set()

    for index, absolute_tick, msg in absolute_messages:
        msg_type = msg["type"]
        if msg_type == "note_on" and msg["velocity"] > 0:
            pending[(msg["channel"], msg["note"])].append((index, absolute_tick, msg))
            continue

        if msg_type == "note_off" or (msg_type == "note_on" and msg["velocity"] == 0):
            key = (msg["channel"], msg["note"])
            if not pending[key]:
                raise ValueError(
                    f"dense: unmatched note offset for channel {msg['channel']} "
                    f"and pitch {msg['note']} at tick {absolute_tick}"
                )
            onset_index, onset_tick, onset_msg = pending[key].popleft()
            paired_notes[onset_index] = {
                "onset_tick": onset_tick,
                "onset_msg": onset_msg,
                "duration": absolute_tick - onset_tick,
                "off_velocity": msg["velocity"],
            }
            offset_indices.add(index)

    unmatched = [
        (key, onset_tick)
        for key, queue in pending.items()
        for _, onset_tick, _ in queue
    ]
    if unmatched:
        key, onset_tick = unmatched[0]
        raise ValueError(
            f"dense: unmatched note onset for channel {key[0]} "
            f"and pitch {key[1]} at tick {onset_tick}"
        )

    events = []
    previous_emitted_tick = 0

    for index, absolute_tick, msg in absolute_messages:
        if index in offset_indices:
            continue

        delta = absolute_tick - previous_emitted_tick
        msg_type = msg["type"]

        if index in paired_notes:
            pair = paired_notes[index]
            onset_msg = pair["onset_msg"]
            note = key2note(onset_msg["note"])
            parts = [f"{note} at {delta}"]
            if onset_msg["velocity"] != default_velocity_on:
                parts[-1] += f" !{onset_msg['velocity']}"
            parts.append(f"for {pair['duration']}")
            if pair["off_velocity"] != default_velocity_off:
                parts[-1] += f" !{pair['off_velocity']}"
            if onset_msg["channel"] != default_channel:
                parts.append(f"@{onset_msg['channel']}")
            events.append(" ".join(parts))
        elif msg_type == "end_of_track":
            events.append(f"{delta} eot")
        elif msg_type == "sysex":
            data_str = " ".join(str(b) for b in msg["data"])
            events.append(f"{delta} sx {data_str}" if data_str else f"{delta} sx")
        elif msg_type in CMD_BY_TEXT_TYPE:
            events.append(f"{delta} {CMD_BY_TEXT_TYPE[msg_type]} {msg['text']}")
        elif msg_type in VALUE_CMD_BY_TYPE:
            events.append(f"{delta} {VALUE_CMD_BY_TYPE[msg_type]} {msg[META_ATTRS[msg_type][0]]}")
        elif msg_type in META_ATTRS:
            events.append(_format_meta_event(delta, msg))
        elif msg_type in CMD_BY_TYPE:
            suffix = "" if msg["channel"] == default_channel else f" @{msg['channel']}"
            cmd = CMD_BY_TYPE[msg_type]
            attrs = CHANNEL_EVENTS_CMDS[cmd][1]
            tokens = [str(delta), cmd]
            for attr in attrs:
                tokens.append(str(msg[attr]))
            events.append(" ".join(tokens) + suffix)
        else:
            raise ValueError(f"dense: cannot store {msg_type!r} events in a track")

        previous_emitted_tick = absolute_tick

    out: Dict[str, Any] = {
        "channel": default_channel,
        "events": events,
    }
    if default_velocity_on is not None or default_velocity_off != 0:
        out["velocity_on"] = default_velocity_on
        out["velocity_off"] = default_velocity_off
    return out
