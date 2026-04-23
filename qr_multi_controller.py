import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import dotenv
from systemd.journal import JournalHandler

from find_device import find_qr_devices
from i2cdetect import detect_i2c_device_not_27
from qr_reader_assignment import (
    MODE_SERIAL,
    ReaderAssignmentError,
    assign_readers_to_directions,
    configured_active_directions,
    env_value_is_set,
)
from serial_reader import find_serial_devices


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.addHandler(JournalHandler())

DISPLAY_X27_DIRECTION = "0x27"
current_dir = Path(__file__).parent


def direction_env_value(direction, key, fallback=None):
    value = os.getenv(f"{key}_{direction}")
    if env_value_is_set(value):
        return value
    return fallback


def lcd_address_for_direction(direction):
    configured = (
        os.getenv(f"LCD_I2C_ADDRESS_{direction}")
        or os.getenv(f"LCD_ADDRESS_{direction}")
    )
    if env_value_is_set(configured):
        return configured

    if direction == "B":
        return DISPLAY_X27_DIRECTION

    try:
        detected = detect_i2c_device_not_27(1)
    except Exception as exc:
        logger.warning("Failed to detect LCD address for direction %s: %s", direction, exc)
        detected = None

    return detected or os.getenv("I2C_ADDRESS")


def build_subprocess_env(assignment):
    direction = assignment.direction
    reader = assignment.reader
    env = os.environ.copy()

    entrance_uuid = direction_env_value(direction, "ENTRANCE_UUID")
    relay_pin = direction_env_value(direction, "RELAY_PIN")
    display_relay_pin = direction_env_value(direction, "RELAY_PIN_DISPLAY")
    lcd_address = lcd_address_for_direction(direction)

    if entrance_uuid:
        env["ENTRANCE_UUID"] = entrance_uuid
    if relay_pin:
        env["RELAY_PIN_DOOR"] = relay_pin
    if display_relay_pin:
        env["RELAY_PIN_DISPLAY"] = display_relay_pin
    if lcd_address:
        env["LCD_I2C_ADDRESS"] = lcd_address
    if os.getenv("RELAY_TOGGLE_DURATION"):
        env["RELAY_TOGGLE_DURATION"] = os.getenv("RELAY_TOGGLE_DURATION")

    env["QR_USB_DEVICE_PATH"] = reader.path
    env["IS_SERIAL_DEVICE"] = str(reader.mode == MODE_SERIAL)
    env["DIRECTION"] = direction

    return {key: value for key, value in env.items() if value is not None}


def launch_qr_process(assignment):
    env = build_subprocess_env(assignment)
    cmd = [sys.executable, str(current_dir / "qr.py")]
    logger.warning(
        "Starting QR subprocess direction=%s mode=%s path=%s",
        assignment.direction,
        assignment.reader.mode,
        assignment.reader.path,
    )
    return subprocess.Popen(cmd, env=env)


def main():
    dotenv.load_dotenv(current_dir / ".env")

    keyboard_devices = find_qr_devices()
    serial_devices = find_serial_devices()
    active_directions = configured_active_directions(os.environ)

    logger.info("Active QR directions: %s", active_directions)
    logger.info("Detected keyboard QR devices: %s", keyboard_devices)
    logger.info("Detected serial QR devices: %s", serial_devices)

    try:
        assignments = assign_readers_to_directions(
            active_directions=active_directions,
            keyboard_devices=keyboard_devices,
            serial_devices=serial_devices,
            env=os.environ,
        )
    except ReaderAssignmentError as exc:
        logger.error("Could not assign QR readers: %s", exc)
        return 1

    processes = []
    for assignment in assignments:
        processes.append(launch_qr_process(assignment))
        time.sleep(1)

    try:
        for process in processes:
            ret_code = process.wait()
            if ret_code != 0:
                logger.error("Subprocess %s exited with code %s. Exiting main process.", process.pid, ret_code)
                return ret_code
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt detected. Terminating all subprocesses.")
        for process in processes:
            process.terminate()

    return 0


if __name__ == "__main__":
    sys.exit(main())
