import smbus2


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


def detect_i2c_device_b(bus_number):
    devices = i2cdetect(bus_number)
    if len(devices) == 1 and "0x27" in devices:
        return [dev for dev in devices if dev != "0x27"][0]


if __name__ == "__main__":
    print(i2cdetect(1))
