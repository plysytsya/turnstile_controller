import json
import logging
import os
import subprocess
import sys

import dotenv
from pathlib import Path

from find_device import find_qr_devices
from i2cdetect import detect_i2c_device_not_27

logging.basicConfig(level=logging.INFO)

EXTENDED_USB_DEVICE_DIRECTION = "B"
DISPLAY_X27_DIRECTION = "B"

UNEXTENDED_USB_DEVICE_DIRECTION = "A"
DISPAY_NOT_X27_DIRECTION = "A"


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

    # Define the environment variables
    env = os.environ.copy()
    env["LCD_I2C_ADDRESS"] = lcd_address
    env["RELAY_PIN_DOOR"] = relay_pin
    env["ENTRANCE_UUID"] = entrance_uuid
    env["QR_USB_DEVICE_PATH"] = qr_reader.path

    # Define the command
    cmd = [sys.executable, str(current_dir / "qr.py")]

    # Run the command in a subprocess
    logging.info(f"Initializing with envvars: {env}")
    p = subprocess.Popen(cmd, env=env)
    processes.append(p)


try:
    for p in processes:
        p.wait()

except KeyboardInterrupt:
    # On keyboard interrupt, terminate all subprocesses
    for p in processes:
        p.terminate()
