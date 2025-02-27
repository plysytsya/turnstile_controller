import serial
import serial.tools.list_ports
import threading
import binascii

DEBUG = True  # Enable debugging output


class SerialDevice:
    def __init__(self, path, is_extended, location):
        self.path = path
        self.is_extended = is_extended
        self.location = location  # Store the raw port.location string

    def __str__(self):
        return f"{self.path} (Extended: {self.is_extended}, Location: '{self.location}')"

    def __repr__(self):
        return str(self)


def get_location_value(location_str):
    """
    Given a location string from pyserial (e.g. "1-1.1.3:1.0"), remove the interface part
    and extract a numeric value from the first subport after "1-1.".
    For example:
      "1-1.1.3:1.0" -> remove ":1.0" gives "1-1.1.3"
                     -> remove "1-1." gives "1.3"
                     -> split on '.' gives ["1", "3"] -> return int("1") i.e. 1.
      "1-1.3.3:1.0" -> returns 3.
    """
    if DEBUG:
        print(f"[DEBUG] Parsing location string: {location_str}")
    # Remove the interface part if present (e.g., ":1.0")
    if ":" in location_str:
        location_str = location_str.split(":")[0]
    prefix = "1-1."
    if location_str.startswith(prefix):
        remainder = location_str[len(prefix):]  # e.g., "1.3" or "3.3"
        parts = remainder.split(".")
        try:
            num = int(parts[0])
            if DEBUG:
                print(f"[DEBUG] Extracted numeric value: {num} from remainder: {remainder}")
            return num
        except ValueError:
            if DEBUG:
                print(f"[DEBUG] Failed to convert '{parts[0]}' to int in location '{location_str}'")
            return 0
    else:
        if DEBUG:
            print(f"[DEBUG] location_str '{location_str}' does not start with '{prefix}'")
        return 0


def find_serial_devices():
    devices = []
    ports = serial.tools.list_ports.comports()

    if DEBUG:
        print("[DEBUG] Found ports:")
    for port in ports:
        if "ACM" in port.device:
            if DEBUG:
                print(f"[DEBUG] Port: {port.device}, location: '{port.location}' (len={len(port.location)})")
            # Use the old heuristic first:
            is_extended = (len(port.location) == 11)
            devices.append(SerialDevice(port.device, is_extended, port.location))

    if DEBUG:
        print("[DEBUG] Devices after initial heuristic:")
        for dev in devices:
            print(f"  {dev}")

    # If there are exactly 2 devices and both are flagged as extended,
    # try to differentiate them using the numeric value extracted from the location.
    if len(devices) == 2 and (all(dev.is_extended for dev in devices) or all(not dev.is_extended for dev in devices)):
        if DEBUG:
            print(
                "[DEBUG] Fallback triggered: Both devices flagged as extended, invoking new algorithm using location strings.")
        new_values = []
        for dev in devices:
            val = get_location_value(dev.location)
            new_values.append(val)
            if DEBUG:
                print(f"[DEBUG] New location value for {dev.path}: {val}")

        if len(new_values) == 2 and new_values[0] != new_values[1]:
            if DEBUG:
                print(f"[DEBUG] Comparing location values: {new_values[0]} vs {new_values[1]}")
            # Assume the device with the lower numeric value is directly attached (non-extended)
            if new_values[0] < new_values[1]:
                devices[0].is_extended = False
                devices[1].is_extended = True
                if DEBUG:
                    print(f"[DEBUG] Setting {devices[0].path} as not extended and {devices[1].path} as extended")
            else:
                devices[0].is_extended = True
                devices[1].is_extended = False
                if DEBUG:
                    print(f"[DEBUG] Setting {devices[0].path} as extended and {devices[1].path} as not extended")
        else:
            if DEBUG:
                print(
                    "[DEBUG] New location values are equal or insufficient for differentiation. Retaining original heuristic.")
    else:
        if DEBUG:
            print("[DEBUG] Fallback not applicable. Either not exactly 2 devices or not all flagged as extended.")

    if DEBUG:
        print("[DEBUG] Final device list:")
        for dev in devices:
            print(f"  {dev}")
    return devices


def read_serial_device(device_name, as_hex: bool):
    try:
        with serial.Serial(device_name, baudrate=9600, timeout=0.1) as ser:
            print(f"Reading raw data from {device_name}...")
            while True:
                if ser.in_waiting > 0:
                    # Read data and clean it
                    ascii_data = ser.readline().decode("utf-8").strip()
                    if ascii_data:
                        if as_hex:
                            print(f"Received (ASCII): {ascii_data}")
                            uid_hex = decimal_to_hex(ascii_data)
                            print(f"UID0-UID3: {uid_hex}")
                            continue

                        try:
                            # Convert ASCII-encoded hex to raw bytes
                            raw_bytes = bytes.fromhex(ascii_data)
                            print(f"raw bytes: {raw_bytes}")
                            hex_output = ":".join(f"{b:02x}" for b in raw_bytes)
                            print(f"Decoded Hex: {hex_output}")

                            # Extract and display UID0-UID3 (first 4 bytes)
                            uid_bytes = raw_bytes[:4]
                            uid_hex = ":".join(f"{b:02x}" for b in uid_bytes)
                            print(f"UID0-UID3: {uid_hex}")

                        except ValueError:
                            print("Invalid ASCII-encoded hex data received.")
    except serial.SerialException as e:
        print(f"Error: {e}")


def decimal_to_hex(decimal_str):
    # Convert the decimal string to an integer
    decimal_value = int(decimal_str)
    # Convert the integer to a hexadecimal string
    hex_value = f"{decimal_value:08x}"
    # Reverse the byte order (convert to big-endian)
    reversed_hex = "".join(hex_value[i: i + 2] for i in range(len(hex_value) - 2, -1, -2))
    # Format as hex bytes with colons
    hex_uid = ":".join(reversed_hex[i: i + 2] for i in range(0, len(reversed_hex), 2))
    return hex_uid


if __name__ == "__main__":
    devices = find_serial_devices()
    print("Detected serial devices:")
    for dev in devices:
        print(f"  {dev}")
    threads = []

    for device in devices:
        thread = threading.Thread(target=read_serial_device, args=(device.path, True))
        thread.start()
        threads.append(thread)
