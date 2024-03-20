import json
import asyncio
import logging
import os
import pathlib
import time

import evdev
from evdev import InputDevice, categorize, KeyEvent
import requests
from dotenv import load_dotenv
import RPi.GPIO as GPIO

from keymap import KEYMAP
from lcd_controller import LCDController

logging.basicConfig(level=logging.INFO)

load_dotenv()

jwt_token = None

ENTRANCE_UUID = os.getenv("ENTRANCE_UUID")
HOSTNAME = os.getenv("HOSTNAME")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DIRECTION = os.getenv("DIRECTION")
JWT_TOKEN = os.getenv("JWT_TOKEN")
USE_LCD = int(os.getenv("USE_LCD", 1))
RELAY_PIN_DOOR = int(os.getenv("RELAY_PIN_DOOR", 24))
LCD_I2C_ADDRESS = int(os.getenv("LCD_I2C_ADDRESS", 0x27), 16)
QR_USB_DEVICE_PATH = os.getenv("QR_USB_DEVICE_PATH")

logging.info("using relay pin %s for the door", RELAY_PIN_DOOR)

# Initialize Relay
relay_pin = RELAY_PIN_DOOR
RELAY_PIN_QR_READER = 22  # Hopefully we never again have to use a relay to restart the qr reader
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(relay_pin, GPIO.OUT)  # Set pin as an output pin

if USE_LCD:
    # Initialize LCD
    lcd = LCDController(use_lcd=USE_LCD, lcd_address=LCD_I2C_ADDRESS)


def scroll_text(line, max_char_count=16, delay=0.2):
    line_length = len(line)
    if line_length <= max_char_count:
        return [line]

    scroll_positions = line_length - max_char_count + 1
    return [line[i : i + max_char_count] for i in range(scroll_positions)]


def display_on_lcd(line1, line2, timeout=None):
    if not USE_LCD:
        logging.info(line1)
        logging.info(line2)
    else:
        lcd.display(line1, line2, timeout)


def reconnect_qr_reader():
    GPIO.setup(RELAY_PIN_QR_READER, GPIO.OUT)  # set up pin as an output pin

    logging.info("Attempting to reconnect the QR scanner via relay...")
    display_on_lcd("Reconectando", "escaner QR...")

    GPIO.output(RELAY_PIN_QR_READER, GPIO.HIGH)  # turn relay on
    time.sleep(1)  # Wait for 1 second
    GPIO.output(RELAY_PIN_QR_READER, GPIO.LOW)  # turn relay off

    logging.info("Reconnection attempt via relay completed.")
    display_on_lcd("Intento de", "reconexión hecho")
    time.sleep(3)


reconnect_qr_reader()

# Initialize the InputDevice
timeout_end_time = time.time() + 300  # 5 minutes from now

while time.time() < timeout_end_time:
    try:
        dev = InputDevice(QR_USB_DEVICE_PATH)
        logging.info("Successfully connected to the QR code scanner.")
        display_on_lcd("Conectado al", "escaneador QR")
        break  # Exit the loop since we've successfully connected
    except FileNotFoundError:
        logging.warning("Failed to connect to the QR code scanner. Retrying in 15 seconds...")
        display_on_lcd("Fallo al conectar", "Cambia USB en 15s")
        time.sleep(15)  # Wait for 15 seconds before retrying

# If we get to this point and `dev` is not defined, we've exhausted our retries
if "dev" not in locals():
    logging.error("Failed to connect to the QR code scanner after multiple attempts.")
    display_on_lcd("No se pudo conectar", "Verifica USB")

# List to hold decoded QR data
shared_list = []


def log_unsuccessful_request(response):
    endpoint = response.url  # Get the URL from the response object
    log_message = "\n".join(response.text.split("\n")[-4:])
    logging.info(f"Unsuccessful request to endpoint {endpoint}. Response: {log_message}")


def toggle_relay(duration=1):
    GPIO.output(relay_pin, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(relay_pin, GPIO.LOW)


async def keyboard_event_loop(device):
    global shared_list
    output_string = ""
    display_on_lcd("Escanea", "codigo QR...")

    async for event in device.async_read_loop():
        if event.type == evdev.ecodes.EV_KEY:
            categorized_event = categorize(event)
            if categorized_event.keystate == KeyEvent.key_up:
                keycode = categorized_event.keycode
                character = KEYMAP.get(keycode, "")

                if character:
                    output_string += character

                if keycode == "KEY_ENTER":
                    try:
                        output_string = "{" + output_string.lstrip("{")
                        qr_dict = json.loads(output_string)
                        shared_list.append(qr_dict)
                        output_string = ""
                    except json.JSONDecodeError:
                        logging.error("Invalid JSON data.")
                        output_string = ""


def unpack_barcode(barcode_data):
    try:
        login_data = json.loads(barcode_data)
        return login_data["customer_uuid"], login_data["timestamp"]
    except Exception as e:
        display_on_lcd("codigo", "QR invalido", timeout=2)  # Displays "Invalid QR Code" in Spanish
        logging.error(f"Error unpacking barcode: {e}")
        display_on_lcd("Escanea", "codigo QR")
        return None, None


def handle_server_response(status_code, first_name=None):
    if status_code == "UserExists":
        return open_door_and_greet(first_name)

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


def open_door_and_greet(first_name):
    logging.info(f"Hola {first_name}")
    toggle_relay()
    display_on_lcd("Hola", first_name, timeout=2)
    display_on_lcd("Escanea", "codigo QR")
    return True


def load_customers_cache():
    script_path = pathlib.Path(__file__).parent
    cache_file_path = script_path / "customer.json"
    if cache_file_path.exists():
        with cache_file_path.open() as cache_file:
            return json.load(cache_file)
    return []


customers_cache = load_customers_cache()


def post_request(url, headers, payload, retries=60, sleep_duration=10):
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, data=payload)
            return response
        except requests.exceptions.RequestException as e:
            logging.warning(f"Internet connection error: {e}. Retrying...")
            display_on_lcd("No internet", "Reintentando...")
            time.sleep(sleep_duration)  # sleep for 10 seconds before retrying
    logging.error("Exhausted all retries. Check your internet connection.")
    display_on_lcd("Sin internet", "Verifica conexión", timeout=20)
    return None


def login():
    global jwt_token
    if jwt_token:
        return jwt_token

    url = f"{HOSTNAME}/api/token/"
    payload = json.dumps({"email": USERNAME, "password": PASSWORD})
    headers = {"Content-Type": "application/json"}

    response = post_request(url, headers, payload)

    if response is None or response.status_code != 200:
        log_unsuccessful_request(response)
        display_on_lcd("Login", "Failed", timeout=2)
        return None

    jwt_token = response.json().get("access", None)
    return jwt_token


def verify_customer(customer_uuid, timestamp):
    global jwt_token

    url = f"{HOSTNAME}/verify_customer/"
    payload = json.dumps(
        {
            "customer_uuid": customer_uuid,
            "entrance_uuid": ENTRANCE_UUID,
            "direction": DIRECTION,
            "timestamp": timestamp,
        }
    )

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    response = get_valid_response(url, headers, payload, customer_uuid)

    if response is None:
        return

    if response.status_code in (401, 403):  # Token expired or invalid
        headers["Authorization"] = refresh_token()
        response = get_valid_response(url, headers, payload, customer_uuid)
        if response is None:
            return

    json_response = response.json()
    status_code = json_response.get("status_code")
    first_name = json_response.get("first_name")

    return handle_server_response(status_code, first_name)


def get_valid_response(url, headers, payload, customer_uuid):
    try:
        response = post_request(url, headers, payload, retries=5)
    except requests.exceptions.RequestException:
        return _find_customer_in_cache(customer_uuid) or post_request(url, headers, payload)

    if response is None or response.status_code not in (200, 401, 403):
        logging.error(f"Invalid response: {response} {response.text}")
        handle_server_response(None)
        if response:
            log_unsuccessful_request(response)
        return None
    return response


def _find_customer_in_cache(customer_uuid):
    for customer in customers_cache:
        if customer["customer_uuid"] == customer_uuid and customer["active_membership"]:
            logging.info(f"Found customer {customer_uuid} in cache.")
            return open_door_and_greet(customer["first_name"])
    return None


def refresh_token():
    global jwt_token
    jwt_token = login()
    return f"Bearer {jwt_token}"


def handle_keyboard_interrupt(vs):
    logging.warning("Keyboard interrupt received. Stopping video stream and exiting...")
    lcd.clear()
    GPIO.cleanup()  # This will reset all GPIO ports you have used in this program back to input mode.
    exit()


async def main_loop():
    global shared_list

    while True:
        if shared_list:
            qr_data = shared_list.pop(0)
            logging.info(f"Received QR data: {qr_data}")
            display_on_lcd("Verificando", "QR...")
            verify_customer(qr_data["customer-uuid"], qr_data["timestamp"])
        await asyncio.sleep(1)  # 1-second delay to avoid busy-waiting


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.gather(keyboard_event_loop(dev), main_loop()))
    except KeyboardInterrupt:
        logging.warning("Received exit signal.")
