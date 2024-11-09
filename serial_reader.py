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
                    data = ser.readline().decode('utf-8').strip()
                    if data:
                        print(f"Received: {data}")
    except serial.SerialException as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    devices = find_serial_devices()
    threads = []

    for device in devices:
        thread = threading.Thread(target=read_serial_device, args=(device.path,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()