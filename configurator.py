import json
import subprocess


def apply_config(config):
    config_data = json.loads(config)
    if "wifi" in config:
        return apply_wifi_config(config_data["wifi"]["SSID"], config_data["wifi"]["password"])
    return config_data


def apply_wifi_config(SSID, password):
    command = f"nmcli device wifi list && sudo nmcli dev wifi connect {SSID} password {password}"
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return e.stderr.decode('utf-8')
