from evdev import InputDevice, list_devices


def find_qr_device():
    device_name_substrings = ["TMC HIDKeyBoard", "Megahunt", "YOKO HID GUM", "TMC HIDKeyBoard"]
    devices = [InputDevice(path) for path in list_devices()]
    for device in devices:
        print(device)
        if any(name.lower() in device.name.lower() for name in device_name_substrings):
            print("Found device", device)
            return device.path  # Return the device path
    else:
        print("Could not find the QR device!")
        exit(1)


if __name__ == "__main__":
    device_path = find_qr_device()
    if device_path:
        print("Device path:", device_path)
