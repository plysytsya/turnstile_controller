from evdev import InputDevice, list_devices


def find_qr_devices():
    device_name_substrings = ["TMC HIDKeyBoard", "Megahunt", "YOKO HID GUM", "TMC HIDKeyBoard", "WCM HIDKeyBoard"]
    devices = [InputDevice(path) for path in list_devices()]
    found_devices = []

    for device in devices:
        print(device)
        if any(name.lower() in device.name.lower() for name in device_name_substrings):
            print("Found device", device)
            found_devices.append(device)

    if not found_devices:
        print("Could not find the QR device!")
        exit(1)

    return found_devices


if __name__ == "__main__":
    device_path = find_qr_devices()
    if device_path:
        print("Device path:", device_path)
