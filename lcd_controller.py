import time

from rpi_lcd import LCD
import logging
from unidecode import unidecode


class LCDController:
    def __init__(self, use_lcd, max_char_count=16, scroll_delay=0.5):
        self.use_lcd = use_lcd
        self.max_char_count = max_char_count
        self.scroll_delay = scroll_delay
        if use_lcd:
            self.lcd = LCD()

    def scroll_text(self, line: str) -> list[str]:
        line_length = len(line)
        if line_length <= self.max_char_count:
            return [line]

        scroll_positions = line_length - self.max_char_count + 1
        return [line[i: i + self.max_char_count] for i in range(scroll_positions)]

    def display(self, line1: str, line2: str, timeout=None) -> None:
        if not self.use_lcd:
            logging.info(line1)
            logging.info(line2)
        else:
            lines_to_scroll1 = self.scroll_text(line1)
            lines_to_scroll2 = self.scroll_text(line2)

            for i in range(max(len(lines_to_scroll1), len(lines_to_scroll2))):
                self.lcd.clear()
                self.lcd.text(unidecode(lines_to_scroll1[i % len(lines_to_scroll1)]), 1)
                self.lcd.text(unidecode(lines_to_scroll2[i % len(lines_to_scroll2)]), 2)
                time.sleep(self.scroll_delay)

            if timeout is not None:
                time.sleep(timeout - self.scroll_delay)
                self.lcd.clear()
