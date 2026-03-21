import json

import device_configurator_service as device_configurator


def main():
    payload = {
        "camera_enabled": device_configurator.camera_services_enabled(),
        "camera_services": device_configurator.current_camera_services(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
