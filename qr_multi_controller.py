import json
import logging
import os
from pathlib import Path
from multiprocessing import Process
import dotenv

from find_device import find_qr_devices
from i2cdetect import detect_i2c_device_b
from qr import run

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

    p = Process(
        target=run,
        kwargs={
            "direction": direction,
            "entrance_uuid": entrance_uuid,
            "relay_pin_door": relay_pin,
            "i2c_address": lcd_address,
            "use_lcd": True,
            "qr_reader": qr_reader,
            "login_credentials": {
                "hostname": os.getenv("HOSTNAME"),
                "username": os.getenv("USERNAME"),
                "password": os.getenv("PASSWORD"),
            },
        },
    )
    p.start()
    processes.append(p)

# Wait for all processes to finish
for p in processes:
    p.join()
