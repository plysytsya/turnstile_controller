import logging
from systemd.journal import JournalHandler
import re

from evdev import InputDevice, list_devices


# Set up the logger
logger = logging.getLogger("qr_logger")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()


def find_qr_devices():
    device_name_substrings = [
        "TMC HIDKeyBoard",
        "Megahunt",
        "YOKO HID GUM",
        "TMC HIDKeyBoard",
        "WCM HIDKeyBoard",
    ]
    devices = [InputDevice(path) for path in list_devices()]
    found_devices = []

    for device in devices:
        logger.info(f"Device: {device.name}")

        if any(name.lower() in device.name.lower() for name in device_name_substrings):
            logger.info(f"Found device: {device}")
            is_extended = is_usb_extended_device(device)
            if is_extended:
                logger.info(f"{device.path} is connected to usb-extender")
            device.is_extended = is_extended
            found_devices.append(device)

    if not found_devices:
        return []

    return found_devices


def is_usb_extended_device(device: InputDevice) -> bool:
    """
    Determines if the USB device has an extended device path.

    Args:
        device (evdev.device.InputDevice): The input device to check.

    Returns:
        bool: True if the device has an extended device path, False otherwise.
    """
    # The device.phys property contains the physical path of the device
    phys = device.phys

    # Regex to match the extended USB path pattern
    extended_pattern = re.compile(r"usb-\d+\.\d+\.\d+/")

    # Return True if the pattern matches, otherwise return False
    return bool(extended_pattern.search(phys))


if __name__ == "__main__":
    found_devices = find_qr_devices()
    if found_devices:
        logger.info(f"Device paths: {[device.path for device in found_devices]}")
