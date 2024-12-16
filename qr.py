import json
import asyncio
import logging
import os
import pathlib
import sys
import threading
import time
import uuid

import evdev
from evdev import InputDevice, categorize, KeyEvent
import requests
from dotenv import load_dotenv
import RPi.GPIO as GPIO
import serial
from keymap import KEYMAP
from lcd_controller import LCDController
from systemd.journal import JournalHandler

from utils import SentryLogger

DIRECTION = os.getenv("DIRECTION")
ENTRANCE_DIRECTION = os.getenv("ENTRANCE_DIRECTION")
ENABLE_STREAM_HANDLER = os.getenv("ENABLE_STREAM_HANDLER", "False").lower() == "true"
DARK_MODE = os.getenv("DARK_MODE", "False").lower() == "true"
MAGIC_TIMESTAMP = 1725628212
current_dir = pathlib.Path(__file__).parent
HEARTBEAT_FILE_PATH = current_dir / f"heartbeat-{DIRECTION}.json"
HEARTBEAT_INTERVAL = 15


class DirectionFilter(logging.Filter):
    def filter(self, record):
        record.msg = f"{DIRECTION} - {record.msg}"
        return True

logging.setLoggerClass(SentryLogger)
logger = logging.getLogger("qr_logger")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
journal_handler.addFilter(DirectionFilter())
logger.addHandler(journal_handler)

if ENABLE_STREAM_HANDLER:
    # Stream handler (for stdout)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    logger.addHandler(stream_handler)

# Example log message
logger.info(f"Starting QR script. My direction is {DIRECTION}")


load_dotenv()

jwt_token = None

ENTRANCE_UUID = os.getenv("ENTRANCE_UUID")
HOSTNAME = os.getenv("HOSTNAME")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
JWT_TOKEN = os.getenv("JWT_TOKEN")
USE_LCD = int(os.getenv("USE_LCD", 1))
RELAY_PIN_DOOR = int(os.getenv("RELAY_PIN_DOOR", 10))
RELAY_PIN_DISPLAY = int(os.getenv("RELAY_PIN_DISPLAY")) if os.getenv("RELAY_PIN_DISPLAY") else None
RELAY_TOGGLE_DURATION = int(os.getenv("RELAY_TOGGLE_DURATION", 1))
OPEN_N_TIMES = int(os.getenv("OPEN_N_TIMES", 1))
IS_SERIAL_DEVICE = os.getenv("IS_SERIAL_DEVICE").lower() == "true"
OUTPUT_ENDIAN = os.getenv("OUTPUT_ENDIAN", "big")

if USE_LCD:
    try:
        LCD_I2C_ADDRESS = int(os.getenv("LCD_I2C_ADDRESS", 0x27), 16)
    except Exception as e:
        logger.warning(f"Error parsing LCD I2C address: {e}. Continuing without")
        USE_LCD = False

QR_USB_DEVICE_PATH = os.getenv("QR_USB_DEVICE_PATH")

logger.info("using relay pin %s for the door. My direction is %s", RELAY_PIN_DOOR, DIRECTION)

# Initialize Relay
relay_pin = RELAY_PIN_DOOR
RELAY_PIN_QR_READER = 22  # Hopefully we never again have to use a relay to restart the qr reader
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering
GPIO.setup(relay_pin, GPIO.OUT)  # Set pin as an output pin

if USE_LCD:
    # Initialize LCD
    try:
        lcd = LCDController(use_lcd=USE_LCD, lcd_address=LCD_I2C_ADDRESS, dark_mode=DARK_MODE, relay_pin=RELAY_PIN_DISPLAY)
        lcd.display("Inicializando...", "")
        logger.info("LCD initialized successfully for direction %s.", DIRECTION)
    except Exception as e:
        logger.exception(
            f"Error initializing LCD direction {DIRECTION} on "
            f"address {LCD_I2C_ADDRESS}. Continuing without LCD: {e}"
        )
        USE_LCD = False


def display_on_lcd(line1, line2, timeout=None):
    if not USE_LCD:
        logger.info(line1)
        logger.info(line2)
    else:
        lcd.display(line1, line2, timeout)


def init_qr_device():
    global dev
    # Initialize the InputDevice
    timeout_end_time = time.time() + 300  # 5 minutes from now
    while time.time() < timeout_end_time:
        try:
            dev = (
                serial.Serial(QR_USB_DEVICE_PATH, baudrate=9600, timeout=0.1)
                if IS_SERIAL_DEVICE
                else InputDevice(QR_USB_DEVICE_PATH)
            )
            logger.info("Successfully connected to the QR code scanner.")
            display_on_lcd("Conectado al", "escaneador QR")

            if IS_SERIAL_DEVICE:
                # we were just testing the serial connection
                dev.close()
            return dev
        except FileNotFoundError:
            logger.warning("Failed to connect to the QR code scanner. Retrying in 15 seconds...")
            display_on_lcd("Fallo al conectar", "Cambia USB en 15s")
            time.sleep(15)  # Wait for 15 seconds before retrying
    # If we get to this point and `dev` is not defined, we've exhausted our retries
    if "dev" not in locals():
        logger.error("Failed to connect to the QR code scanner after multiple attempts.")
        display_on_lcd("No se pudo conectar", "Verifica USB")
    return dev


# List to hold decoded QR data
shared_list = []


def log_unsuccessful_request(response):
    endpoint = response.url  # Get the URL from the response object
    log_message = "\n".join(response.text.split("\n")[-4:])
    logger.info(f"Unsuccessful request to endpoint {endpoint}. Response: {log_message}")


def toggle_relay(duration=RELAY_TOGGLE_DURATION, open_n_times=OPEN_N_TIMES):
    logger.info(f"Toggling relay PIN {relay_pin}")
    open_duration = duration / open_n_times
    for _ in range(open_n_times):
        GPIO.output(relay_pin, GPIO.HIGH)
        time.sleep(open_duration)
    for i in range(10):
        GPIO.output(relay_pin, GPIO.LOW)


def unpack_barcode(barcode_data):
    try:
        login_data = json.loads(barcode_data)
        return login_data["customer_uuid"], login_data["timestamp"]
    except Exception as e:
        display_on_lcd("codigo", "QR invalido", timeout=2)  # Displays "Invalid QR Code" in Spanish
        logger.error(f"Error unpacking barcode: {e}")
        display_on_lcd("Escanea", "codigo QR")
        return None, None


def handle_server_response(status_code, first_name=None):
    if status_code == "UserExists":
        return open_door_and_greet(first_name)

    elif status_code == "MembershipInactive":
        display_on_lcd("Membresía", "inactiva", timeout=2)

    elif status_code == "UserDoesNotExist":
        display_on_lcd("Usuario", "no existe", timeout=2)

    else:
        display_on_lcd("Error", "Intenta de nuevo", timeout=2)

    display_on_lcd("Escanea", "codigo QR")
    return False


def open_door_and_greet(first_name):
    if ENTRANCE_DIRECTION == DIRECTION:
        greet_word = "Hola"
    else:
        greet_word = "Adios"
    logger.info(f"{greet_word}, {first_name}!")
    logger.info(f"Opening door...with pin {RELAY_PIN_DOOR}")

    # Start a new thread to toggle the relay
    relay_thread = threading.Thread(target=toggle_relay)
    relay_thread.start()

    # Continue with the display updates in the main thread
    display_on_lcd(f"{greet_word}", first_name, timeout=3)
    display_on_lcd("Escanea", "codigo QR")

    # Optionally, wait for the relay thread to finish if necessary
    # relay_thread.join()

    return True


def load_customers_cache():
    script_path = pathlib.Path(__file__).parent
    cache_file_path = script_path / "customers.json"
    if cache_file_path.exists():
        with cache_file_path.open() as cache_file:
            return json.load(cache_file)
    return {}


def post_request(url, headers, payload, retries=10, sleep_duration=10):
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload)
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Eerror: {e}. Retrying...")
            display_on_lcd("No internet", "Reintentando...")
            time.sleep(sleep_duration)  # sleep for 10 seconds before retrying
    logger.error("Exhausted all retries. Check your internet connection.")
    display_on_lcd("Sin internet", "Verifica conexión", timeout=20)
    return None


def send_entrance_log(url, headers, payload, retries=3, sleep_duration=5):
    _uuid = generate_uuid_from_string(str(payload))
    payload["uuid"] = _uuid
    for i in range(retries):
        try:
            response = requests.put(url, headers=headers, json=payload)
            if response.status_code == 200:
                logger.info(f"Entrance log sent successfully: {payload}")
            else:
                logger.error(f"Failed to send entrance log: {response.text}")
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Internet connection error when sending entrance-log: {e}. Retrying...")
            time.sleep(sleep_duration)  # sleep for 10 seconds before retrying
    return None


def generate_uuid_from_string(input_string):
    # Use a predefined namespace (e.g., UUID namespace for DNS)
    namespace = uuid.NAMESPACE_DNS

    # Generate a UUID using UUID5, which is based on the SHA-1 hash of a namespace and a name (your string)
    generated_uuid = uuid.uuid5(namespace, input_string)

    return str(generated_uuid)


def login():
    global jwt_token
    if jwt_token:
        return jwt_token

    url = f"{HOSTNAME}/api/token/"
    payload = {"email": USERNAME, "password": PASSWORD}
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
    payload = {
        "customer_uuid": customer_uuid,
        "entrance_uuid": ENTRANCE_UUID,
        "direction": DIRECTION,
        "timestamp": timestamp,
    }

    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    if not is_valid_timestamp(timestamp):
        display_on_lcd("Error", "QR vencido", timeout=2)
        payload["response_code"] = "TimestampExpired"
        send_entrance_log(url, headers, payload)
        display_on_lcd("Escanea", "codigo QR")
        return

    if timestamp == MAGIC_TIMESTAMP:  # update the magic timestamp after check to create a proper entrance-log
        payload["timestamp"] = int(time.time())

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


def is_valid_timestamp(timestamp: int):
    """Timestamp can't be older than 10 seconds"""
    timestamp = int(timestamp)
    if timestamp == MAGIC_TIMESTAMP:  # magic timestamp for card users which are an exception
        return True
    current_time = int(time.time())
    if current_time - timestamp > 60:
        return False
    return True


def get_valid_response(url, headers, payload, customer_uuid):
    status_code, customer = _find_customer_in_cache(customer_uuid)
    if status_code == "UserExists":
        open_door_and_greet(customer["first_name"])
        payload["response_code"] = status_code
        send_entrance_log(url, headers, payload, retries=15)
        return None
    else:
        response = post_request(url, headers, payload, retries=5)
        logger.info(f"Response: {response.json()}")

    if response is None or response.status_code not in (200, 401, 403):
        logger.error(f"Invalid response: {response} {response.headers}")
        handle_server_response(None)
        if response:
            log_unsuccessful_request(response)
        return None
    return response


def _find_customer_in_cache(customer_uuid):
    customers = load_customers_cache()
    customer = customers.get(customer_uuid, None)
    if customer:
        if customer["active_membership"] or customer["is_staff"]:
            logger.info(f"Found customer {customer_uuid} in cache.")
            return "UserExists", customer
        else:
            return "MembershipInactive", None
    return "UserDoesNotExist", None


def refresh_token():
    global jwt_token
    jwt_token = login()
    return f"Bearer {jwt_token}"


def handle_keyboard_interrupt(vs):
    logger.warning("Keyboard interrupt received. Stopping video stream and exiting...")
    lcd.clear()
    GPIO.cleanup()  # This will reset all GPIO ports you have used in this program back to input mode.
    exit()


async def heartbeat():
    while True:
        try:
            timestamp = int(time.time())
            heartbeat_data = {"timestamp": timestamp, "direction": DIRECTION}

            # Write to the file
            heartbeat_file = pathlib.Path(HEARTBEAT_FILE_PATH)
            with heartbeat_file.open("w") as f:
                json.dump(heartbeat_data, f)

        except Exception as e:
            logger.error(f"Failed to write heartbeat: {e}")

        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def keyboard_event_loop(device):
    global shared_list
    output_string = ""
    display_on_lcd("Escanea", "codigo QR...")

    try:
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
                            logger.error("Invalid JSON data.")
                            output_string = ""
    except OSError as e:
        lcd.display("No coneccion con", "lector, reinicio")
        logger.error(f"OSError detected: {e}. Exiting the script to trigger systemd restart...")
        sys.exit(1)  # Exit with non-zero code to signal failure to systemd


async def serial_device_event_loop():
    global shared_list
    display_on_lcd("Escanea", "codigo QR...")

    try:
        with serial.Serial(QR_USB_DEVICE_PATH, baudrate=9600, timeout=0.1) as ser:
            while True:
                # Read data from the serial port
                if ser.in_waiting > 0:
                    data = ser.readline().decode('utf-8').strip()
                    logger.info(f"Received: {data}")
                    try:
                        qr_dict = json.loads(data)
                        customer = qr_dict.get("customer-uuid", qr_dict.get("customer_uuid"))
                        verify_customer(customer, qr_dict["timestamp"])
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        if len(data) > 15:
                            display_on_lcd("datos invalidos", "", timeout=2)
                            display_on_lcd("Escanea", "codigo QR...")
                            logger.warning(f"Invalid JSON data: {data}")
                            await asyncio.sleep(0.1)
                            continue
                        verify_customer(hash_uuid(data), int(time.time()))
                await asyncio.sleep(0.2)
    except OSError as e:
        lcd.display("No coneccion con", "lector, reinicio")
        logger.error(f"OSError detected: {e}. Exiting the script to trigger systemd restart...")
        sys.exit(1)  # Exit with non-zero code to signal failure to systemd
    except (serial.SerialException, Exception) as e:
        logger.exception(f"Error: {e}")


def read_serial_device(device_name):
    # Find the QR device

    try:
        # Open the serial connection
        with serial.Serial(device_name, baudrate=9600, timeout=0.1) as ser:
            print(f"Reading from {device_name}...")
            while True:
                # Read data from the serial port
                if ser.in_waiting > 0:
                    data = ser.readline().decode('utf-8').strip()
                    if data:
                        print(f"Received: {data}")
    except serial.SerialException as e:
        print(f"Error: {e}")


def hash_uuid(input_string) -> str:
    # Use uuid5 with a standard namespace (NAMESPACE_DNS) for consistent hashing
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, input_string))


async def main_loop():
    global shared_list

    login()

    while True:
        if shared_list:
            qr_data = shared_list.pop(0)
            logger.info(f"Received QR data: {qr_data}")
            customer = qr_data.get("customer-uuid", qr_data.get("customer_uuid"))
            verify_customer(customer, qr_data["timestamp"])
        await asyncio.sleep(0.1)  # 1-second delay to avoid busy-waiting


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    dev = init_qr_device()
    try:
        if IS_SERIAL_DEVICE:
            loop.run_until_complete(asyncio.gather(serial_device_event_loop(), heartbeat()))
        else:
            loop.run_until_complete(asyncio.gather(keyboard_event_loop(dev), main_loop(), heartbeat()))
    except KeyboardInterrupt:
        logger.warning("Received exit signal.")
