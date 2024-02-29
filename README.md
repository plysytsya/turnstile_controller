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
4. Exit and reboot your Raspberry Pi. `sudo reboot`

## Install I2C Tools

If you haven't already, you should install the I2C tools:

```bash
sudo apt-get update
sudo apt-get install -y i2c-tools libi2c-dev
```

Install our services (QR reader and cronjob to periodically download the customer database)

```bash
make install-qr
```

```bash
make install-cronjob
```
