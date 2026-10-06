"""Dense YAML representation: compact, human-readable MIDI serialization."""

from collections import Counter
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
# The dense command is a short code (e.g., "on" for note_on), and the tuple contains the
# corresponding mido message type and the order of dense attributes.
CHANNEL_EVENTS_CMDS = {
    "on": ("note_on", ("note", "velocity")),
    "off": ("note_off", ("note", "velocity")),
    "pt": ("polytouch", ("note", "value")),
    "cc": ("control_change", ("control", "value")),
    "pc": ("program_change", ("program",)),
    "at": ("aftertouch", ("value",)),
    "pw": ("pitchwheel", ("pitch",)),
}
# Reverse mapping: mido channel message type -> dense event command.
CMD_BY_TYPE = {msg_type: cmd for cmd, (msg_type, _) in CHANNEL_EVENTS_CMDS.items()}

# Dense event command -> mido meta type for text-based messages.
TEXT_CMDS = {
    "text": "text",
    "copyright": "copyright",
    "lyrics": "lyrics",
    "marker": "marker",
    "cue": "cue_marker",
}
# Reverse mapping: mido text meta type -> dense event command.
CMD_BY_TEXT_TYPE = {meta_type: cmd for cmd, meta_type in TEXT_CMDS.items()}

# Dense event command -> meta type whose single integer attribute is stored verbatim.
INTEGER_CMDS = {
    "port": "midi_port",
}
# Reverse mapping: mido integer meta type -> dense event command.
VALUE_CMD_BY_TYPE = {meta_type: cmd for cmd, meta_type in INTEGER_CMDS.items()}


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

def _parse_note_cmd(
    cmd: str,
    args: List[str],
    time: int,
    event: Any,
    channel: int,
    default_velocity_on: int | None,
    default_velocity_off: int | None,
) -> Dict[str, Any]:
    if not 1 <= len(args) <= 2:
        raise ValueError(
            f"dense: command {cmd!r} takes a note and optional !velocity in event {event!r}"
        )
    note = note2key(args[0])
    if len(args) == 1:
        velocity = default_velocity_on if cmd == "on" else default_velocity_off
    else:
        if not args[1].startswith("!") or len(args[1]) == 1:
            raise ValueError(
                f"dense: velocity must use ! prefix followed by a number in event {event!r}, got {args[1]!r}"
            )
        velocity = _int(args[1][1:], event)
    return {
        "type": "note_on" if cmd == "on" else "note_off",
        "time": time,
        "channel": channel,
        "note": note,
        "velocity": velocity,
    }

def _parse_channel_cmd(
    cmd: str,
    args: List[str],
    time: int,
    event: Any,
    default_channel: int,
    default_velocity_on: int | None,
    default_velocity_off: int | None,
) -> Dict[str, Any]:
    channel = default_channel
    if args and args[-1].startswith("@"):
        channel = _int(args[-1][1:], event)
        args = args[:-1]

    if cmd in ("on", "off"):
        if default_velocity_on is None and cmd == "on":
            raise ValueError(
                f"dense: got velocity event {event} without a default velocity_on"
            )
        return _parse_note_cmd(
            cmd,
            args,
            time,
            event,
            channel,
            default_velocity_on,
            default_velocity_off,
        )

    msg_type, attrs = CHANNEL_EVENTS_CMDS[cmd]
    min_args = len(attrs)
    if not min_args <= len(args) <= len(attrs):
        raise ValueError(f"dense: command {cmd!r} takes {' and '.join(attrs)} in event {event!r}")

    values = [_int(arg, event) for arg in args]
    return {"type": msg_type, "time": time, "channel": channel, **dict(zip(attrs, values))}


def _parse_event(
    event: Any,
    default_channel: int,
    default_velocity_on: int | None,
    default_velocity_off: int | None,
) -> Dict[str, Any]:
    """Parse one dense event string into a raw message dict."""
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
        return _parse_channel_cmd(
            cmd, args, time, event, default_channel,
            default_velocity_on, default_velocity_off,
        )

    raise ValueError(f"dense: unknown event command {cmd!r} in {event!r}")


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
        msgs = [
            _parse_event(event, default_channel, default_velocity_on, default_velocity_off)
            for event in (track.get("events") or [])
        ]
        tracks.append(msgs)

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
    default_channel = next((msg["channel"] for msg in track if msg["type"] in CMD_BY_TYPE), 0)
    velocities = SimpleNamespace(note_on=Counter(), note_off=Counter())

    for msg in track:
        msg_type = msg["type"]
        if msg_type not in ("note_on", "note_off"):
            continue

        velocity = msg["velocity"]

        if velocity == 0 and msg_type == 'note_on':
            msg_type = 'note_off'

        getattr(velocities, msg_type)[velocity] += 1

    default_velocity_on = velocities.note_on.most_common(1)[0][0] if velocities.note_on else None
    default_velocity_off = velocities.note_off.most_common(1)[0][0] if velocities.note_off else 0

    events = []
    for msg in track:
        time = msg["time"]
        meta_type = msg["type"]
        if meta_type == "end_of_track":
            events.append(f"{time} eot")
        elif meta_type == "sysex":
            data_str = " ".join(str(b) for b in msg["data"])
            events.append(f"{time} sx {data_str}" if data_str else f"{time} sx")
        elif meta_type in CMD_BY_TEXT_TYPE:
            events.append(f"{time} {CMD_BY_TEXT_TYPE[meta_type]} {msg['text']}")
        elif meta_type in VALUE_CMD_BY_TYPE:
            events.append(f"{time} {VALUE_CMD_BY_TYPE[meta_type]} {msg[META_ATTRS[meta_type][0]]}")
        elif meta_type in META_ATTRS:
            events.append(_format_meta_event(time, msg))
        elif meta_type in CMD_BY_TYPE:
            suffix = "" if msg["channel"] == default_channel else f" @{msg['channel']}"
            if meta_type == "note_on":
                note = key2note(msg["note"])
                velocity = msg["velocity"]
                if velocity == 0:
                    events.append(f"{time} off {note}{suffix}")
                elif velocity == default_velocity_on:
                    events.append(f"{time} on {note}{suffix}")
                else:
                    events.append(f"{time} on {note} !{velocity}{suffix}")
            elif meta_type == "note_off":
                note = key2note(msg["note"])
                velocity = msg["velocity"]
                if velocity == default_velocity_off:
                    events.append(f"{time} off {note}{suffix}")
                else:
                    events.append(f"{time} off {note} !{velocity}{suffix}")
            else:
                cmd = CMD_BY_TYPE[meta_type]
                attrs = CHANNEL_EVENTS_CMDS[cmd][1]
                tokens = [str(time), cmd]
                for a in attrs:
                    if a == "note" and meta_type in ("note_on", "note_off"):
                        tokens.append(key2note(msg[a]))
                    else:
                        tokens.append(str(msg[a]))
                events.append(" ".join(tokens) + suffix)
        else:
            raise ValueError(f"dense: cannot store {meta_type!r} events in a track")

    out: Dict[str, Any] = {
        "channel": default_channel,
        "events": events,
    }
    if default_velocity_on is not None or default_velocity_off != 0:
        out["velocity_on"] = default_velocity_on
        out["velocity_off"] = default_velocity_off
    return out
