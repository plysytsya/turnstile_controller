from unittest.mock import patch

import pytest

from .lcd_controller import LCDController


@pytest.fixture
def lcd_25():
    with patch('lcd_controller.LCD') as mock:
        yield LCDController(use_lcd=True, lcd_address=25)


@pytest.fixture
def lcd_27():
    with patch('lcd_controller.LCD') as mock:
        yield LCDController(use_lcd=True, lcd_address=27)


def test_display_on_two_lcds(lcd_25, lcd_27):
    # Mock the text and clear methods for both LCDs
    mock_lcd_instance1 = lcd_25.lcd
    mock_lcd_instance2 = lcd_27.lcd

    # Display text on both LCDs
    lcd_25.display("hello1", "line2-1")
    lcd_27.display("hello2", "line2-2")

    # Verify that the text method was called with the expected arguments
    mock_lcd_instance1.text.assert_any_call("hello1", 1)
    mock_lcd_instance1.text.assert_any_call("line2-1", 2)
    mock_lcd_instance2.text.assert_any_call("hello2", 1)
    mock_lcd_instance2.text.assert_any_call("line2-2", 2)

    # Verify that the clear method was called
    assert mock_lcd_instance1.clear.call_count == 1
    assert mock_lcd_instance2.clear.call_count == 1
