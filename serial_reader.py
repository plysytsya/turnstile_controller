import serial
import serial.tools.list_ports
import threading
import binascii


class SerialDevice:
    def __init__(self, path, is_extended):
        self.path = path
        self.is_extended = is_extended

    def __str__(self):
        return f"{self.path} (Extended: {self.is_extended})"

    def __repr__(self):
        return str(self)


def find_serial_devices():
    devices = []
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "ACM" in port.device:
            device = SerialDevice(port.device, len(port.location) == 11)
            devices.append(device)
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
    reversed_hex = "".join(hex_value[i : i + 2] for i in range(len(hex_value) - 2, -1, -2))
    # Format as hex bytes with colons
    hex_uid = ":".join(reversed_hex[i : i + 2] for i in range(0, len(reversed_hex), 2))
    return hex_uid


if __name__ == "__main__":
    devices = find_serial_devices()
    threads = []

    for device in devices:
        thread = threading.Thread(target=read_serial_device, args=(device.path, True))
        thread.start()
        threads
