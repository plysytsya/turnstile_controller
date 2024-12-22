import json
import subprocess
from pathlib import Path


def apply_config(config):
    config_data = json.loads(config)
    config = config_data["config"]
    if "wifi" in config:
        return apply_wifi_config(config["wifi"]["SSID"], config["wifi"]["password"])
    if "env" in config:
        return write_env_file(config["env"])
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


def write_env_file(env_dict):
    env_str = ""
    for key, value in env_dict.items():
        env_str += f'{key}="{value}"\n'
    Path("/home/manager/turnstile_controller/.env").write_text(env_str)
    reboot_cmd = "sudo reboot"
    #subprocess.run(reboot_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
