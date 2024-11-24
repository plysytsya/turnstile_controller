import argparse
import json
import logging
import os
import time

import imutils
import requests
from dotenv import load_dotenv
from imutils.video import VideoStream
from pyzbar import pyzbar
from rpi_lcd import LCD
from unidecode import unidecode
import RPi.GPIO as GPIO


# Configure logging
logging.basicConfig(level=logging.INFO)

load_dotenv()

# Fetch global variables from environment
ENTRANCE_UUID = os.getenv("ENTRANCE_UUID")
HOSTNAME = os.getenv("HOSTNAME")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DIRECTION = os.getenv("DIRECTION")
JWT_TOKEN = os.getenv("JWT_TOKEN")


# Initialize Relay
relay_pin = 24  # Relay is connected to GPIO 24
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(relay_pin, GPIO.OUT)  # Set pin as an output pin


def toggle_relay(duration=1):
    GPIO.output(relay_pin, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(relay_pin, GPIO.LOW)


# Initialize LCD
lcd = LCD()


def display_on_lcd(line1, line2, timeout=None):
    lcd.clear()
    lcd.text(unidecode(line1), 1)
    lcd.text(unidecode(line2), 2)
    if timeout is not None:
        time.sleep(timeout)
        lcd.clear()


def log_unsuccessful_request(response):
    log_message = "\n".join(response.text.split("\n")[-4:])
    logging.info(f"Unsuccessful request. Response: {log_message}")


def login():
    if JWT_TOKEN is not None:
        return JWT_TOKEN
    url = f"{HOSTNAME}/api/token/"
    payload = json.dumps({"email": USERNAME, "password": PASSWORD})
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code != 200:
        log_unsuccessful_request(response)
    return response.json()["access"]


def unpack_barcode(barcode_data):
    try:
        login_data = json.loads(barcode_data)
        return login_data["customer_uuid"], login_data["timestamp"]
    except Exception as e:
        display_on_lcd("Codigo", "QR invalido", timeout=2)  # Displays "Invalid QR Code" in Spanish
        logging.error(f"Error unpacking barcode: {e}")
        display_on_lcd("Escanea", "codigo QR")
        return None, None


def handle_server_response(status_code, first_name=None):
    if status_code == "UserExists":
        logging.info(f"Hola {first_name}")
        toggle_relay()
        display_on_lcd("Hola", first_name, timeout=2)
        display_on_lcd("Escanea", "codigo QR")
        return True

    elif status_code == "TimestampExpired":
        display_on_lcd("Error", "QR vencido", timeout=2)

    elif status_code == "MembershipInactive":
        display_on_lcd("Membresía", "inactiva", timeout=2)

    elif status_code == "UserDoesNotExist":
        display_on_lcd("Usuario", "no existe", timeout=2)

    else:
        display_on_lcd("Error", "Intenta de nuevo", timeout=2)

    display_on_lcd("Escanea", "codigo QR")
    return False


def verify_customer(customer_uuid, timestamp):
    url = f"{HOSTNAME}/verify_customer/"
    payload = json.dumps(
        {
            "customer_uuid": customer_uuid,
            "entrance_uuid": ENTRANCE_UUID,
            "direction": DIRECTION,
            "timestamp": timestamp,
        }
    )
    jwt_token = login()
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, data=payload)

    if response.status_code != 200:
        log_unsuccessful_request(response)
        handle_server_response(None)  # This will hit the 'else' in `handle_server_response`

    json_response = response.json()
    status_code = json_response.get("status_code")
    first_name = json_response.get("first_name")

    return handle_server_response(status_code, first_name)


def handle_keyboard_interrupt(vs):
    logging.warning("Keyboard interrupt received. Stopping video stream and exiting...")
    vs.stop()
    lcd.clear()
    exit()


def main():
    display_on_lcd("Iniciando", "sistema")
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "-o",
        "--output",
        type=str,
        default="barcodes.csv",
        help="path to output CSV file containing barcodes",
    )
    args = vars(ap.parse_args())
    logging.info("Starting video stream...")
    vs = VideoStream(usePiCamera=True).start()
    time.sleep(2.0)
    logging.info("Now scan")
    display_on_lcd("Escanea", "codigo QR")

    try:
        while True:
            frame = vs.read()
            frame = imutils.resize(frame, width=400)
            barcodes = pyzbar.decode(frame)
            for barcode in barcodes:
                try:
                    barcode_data = barcode.data.decode("utf-8")
                    customer_uuid, timestamp = unpack_barcode(barcode_data)
                    if customer_uuid and timestamp:
                        display_on_lcd("Verificando", "usuario...")  # Display message in Spanish for verifying user
                        verify_customer(customer_uuid, timestamp)
                    logging.info("Pausing for 3 seconds...")
                    time.sleep(3)
                    break  # break the for loop, to wait for next QR code
                except KeyboardInterrupt:
                    handle_keyboard_interrupt(vs)
    except KeyboardInterrupt:
        handle_keyboard_interrupt(vs)


if __name__ == "__main__":
    main()
