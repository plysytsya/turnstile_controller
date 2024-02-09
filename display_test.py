import time

from rpi_lcd import LCD
from unidecode import unidecode

lcd = LCD()


def display_on_lcd(line1, line2, timeout=None):
    max_char_count = 16  # Maximum number of characters per line
    delay = 0.5  # Delay in seconds between each scroll step

    lines_to_scroll1 = scroll_text(line1, max_char_count, delay)
    lines_to_scroll2 = scroll_text(line2, max_char_count, delay)

    for i in range(max(len(lines_to_scroll1), len(lines_to_scroll2))):
        lcd.clear()
        lcd.text(unidecode(lines_to_scroll1[i % len(lines_to_scroll1)]), 1)
        lcd.text(unidecode(lines_to_scroll2[i % len(lines_to_scroll2)]), 2)
        time.sleep(delay)

    if timeout is not None:
        time.sleep(timeout - delay)
        lcd.clear()


def scroll_text(line, max_char_count=16, delay=0.2):
    line_length = len(line)
    if line_length <= max_char_count:
        return [line]

    scroll_positions = line_length - max_char_count + 1
    return [line[i : i + max_char_count] for i in range(scroll_positions)]


if __name__ == "__main__":
    display_on_lcd("hello", "world")
