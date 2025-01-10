import os

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

from qr import _find_customer_in_cache


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
