# Step 1: Install the systemd-python package
# You can install it using pip:
# pip install systemd-python

# Step 2: Import the necessary modules
import json
import logging
import os
import subprocess
import sys

import dotenv
from pathlib import Path
from systemd.journal import JournalHandler

from find_device import find_qr_devices
from i2cdetect import detect_i2c_device_not_27

# Step 3: Configure logging to use JournalHandler
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.addHandler(JournalHandler())

EXTENDED_USB_DEVICE_DIRECTION = "B"
DISPLAY_X27_DIRECTION = "0x27"

UNEXTENDED_USB_DEVICE_DIRECTION = "A"

# Get the directory of the current file
current_dir = Path(__file__).parent

devices = find_qr_devices()
usb_direction_lookup = json.loads(
    Path(Path(__file__).parent / "usb_port_map.json").read_text()
)
load_dotenv = dotenv.load_dotenv(Path(__file__).parent / ".env")

processes = []

for qr_reader in devices:
    if qr_reader.is_extended:
        direction = EXTENDED_USB_DEVICE_DIRECTION
        lcd_address = DISPLAY_X27_DIRECTION
        entrance_uuid = os.getenv("ENTRANCE_UUID_B")
        relay_pin = os.getenv("RELAY_PIN_B")
    else:
        direction = UNEXTENDED_USB_DEVICE_DIRECTION
        lcd_address = detect_i2c_device_not_27(1)
        entrance_uuid = os.getenv("ENTRANCE_UUID_A")
        relay_pin = os.getenv("RELAY_PIN_A")

    env = os.environ.copy()

    if lcd_address:
        env["LCD_I2C_ADDRESS"] = lcd_address
    else:
        logger.warning("LCD address is None. Skipping this device.")

    # Define the environment variables
    env["RELAY_PIN_DOOR"] = relay_pin
    env["ENTRANCE_UUID"] = entrance_uuid
    env["QR_USB_DEVICE_PATH"] = qr_reader.path
    env["DIRECTION"] = direction
    if os.getenv("RELAY_TOGGLE_DURATION"):
        env["RELAY_TOGGLE_DURATION"] = os.getenv("RELAY_TOGGLE_DURATION")

    # Define the command
    cmd = [sys.executable, str(current_dir / "qr.py")]

    # Run the command in a subprocess

    logging.warning(f"Starging subprocess {direction} with env-vars: {env}")
    env_without_none_values = {k: v for k, v in env.items() if v is not None}
    p = subprocess.Popen(cmd, env=env_without_none_values)
    processes.append(p)

try:
    for p in processes:
        ret_code = p.wait()  # Wait for each subprocess to finish and get the return code
        if ret_code != 0:
            # If any subprocess exits with a non-zero code, exit the main process with the same code
            logger.error(f"Subprocess {p.pid} exited with code {ret_code}. Exiting main process.")
            sys.exit(ret_code)

except KeyboardInterrupt:
    # On keyboard interrupt, terminate all subprocesses
    logger.warning("Keyboard interrupt detected. Terminating all subprocesses.")
    for p in processes:
        p.terminate()
