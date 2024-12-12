# Step 1: Install the systemd-python package
# You can install it using pip:
# pip install systemd-python

# Step 2: Import the necessary modules
import logging
import os
from multiprocessing import Process, Manager, Lock
import sys
import time
import qr

import dotenv
from pathlib import Path
from systemd.journal import JournalHandler

from find_device import find_qr_devices
from serial_reader import find_serial_devices, SerialDevice
from i2cdetect import detect_i2c_device_not_27

# Step 3: Configure logging to use JournalHandler
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("qr_multi_controller")
logger.addHandler(JournalHandler())
logger.propagate = False

EXTENDED_USB_DEVICE_DIRECTION = "B"
DISPLAY_X27_DIRECTION = "0x27"

UNEXTENDED_USB_DEVICE_DIRECTION = "A"

# Get the directory of the current file
current_dir = Path(__file__).parent

keyboard_devices = find_qr_devices()
serial_devices = find_serial_devices()
devices = keyboard_devices + serial_devices

load_dotenv = dotenv.load_dotenv(Path(__file__).parent / ".env")

processes = []

# Create a Manager for shared data
manager = Manager()
multi_process_qr_data = manager.dict()
lock = manager.Lock()


for qr_reader in devices:
    if qr_reader.is_extended:
        logger.info(f"Found extended device: {qr_reader}")
        direction = EXTENDED_USB_DEVICE_DIRECTION
        lcd_address = DISPLAY_X27_DIRECTION
        entrance_uuid = os.getenv("ENTRANCE_UUID_B")
        relay_pin = os.getenv("RELAY_PIN_B", "10")
        display_relay_pin = os.getenv("RELAY_PIN_DISPLAY_B", "20")
    else:
        direction = UNEXTENDED_USB_DEVICE_DIRECTION
        lcd_address = detect_i2c_device_not_27(1)
        entrance_uuid = os.getenv("ENTRANCE_UUID_A")
        relay_pin = os.getenv("RELAY_PIN_A", "24")
        display_relay_pin = os.getenv("RELAY_PIN_DISPLAY_A", "21")

    env = os.environ.copy()

    if lcd_address:
        env["LCD_I2C_ADDRESS"] = lcd_address
    else:
        logger.warning("LCD address is None. Skipping this device.")

    # Define the environment variables
    env["RELAY_PIN_DOOR"] = relay_pin
    env["ENTRANCE_UUID"] = entrance_uuid
    env["QR_USB_DEVICE_PATH"] = qr_reader.path
    env["IS_SERIAL_DEVICE"] = str(isinstance(qr_reader, SerialDevice))
    env["DIRECTION"] = direction
    env["RELAY_PIN_DISPLAY"] = display_relay_pin
    if os.getenv("RELAY_TOGGLE_DURATION"):
        env["RELAY_TOGGLE_DURATION"] = os.getenv("RELAY_TOGGLE_DURATION")

    # Define the command
    cmd = [sys.executable, str(current_dir / "qr.py")]

    # Run the command in a subprocess

    logging.warning(f"Starging subprocess {direction} with env-vars: {env}")
    env_without_none_values = {k: v for k, v in env.items() if v is not None}

    p = Process(target=qr.main, args=(env_without_none_values, multi_process_qr_data, lock))
    processes.append(p)


if os.getenv("HAS_CAMERA").lower() in ["true", "1"]:
    from camera import simple_camera as videocamera

    logger.info("Camera is enabled. Initializing camera process.")

    class CameraSettings:
        """Configuration settings for camera video uploads and S3 integration."""

        S3_BUCKET = os.getenv("S3_BUCKET")
        S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
        S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
        S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
        GYM_UUID = os.getenv("GYM_UUID")
        RECORDING_DIR = os.getenv("RECORDING_DIR")
        HOSTNAME = os.getenv("HOSTNAME")
        USERNAME = os.getenv("USERNAME")
        PASSWORD = os.getenv("PASSWORD")
        FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", 480))
        FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", 360))
        FPS = int(os.getenv("FPS", 15))

        @classmethod
        def from_environment(cls):
            """Create a settings instance populated from environment variables."""
            return cls()


    def run_camera_with_exception_handling(settings, qr_data, lock):
        try:
            videocamera.run_camera(settings, qr_data, lock)
        except Exception as e:
            logger.exception(f"Camera process failed with exception: {e}")

    camera_process = Process(
        target=run_camera_with_exception_handling, args=(CameraSettings.from_environment(), multi_process_qr_data, lock)
    )
    processes.append(camera_process)


if __name__ == "__main__":
    try:
        for process in processes:
            process.start()
            logger.info(f"Started process {process.name}. Sleeping for 2 seconds before starting the next process.")
            time.sleep(2)

        # Wait for all processes to complete (in this case, they never end, so this is just a safeguard)
        for process in processes:
            process.join()

    except KeyboardInterrupt:
        logger.info("Interrupt received. Terminating all processes.")
        for process in processes:
            process.terminate()
            process.join()
        logger.info("All processes terminated.")
