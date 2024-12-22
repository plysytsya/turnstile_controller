import json
import subprocess


def apply_config(config):
    config_data = json.loads(config)
    config = config_data["config"]
    if "wifi" in config:
        return apply_wifi_config(config["wifi"]["SSID"], config["wifi"]["password"])
    return config


def apply_wifi_config(SSID, password):
    command = f"sudo nmcli device wifi list && sudo nmcli dev wifi connect {SSID} password {password}"
    verify_command = "sudo nmcli device show --active"
    try:
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = subprocess.run(verify_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if SSID in result.stdout.decode('utf-8'):
            return "OK"
    except subprocess.CalledProcessError as e:
        return e.stderr.decode('utf-8')
