import serial
import serial.tools.list_ports

def find_qr_device():
    # List all serial ports
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Looking for the specific USB ACM device
        if "ACM" in port.device:
            return port.device
    return None

def read_qr_device():
    # Find the QR device
    device = find_qr_device()
    if device is None:
        print("QR code reader not found.")
        return

    print(f"Found QR code reader on {device}")

    try:
        # Open the serial connection
        with serial.Serial(device, baudrate=9600, timeout=0.1) as ser:
            print(f"Reading from {device}...")
            while True:
                # Read data from the serial port
                if ser.in_waiting > 0:
                    data = ser.readline().decode('utf-8').strip()
                    if data:
                        print(f"Received: {data}")
    except serial.SerialException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    read_qr_device()
