import logging
import threading
import time
import RPi.GPIO as GPIO

from rpi_lcd import LCD
from unidecode import unidecode


class LCDController:
    def __init__(self, use_lcd, max_char_count=16, scroll_delay=0.5, lcd_address=None, dark_mode=False, relay_pin=None):
        self.use_lcd = use_lcd
        self.max_char_count = max_char_count
        self.scroll_delay = scroll_delay
        if use_lcd:
            self.lcd = LCD(lcd_address)
        self.dark_mode = dark_mode
        if dark_mode and relay_pin:
            self.relay_pin = relay_pin
            GPIO.setup(relay_pin, GPIO.OUT)
            GPIO.output(relay_pin, GPIO.LOW)
            time.sleep(0.5)
            GPIO.output(relay_pin, GPIO.HIGH)


    def clear(self):
        if self.use_lcd:
            self.lcd.clear()
        else:
            logging.info("Clearing display")

    def scroll_text(self, line: str) -> list[str]:
        line_length = len(line)
        if line_length <= self.max_char_count:
            return [line]

        scroll_positions = line_length - self.max_char_count + 1
        return [line[i: i + self.max_char_count] for i in range(scroll_positions)]

    def display(self, line1: str, line2: str, timeout=2) -> None:
        if self.dark_mode and timeout is None:
            # Don't display continuous text in dark mode
            return

        if self.dark_mode and self.relay_pin:
            GPIO.output(self.relay_pin, GPIO.LOW)

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
                if self.dark_mode and self.relay_pin:
                    GPIO.output(self.relay_pin, GPIO.HIGH)


def display_on_multiple_lcds(line1: str, line2: str, controllers: list[LCDController], timeout=2) -> None:
    """
    Display text on multiple LCD controllers simultaneously using threading.

    Args:
        line1 (str): The first line of text to display.
        line2 (str): The second line of text to display.
        controllers (list[LCDController]): A list of LCDController instances.
        timeout (int, optional): How long to display the message for. Defaults to 2 seconds.
    """

    def display_thread(controller: LCDController):
        """Thread target function to display text on a single controller."""
        controller.display(line1, line2, timeout)

    threads = []
    for controller in controllers:
        # Create a new thread for each controller's display method
        thread = threading.Thread(target=display_thread, args=(controller,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()
