import evdev
from evdev import InputDevice, categorize, KeyEvent
import asyncio
import json

from keymap import KEYMAP  # your existing keymap module

# Replace 'eventX' with the event number you found
dev = InputDevice("/dev/input/event2")

# String to hold the output
output_string = ""


async def print_events(device):
    global output_string  # Use the global string variable

    async for event in device.async_read_loop():
        if event.type == evdev.ecodes.EV_KEY:

            if event.type == evdev.ecodes.EV_KEY:
                categorized_event = categorize(event)
                if categorized_event.keystate == evdev.KeyEvent.key_up:
                    keycode = categorized_event.keycode
                    character = KEYMAP.get(keycode)

                    if character:
                        output_string += character

                    if keycode == "KEY_ENTER":
                        output_string = "{" + output_string.lstrip("{")

                        qr_dict = json.loads(output_string)
                        print(qr_dict)

                        output_string = ""


loop = asyncio.get_event_loop()
loop.run_until_complete(print_events(dev))
