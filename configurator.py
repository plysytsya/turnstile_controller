import json
import subprocess


def apply_config(config):
    config_data = json.loads(config)
    config = config_data["config"]
    if "wifi" in config:
        return apply_wifi_config(config["wifi"]["SSID"], config["wifi"]["password"])
    return config


def apply_wifi_config(SSID, password):
    command = f"nmcli device wifi list && sudo nmcli dev wifi connect {SSID} password {password}"
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return e.stderr.decode('utf-8')
