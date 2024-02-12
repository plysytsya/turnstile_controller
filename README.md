## Install git on Raspberry Pi
```bash
sudo apt update
sudo apt install git
```

## Install pip3 on Raspberry Pi
```bash
sudo apt update
sudo apt install python3-pip
```

## Clone the git repository
````bash
git clone https://github.com/plysytsya/turnstile_controller.git
````

## installar virtualenv
```
sudo apt install python3-venv
```
```
python3 -m venv /home/manager/turnstile_controller/venv
```

## activar virtualenv
```
source /home/manager/turnstile_controller/venv/bin/activate
```

### Install dependencies
```bash
pip3 install -r requirements.txt
```

### Paste .env file
```bash
nano .env
```

## Enable I2C Interface

1. Run `sudo raspi-config`.
2. Navigate to `Interface Options` or `Interfacing Options`.
3. Select `I2C` and enable it.
4. Exit and reboot your Raspberry Pi.

## Install I2C Tools

If you haven't already, you should install the I2C tools:

```bash
sudo apt-get update
sudo apt-get install -y i2c-tools libi2c-dev
```


## Register `qr_script` Service

1. **Copy the service file to the systemd directory**:
```bash
sudo cp /home/manager/turnstile_controller/qr_script.service /etc/systemd/system/
```

2. **Reload systemd to read the new configuration**:
```bash
sudo systemctl daemon-reload
```

3. **Enable the service to start on boot**:
```bash
sudo systemctl enable qr_script
```

4. **Start the service**:
```bash
sudo systemctl start qr_script
```

5. **To Confirm the Service Status**:
```bash
sudo systemctl status qr_script
```

## Unregister `qr_script` Service
```bash
sudo systemctl stop qr_script
sudo systemctl disable qr_script
sudo rm /etc/systemd/system/qr_script.service
sudo systemctl daemon-reload
sudo systemctl reset-failed
```

## Activate cronjob (systemd-scheduled) for downloading customer db in case of internet outage:
```bash
sudo cp /home/manager/turnstile_controller/download_customer_db.service /etc/systemd/system/
sudo cp /home/manager/turnstile_controller/download_customer_db.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable download_customer_db.service
sudo systemctl enable download_customer_db.timer
sudo systemctl start download_customer_db.timer
```

## Watch logs of download customer db service:
```bash
journalctl -u download_customer_db.service -f
```

## Trigger cronjob once
```bash
sudo systemctl start download_customer_db.service
```

## list all services
```bash
systemctl list-units --type=service
```

# How to Use The Makefile

This Makefile simplifies the process of managing services and cronjobs. Below are the instructions on how to use the Makefile commands.

## To Register `qr_script` Service

To install and start the `qr_script` service, run:

```bash
make install-qr
```

## To Unregister `qr_script` Service

To stop and unregister the `qr_script` service, execute:

```bash
make uninstall-qr
```

## To Activate the Cronjob for Downloading Customer DB

To set up and start the cronjob for downloading the customer database, use:

```bash
make install-cronjob
```

## To Watch Logs of the Download Customer DB Service

To watch the logs of the customer database download service, run:

```bash
make watch-cronjob
```

## To Trigger the Cronjob Once

If you need to trigger the cronjob manually once, use:

```bash
make trigger-cronjob
```

## To List All Services

To list all the services managed by your system, execute:

```bash
make list-services
```
