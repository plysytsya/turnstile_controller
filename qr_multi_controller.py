import json
import logging
import os
import subprocess
import sys

import dotenv
from pathlib import Path

from find_device import find_qr_devices
from i2cdetect import detect_i2c_device_b

# Get the directory of the current file
current_dir = Path(__file__).parent


devices = find_qr_devices()
usb_direction_lookup = json.loads(
    Path(Path(__file__).parent / "usb_port_map.json").read_text()
)
load_dotenv = dotenv.load_dotenv(Path(__file__).parent / ".env")

processes = []

for device in devices:
    direction = usb_direction_lookup.get(device.phys)
    lcd_address = "0x27" if direction == "A" else detect_i2c_device_b(1)
    usb_devices = find_qr_devices()
    qr_reader = None
    for usb_device in usb_devices:
        if usb_direction_lookup[usb_device.phys] == direction:
            qr_reader = usb_device
            break
    if qr_reader is None:
        logging.warning(f"Could not find QR reader for direction {direction}")
    relay_pin = (
        os.getenv("RELAY_PIN_A") if direction == "A" else os.getenv("RELAY_PIN_B")
    )
    entrance_uuid = (
        os.getenv("ENTRANCE_UUID_A")
        if direction == "A"
        else os.getenv("ENTRANCE_UUID_B")
    )

    # Define the environment variables
    env = os.environ.copy()
    env["LCD_I2C_ADDRESS"] = lcd_address
    env["RELAY_PIN"] = relay_pin
    env["ENTRANCE_UUID"] = entrance_uuid
    env["QR_USB_DEVICE_PATH"] = qr_reader.path

    # Define the command
    cmd = [sys.executable, str(current_dir / "qr.py")]

    # Run the command in a subprocess
    p = subprocess.Popen(cmd, env=env)
    processes.append(p)


try:
    # Your existing code here...

    # Wait for all processes to finish
    for p in processes:
        p.wait()

except KeyboardInterrupt:
    # On keyboard interrupt, terminate all subprocesses
    for p in processes:
        p.terminate()