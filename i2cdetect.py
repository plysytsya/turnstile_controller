import smbus2
import logging


def i2cdetect(bus_number):
    bus = smbus2.SMBus(bus_number)
    devices = []
    for device in range(128):
        try:
            bus.read_byte(device)
            devices.append(hex(device))
        except:
            pass  # No device at that address
    return devices


if __name__ == "__main__":
    print(i2cdetect(1))
