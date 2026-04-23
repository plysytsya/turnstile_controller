import os
from dataclasses import dataclass


MODE_AUTO = "auto"
MODE_SERIAL = "serial"
MODE_KEYBOARD = "keyboard"
MODE_DISABLED = "disabled"

VALID_DIRECTIONS = ("A", "B")
VALID_MODES = (MODE_AUTO, MODE_SERIAL, MODE_KEYBOARD, MODE_DISABLED)

DEFAULT_MODE_PREFERENCE = {
    "A": (MODE_SERIAL, MODE_KEYBOARD),
    "B": (MODE_KEYBOARD, MODE_SERIAL),
}

INVALID_ENV_VALUES = {"", "none", "null", "false", "0"}


class ReaderAssignmentError(Exception):
    pass


@dataclass(frozen=True)
class ReaderDevice:
    mode: str
    path: str
    is_extended: bool = False
    raw_device: object = None

    @property
    def is_serial(self):
        return self.mode == MODE_SERIAL


@dataclass(frozen=True)
class ReaderAssignment:
    direction: str
    reader: ReaderDevice


def env_value_is_set(value):
    if value is None:
        return False
    return str(value).strip().strip("\"'").lower() not in INVALID_ENV_VALUES


def parse_bool(value, default=False):
    if value is None:
        return default
    normalized = str(value).strip().strip("\"'").lower()
    if normalized in ("1", "true", "yes", "y", "on"):
        return True
    if normalized in ("0", "false", "no", "n", "off"):
        return False
    return default


def normalize_direction(direction):
    normalized = str(direction or "").strip().strip("\"'").upper()
    if normalized not in VALID_DIRECTIONS:
        raise ReaderAssignmentError(f"Unsupported QR direction: {direction!r}")
    return normalized


def normalize_mode(mode, default=MODE_AUTO):
    normalized = str(mode or default).strip().strip("\"'").lower()
    aliases = {
        "hid": MODE_KEYBOARD,
        "keyboard_mode": MODE_KEYBOARD,
        "serial_mode": MODE_SERIAL,
        "off": MODE_DISABLED,
        "false": MODE_DISABLED,
        "none": MODE_DISABLED,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in VALID_MODES:
        raise ReaderAssignmentError(
            f"Unsupported QR reader mode {mode!r}. Use one of: {', '.join(VALID_MODES)}."
        )
    return normalized


def reader_mode_for_direction(direction, env=os.environ):
    direction = normalize_direction(direction)
    return normalize_mode(
        env.get(f"QR_READER_MODE_{direction}") or env.get(f"QR_READER_TYPE_{direction}") or env.get("QR_READER_MODE")
    )


def configured_active_directions(env=os.environ):
    explicit = env.get("QR_ACTIVE_DIRECTIONS") or env.get("ACTIVE_QR_DIRECTIONS")
    if explicit:
        directions = []
        for value in str(explicit).replace(";", ",").split(","):
            value = value.strip()
            if value:
                directions.append(normalize_direction(value))
        return list(dict.fromkeys(directions))

    if parse_bool(env.get("USE_2_QR_READERS"), False):
        return ["A", "B"]

    return ["A"]


def build_reader_devices(keyboard_devices, serial_devices):
    readers = []
    for device in serial_devices:
        readers.append(
            ReaderDevice(
                mode=MODE_SERIAL,
                path=device.path,
                is_extended=bool(getattr(device, "is_extended", False)),
                raw_device=device,
            )
        )
    for device in keyboard_devices:
        readers.append(
            ReaderDevice(
                mode=MODE_KEYBOARD,
                path=device.path,
                is_extended=bool(getattr(device, "is_extended", False)),
                raw_device=device,
            )
        )
    return readers


def _path_override_for_direction(direction, env):
    return (
        env.get(f"QR_USB_DEVICE_PATH_{direction}")
        or env.get(f"QR_READER_PATH_{direction}")
        or env.get(f"QR_DEVICE_PATH_{direction}")
    )


def _mode_for_path_override(direction, path, readers, env):
    for reader in readers:
        if reader.path == path:
            return reader.mode

    explicit_mode = reader_mode_for_direction(direction, env)
    if explicit_mode in (MODE_SERIAL, MODE_KEYBOARD):
        return explicit_mode

    explicit_is_serial = env.get(f"IS_SERIAL_DEVICE_{direction}")
    if explicit_is_serial is not None:
        return MODE_SERIAL if parse_bool(explicit_is_serial, False) else MODE_KEYBOARD

    raise ReaderAssignmentError(
        f"QR path override for direction {direction} needs QR_READER_MODE_{direction} "
        f"or IS_SERIAL_DEVICE_{direction} because the path was not detected: {path}"
    )


def _candidate_sort_key(direction, reader):
    # Keep old USB-hub behavior as the fallback for same-mode readers:
    # direction B prefers the extended side, direction A prefers the local side.
    extended_rank = 0 if reader.is_extended == (direction == "B") else 1
    return (extended_rank, reader.path)


def _select_reader(direction, readers, used_paths, env):
    path_override = _path_override_for_direction(direction, env)
    if path_override:
        mode = _mode_for_path_override(direction, path_override, readers, env)
        if path_override in used_paths:
            raise ReaderAssignmentError(f"QR reader path {path_override} is assigned more than once.")
        return ReaderDevice(mode=mode, path=path_override)

    configured_mode = reader_mode_for_direction(direction, env)
    if configured_mode == MODE_DISABLED:
        return None

    mode_preferences = (
        (configured_mode,)
        if configured_mode in (MODE_SERIAL, MODE_KEYBOARD)
        else DEFAULT_MODE_PREFERENCE[direction]
    )

    for mode in mode_preferences:
        candidates = [
            reader
            for reader in readers
            if reader.mode == mode and reader.path not in used_paths
        ]
        if candidates:
            return sorted(candidates, key=lambda reader: _candidate_sort_key(direction, reader))[0]

    return None


def assign_readers_to_directions(active_directions, keyboard_devices, serial_devices, env=os.environ):
    readers = build_reader_devices(keyboard_devices, serial_devices)
    used_paths = set()
    assignments = []

    for raw_direction in active_directions:
        direction = normalize_direction(raw_direction)
        reader = _select_reader(direction, readers, used_paths, env)
        if reader is None:
            mode = reader_mode_for_direction(direction, env)
            if mode == MODE_DISABLED:
                continue
            raise ReaderAssignmentError(f"No QR reader available for direction {direction} with mode {mode}.")

        used_paths.add(reader.path)
        assignments.append(ReaderAssignment(direction=direction, reader=reader))

    return assignments


def select_reader_for_direction(direction, keyboard_devices, serial_devices, env=os.environ):
    assignments = assign_readers_to_directions([direction], keyboard_devices, serial_devices, env)
    if not assignments:
        raise ReaderAssignmentError(f"QR reader direction {direction} is disabled.")
    return assignments[0].reader
