import serial
import serial.tools.list_ports
import threading


class SerialDevice:
    def __init__(self, path, is_extended):
        self.path = path
        self.is_extended = is_extended

    def __str__(self):
        return f"{self.path} (Extended: {self.is_extended})"

    def __repr__(self):
        return str(self)


def find_serial_devices():
    # List all serial ports
    devices = []
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Looking for the specific USB ACM device
        if "ACM" in port.device:
            device = SerialDevice(port.device, len(port.location) == 11)
            devices.append(device)
    return devices


def read_serial_device(device_name):
    # Find the QR device

    try:
        # Open the serial connection
        with serial.Serial(device_name, baudrate=9600, timeout=0.1) as ser:
            print(f"Reading from {device_name}...")
            while True:
                # Read data from the serial port
                if ser.in_waiting > 0:
                    data = ser.readline().decode("utf-8").strip()
                    if data:
                        normalized = detect_format_and_normalize(data)
                        print(f"Received: {data}. Normalized: {normalized}")
    except serial.SerialException as e:
        print(f"Error: {e}")


def detect_format_and_normalize(uid: str) -> str:
    """
    Detects the format (decimal/hexadecimal) and byte order, then normalizes to big-endian hexadecimal.
    """
    try:
        # Step 1: Convert to hexadecimal if input is decimal
        if uid.isdigit():
            uid_hex = format(int(uid), 'X')  # Decimal to hex
        else:
            uid_hex = uid.upper()  # Assume already in hex

        # Step 2: Detect and handle little-endian
        # NFC UIDs are usually 4 or 8 bytes (8 or 16 hex characters)
        if len(uid_hex) % 2 == 0:  # Ensure even length for byte processing
            # Reconstruct big-endian order and check if it matches known patterns
            reversed_hex = ''.join(reversed([uid_hex[i:i + 2] for i in range(0, len(uid_hex), 2)]))
            # Use heuristic: reversed_hex should look more like a standard UID
            if int(reversed_hex, 16) > int(uid_hex, 16):  # Heuristic to decide byte order
                return reversed_hex
        return uid_hex
    except ValueError:
        return "Invalid UID"


if __name__ == "__main__":
    devices = find_serial_devices()
    threads = []

    for device in devices:
        thread = threading.Thread(target=read_serial_device, args=(device.path,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()
