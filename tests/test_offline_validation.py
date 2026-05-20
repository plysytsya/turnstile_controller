import json
import os
import time

import pytest
from freezegun import freeze_time
from unittest.mock import patch
import sys
from unittest.mock import MagicMock

from dotenv import load_dotenv

sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['rpi_lcd'] = MagicMock()
sys.modules['unidecode'] = MagicMock()
sys.modules['systemd'] = MagicMock()
sys.modules['systemd.journal'] = MagicMock()
sys.modules['evdev'] = MagicMock()
sys.modules['gpiod'] = MagicMock()
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()
os.environ["IS_SERIAL_DEVICE"] = "True"

# Mock the logging module
import logging
logging.getLogger = MagicMock()
mock_logger = logging.getLogger()
mock_handler = MagicMock()
mock_handler.level = logging.INFO
mock_logger.handlers = [mock_handler]


one_level_up = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# Construct the path to the .env file in the directory one level up
dotenv_path = os.path.join(one_level_up, '.env')
# Load the .env file
load_dotenv(dotenv_path)

import qr
from qr import _find_customer_in_cache, _get_current_local_time


CUSTOMER_CARD_NUMBER = "312f8abd-bc60-5988-9ebf-277c9581c19b"


def write_customers_cache(tmp_path, monkeypatch, customers):
    monkeypatch.setattr(qr, "__file__", str(tmp_path / "qr.py"))
    cache_path = tmp_path / "customers.json"
    cache_path.write_text(json.dumps(customers), encoding="utf-8")
    return cache_path


def readable_scheduled_customer():
    return {
        "id": 5239,
        "customer_uuid": "87213db3-d930-4321-84fc-452fc656d685",
        "first_name": "Andres",
        "last_name": "Marquez Quiros",
        "is_staff": False,
        "card_number": CUSTOMER_CARD_NUMBER,
        "second_card_number": "",
        "active_membership": True,
        "entrance_schedules": [
            {
                "start_time": "07:00:00",
                "end_time": "22:00:00",
                "days_of_week": [0, 1, 2, 3, 4]
            },
            {
                "start_time": "08:00:00",
                "end_time": "13:00:00",
                "days_of_week": [5]
            }
        ]
    }


@pytest.mark.parametrize("frozen_time, expected_status, expected_first_name", [
    ("2025-01-10 10:00:00", "UserExists", "Usuario"),
    ("2025-01-10 23:00:00", "OutsideSchedule", None),
    ("2025-01-12 13:00:00", "OutsideSchedule", None),
])
@patch('qr.load_customers_cache')
def test_validate_customer(mock_load_customers_cache, frozen_time, expected_status, expected_first_name):
    # Mock return value for load_customers_cache
    mock_load_customers_cache.return_value = {
        "bd832dfc-f986-49a9-b028-5915a45b3bb1": {
            "id": 895,
            "customer_uuid": "bd832dfc-f986-49a9-b028-5915a45b3bb1",
            "first_name": "Usuario",
            "last_name": "Prueba",
            "is_staff": False,
            "card_number": "",
            "second_card_number": "",
            "active_membership": True,
            "entrance_schedules": [
                {
                    "start_time": "10:00:00",
                    "end_time": "22:00:00",
                    "days_of_week": [0, 1, 2, 3, 4]
                },
                {
                    "start_time": "10:00:00",
                    "end_time": "12:00:00",
                    "days_of_week": [6]
                }
            ]
        }
    }

    with freeze_time(frozen_time):
        status_code, customer = _find_customer_in_cache("bd832dfc-f986-49a9-b028-5915a45b3bb1")
        assert status_code == expected_status


@pytest.mark.parametrize("frozen_utc_time, expected_status", [
    ("2025-01-10 08:59:00+00:00", "OutsideSchedule"),
    ("2025-01-10 09:00:00+00:00", "UserExists"),
])
@patch('qr.load_customers_cache')
def test_validate_customer_uses_madrid_time_for_schedule(mock_load_customers_cache, frozen_utc_time, expected_status):
    mock_load_customers_cache.return_value = {
        "bd832dfc-f986-49a9-b028-5915a45b3bb1": {
            "id": 895,
            "customer_uuid": "bd832dfc-f986-49a9-b028-5915a45b3bb1",
            "first_name": "Usuario",
            "last_name": "Prueba",
            "is_staff": False,
            "card_number": "",
            "second_card_number": "",
            "active_membership": True,
            "entrance_schedules": [
                {
                    "start_time": "10:00:00",
                    "end_time": "22:00:00",
                    "days_of_week": [4]
                }
            ]
        }
    }

    with freeze_time(frozen_utc_time):
        status_code, customer = _find_customer_in_cache("bd832dfc-f986-49a9-b028-5915a45b3bb1")
        assert status_code == expected_status


def test_get_current_local_time_returns_localtime_compatible_struct():
    current_time = _get_current_local_time()

    assert isinstance(current_time, time.struct_time)
    assert hasattr(current_time, "tm_wday")
    assert hasattr(current_time, "tm_hour")
    assert hasattr(current_time, "tm_min")


def test_refresh_runtime_reader_assignment_updates_globals(monkeypatch):
    monkeypatch.setattr(
        qr,
        "configure_direction_environment",
        lambda direction, force_reader_refresh=False: os.environ.update(
            {
                "ENTRANCE_UUID": "entrance-1",
                "IS_SERIAL_DEVICE": "True",
                "QR_USB_DEVICE_PATH": "/dev/input/test-reader",
            }
        ),
    )

    qr.refresh_runtime_reader_assignment(force_reader_refresh=True)

    assert qr.ENTRANCE_UUID == "entrance-1"
    assert qr.IS_SERIAL_DEVICE is True
    assert qr.QR_USB_DEVICE_PATH == "/dev/input/test-reader"


def test_init_qr_device_retries_until_reconnected(monkeypatch):
    attempts = {"count": 0}
    sleep_calls = []
    state_calls = []
    fake_device = MagicMock()

    monkeypatch.setattr(qr, "USB_COMPONENT", "qr_a")
    monkeypatch.setattr(qr, "QR_RECONNECT_SLEEP_SECONDS", 0)
    monkeypatch.setattr(qr, "display_on_lcd", lambda *args, **kwargs: None)
    monkeypatch.setattr(qr, "record_component_state", lambda component, connected: state_calls.append((component, connected)))

    def fake_refresh(force_reader_refresh=False):
        qr.IS_SERIAL_DEVICE = False
        qr.QR_USB_DEVICE_PATH = "/dev/input/test-reader"

    monkeypatch.setattr(qr, "refresh_runtime_reader_assignment", fake_refresh)

    def fake_input_device(path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise FileNotFoundError("missing")
        return fake_device

    monkeypatch.setattr(qr, "InputDevice", fake_input_device)
    monkeypatch.setattr(qr.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    device = qr.init_qr_device()

    assert device is fake_device
    assert attempts["count"] == 2
    assert sleep_calls == [0]
    assert state_calls[-2:] == [("qr_a", False), ("qr_a", True)]


def test_find_customer_in_customers_json_inside_schedule(tmp_path, monkeypatch):
    write_customers_cache(
        tmp_path,
        monkeypatch,
        {CUSTOMER_CARD_NUMBER: readable_scheduled_customer()},
    )

    with freeze_time("2025-01-10 09:00:00+00:00"):
        status_code, customer = _find_customer_in_cache(CUSTOMER_CARD_NUMBER)

    assert status_code == "UserExists"
    assert customer["first_name"] == "Andres"


def test_find_customer_in_customers_json_outside_schedule(tmp_path, monkeypatch):
    write_customers_cache(
        tmp_path,
        monkeypatch,
        {CUSTOMER_CARD_NUMBER: readable_scheduled_customer()},
    )

    with freeze_time("2025-01-10 22:00:00+00:00"):
        status_code, customer = _find_customer_in_cache(CUSTOMER_CARD_NUMBER)

    assert status_code == "OutsideSchedule"
    assert customer is None
