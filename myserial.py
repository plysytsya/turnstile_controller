import serial

# Adjust this to the actual device name you see in `dmesg | grep tty`
PORT = "/dev/ttyUSB0"   # or "/dev/ttyAMA0" if it's on UART pins
BAUDRATE = 9600         # common for readers; change if your reader uses another speed

def main():
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        print(f"Listening on {PORT} at {BAUDRATE} baud...")

        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                print(f"Read: {line}")

    except serial.SerialException as e:
        print(f"Serial error: {e}")

if __name__ == "__main__":
    main()
