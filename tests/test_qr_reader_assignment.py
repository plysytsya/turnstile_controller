from dataclasses import dataclass

import pytest

from qr_reader_assignment import (
    MODE_KEYBOARD,
    MODE_SERIAL,
    ReaderAssignmentError,
    assign_readers_to_directions,
    configured_active_directions,
)


@dataclass
class FakeDevice:
    path: str
    is_extended: bool = False


def assignment_map(assignments):
    return {assignment.direction: assignment.reader for assignment in assignments}


def test_single_active_direction_a_uses_serial_reader_when_present():
    assignments = assign_readers_to_directions(
        active_directions=["A"],
        keyboard_devices=[],
        serial_devices=[FakeDevice("/dev/ttyACM0")],
        env={},
    )

    reader = assignment_map(assignments)["A"]
    assert reader.mode == MODE_SERIAL
    assert reader.path == "/dev/ttyACM0"


def test_single_active_direction_a_can_use_keyboard_reader():
    assignments = assign_readers_to_directions(
        active_directions=["A"],
        keyboard_devices=[FakeDevice("/dev/input/event4")],
        serial_devices=[],
        env={},
    )

    reader = assignment_map(assignments)["A"]
    assert reader.mode == MODE_KEYBOARD
    assert reader.path == "/dev/input/event4"


def test_two_active_directions_default_to_serial_a_keyboard_b():
    assignments = assign_readers_to_directions(
        active_directions=["A", "B"],
        keyboard_devices=[FakeDevice("/dev/input/event4")],
        serial_devices=[FakeDevice("/dev/ttyACM0")],
        env={},
    )

    readers = assignment_map(assignments)
    assert readers["A"].mode == MODE_SERIAL
    assert readers["A"].path == "/dev/ttyACM0"
    assert readers["B"].mode == MODE_KEYBOARD
    assert readers["B"].path == "/dev/input/event4"


def test_two_active_directions_can_flip_serial_and_keyboard_modes():
    assignments = assign_readers_to_directions(
        active_directions=["A", "B"],
        keyboard_devices=[FakeDevice("/dev/input/event4")],
        serial_devices=[FakeDevice("/dev/ttyACM0")],
        env={
            "QR_READER_MODE_A": "keyboard",
            "QR_READER_MODE_B": "serial",
        },
    )

    readers = assignment_map(assignments)
    assert readers["A"].mode == MODE_KEYBOARD
    assert readers["A"].path == "/dev/input/event4"
    assert readers["B"].mode == MODE_SERIAL
    assert readers["B"].path == "/dev/ttyACM0"


def test_same_mode_readers_keep_usb_hub_fallback_a_local_b_extended():
    assignments = assign_readers_to_directions(
        active_directions=["A", "B"],
        keyboard_devices=[
            FakeDevice("/dev/input/event-local", is_extended=False),
            FakeDevice("/dev/input/event-extended", is_extended=True),
        ],
        serial_devices=[],
        env={},
    )

    readers = assignment_map(assignments)
    assert readers["A"].path == "/dev/input/event-local"
    assert readers["B"].path == "/dev/input/event-extended"


def test_configured_active_directions_defaults_to_a():
    assert configured_active_directions({}) == ["A"]


def test_configured_active_directions_uses_two_reader_flag():
    assert configured_active_directions({"USE_2_QR_READERS": "true"}) == ["A", "B"]


def test_configured_active_directions_can_be_explicit():
    assert configured_active_directions({"QR_ACTIVE_DIRECTIONS": "B,A,B"}) == ["B", "A"]


def test_explicit_mode_errors_when_reader_is_not_available():
    with pytest.raises(ReaderAssignmentError):
        assign_readers_to_directions(
            active_directions=["A"],
            keyboard_devices=[FakeDevice("/dev/input/event4")],
            serial_devices=[],
            env={"QR_READER_MODE_A": "serial"},
        )
