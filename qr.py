import asyncio
import json
import logging
import os
import pathlib
import time

import RPi.GPIO as GPIO
import evdev
import requests
from dotenv import load_dotenv
from evdev import InputDevice, categorize, KeyEvent

from find_device import find_qr_device
from keymap import KEYMAP
from lcd_controller import LCDController

logging.basicConfig(level=logging.INFO)

load_dotenv()

jwt_token = None

# Fetch global variables from environment
HOSTNAME = os.getenv("HOSTNAME")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DIRECTION = os.getenv("DIRECTION")
JWT_TOKEN = os.getenv("JWT_TOKEN")

ENTRANCE_UUID = os.getenv("ENTRANCE_UUID")
USE_LCD = int(os.getenv("USE_LCD", 1))
RELAY_PIN_DOOR = int(os.getenv("RELAY_PIN_DOOR", 24))
NUM_RELAY_TOGGLES = int(os.getenv("TOGGLES", 1))
TOGGLE_DURATION = float(os.getenv("DURATION", 1.0))
I2C_ADDRESS = int(os.getenv("I2CADDRESS"), 16)

# Initialize Relay
relay_pin = RELAY_PIN_DOOR
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(relay_pin, GPIO.OUT)  # Set pin as an output pin

lcd_controller = LCDController(USE_LCD, lcd_address=I2C_ADDRESS)

# Initialize the InputDevice
timeout_end_time = time.time() + 300  # 5 minutes from now

while time.time() < timeout_end_time:
    try:
        dev = InputDevice(find_qr_device())
        logging.info("Successfully connected to the QR code scanner.")
        lcd_controller.display("Conectado al", "escaneador QR")
        break  # Exit the loop since we've successfully connected
    except FileNotFoundError:
        logging.warning("Failed to connect to the QR code scanner. Retrying in 15 seconds...")
        lcd_controller.display("Fallo al conectar", "Cambia USB en 15s")
        time.sleep(15)  # Wait for 15 seconds before retrying

# If we get to this point and `dev` is not defined, we've exhausted our retries
if "dev" not in locals():
    logging.error("Failed to connect to the QR code scanner after multiple attempts.")
    lcd_controller.display("No se pudo conectar", "Verifica USB")

# List to hold decoded QR data
shared_list = []


def log_unsuccessful_request(response):
    endpoint = response.url  # Get the URL from the response object
    log_message = "\n".join(response.text.split("\n")[-4:])
    logging.info(f"Unsuccessful request to endpoint {endpoint}. Response: {log_message}")


def toggle_relay(duration: float = 1.0, toggles: int = 1):
    for _ in range(toggles):
        GPIO.output(relay_pin, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(relay_pin, GPIO.LOW)


async def keyboard_event_loop(device):
    global shared_list
    output_string = ""
    lcd_controller.display("Escanea", "codigo QR...")

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
        lcd_controller.display("codigo", "QR invalido", timeout=2)  # Displays "Invalid QR Code" in Spanish
        logging.error(f"Error unpacking barcode: {e}")
        lcd_controller.display("Escanea", "codigo QR")
        return None, None


def handle_server_response(status_code, first_name=None):
    if status_code == "UserExists":
        return open_door_and_greet(first_name)

    elif status_code == "TimestampExpired":
        lcd_controller.display("Error", "QR vencido", timeout=2)

    elif status_code == "MembershipInactive":
        lcd_controller.display("Membresía", "inactiva", timeout=2)

    elif status_code == "UserDoesNotExist":
        lcd_controller.display("Usuario", "no existe", timeout=2)

    else:
        lcd_controller.display("Error", "Intenta de nuevo", timeout=2)

    lcd_controller.display("Escanea", "codigo QR")
    return False


def open_door_and_greet(first_name):
    logging.info(f"Hola {first_name}")
    toggle_relay(duration=TOGGLE_DURATION, toggles=NUM_RELAY_TOGGLES)
    lcd_controller.display("Hola", first_name, timeout=2)
    lcd_controller.display("Escanea", "codigo QR")
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
            lcd_controller.display("No internet", "Reintentando...")
            time.sleep(sleep_duration)  # sleep for 10 seconds before retrying
    logging.error("Exhausted all retries. Check your internet connection.")
    lcd_controller.display("Sin internet", "Verifica conexión", timeout=20)
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
        lcd_controller.display("Login", "Failed", timeout=2)
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
    is_found = _find_customer_in_cache(customer_uuid)
    if is_found:
        return is_found
    try:
        response = post_request(url, headers, payload, retries=5)
    except requests.exceptions.RequestException:
        return post_request(url, headers, payload)

    if response is None or response.status_code not in (200, 401, 403):
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
            lcd_controller.display("Verificando", "QR...")
            verify_customer(qr_data["customer-uuid"], qr_data["timestamp"])
        await asyncio.sleep(1)  # 1-second delay to avoid busy-waiting


def run(direction, entrance_uuid, relay_pin_door, i2c_address, use_lcd, login_credentials, num_relay_toggles=1,
        toggle_duration=1.0):
    global DIRECTION, ENTRANCE_UUID, RELAY_PIN_DOOR, TOGGLES, DURATION, I2CADDRESS, USE_LCD, HOSTNAME, USERNAME, PASSWORD
    DIRECTION = direction
    ENTRANCE_UUID = entrance_uuid
    RELAY_PIN_DOOR = str(relay_pin_door)
    TOGGLES = str(num_relay_toggles)
    DURATION = str(toggle_duration)
    I2CADDRESS = str(i2c_address)
    USE_LCD = str(use_lcd)
    HOSTNAME = login_credentials["hostname"]
    USERNAME = login_credentials["username"]
    PASSWORD = login_credentials["password"]

    logging.info("initializing ENTRACE_UUID: %s", entrance_uuid)
    logging.info("using relay pin %s for the door", relay_pin_door)
    logging.info("using %s toggles for the relay", num_relay_toggles)
    logging.info("using %s seconds for the relay", toggle_duration)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.gather(keyboard_event_loop(dev), main_loop()))
    except KeyboardInterrupt:
        logging.warning("Received exit signal.")


if __name__ == "__main__":
    logging.info("initializing ENTRACE_UUID: %s", ENTRANCE_UUID)
    logging.info("using relay pin %s for the door", RELAY_PIN_DOOR)
    logging.info("using %s toggles for the relay", NUM_RELAY_TOGGLES)
    logging.info("using %s seconds for the relay", TOGGLE_DURATION)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.gather(keyboard_event_loop(dev), main_loop()))
    except KeyboardInterrupt:
        logging.warning("Received exit signal.")
