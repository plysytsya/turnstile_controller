#!/usr/bin/env python3

import json
import asyncio
import logging
import os
import pathlib
import re
import threading
import time
import uuid

import evdev
from evdev import InputDevice, categorize, KeyEvent
import requests
from dotenv import load_dotenv
import gpiod  # Changed from RPi.GPIO
import serial

from configurator import apply_config
from find_device import find_qr_devices
try:
    from i2cdetect import detect_i2c_device_not_27
except ImportError as e:
    logging.warning(f"i2cdetect module not available: {e}")
    detect_i2c_device_not_27 = None

from keymap import KEYMAP

try:
    from lcd_controller import LCDController
except ImportError as e:
    logging.warning(f"LCD controller module not available: {e}")
    LCDController = None
from systemd.journal import JournalHandler
import sentry_sdk

from serial_reader import find_serial_devices
from utils import SentryLogger

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("SENTRY_ENV"),
    traces_sample_rate=1.0,
)

load_dotenv()


# Odroid GPIO Compatibility Layer
class OdroidGPIO:
    HIGH = 1
    LOW = 0
    BCM = "BCM"
    OUT = gpiod.LINE_REQ_DIR_OUT
    
    def __init__(self):
        self.chip = None
        self.lines = {}
    
    def setmode(self, mode):
        if not self.chip:
            self.chip = gpiod.Chip("gpiochip0")
    
    def setup(self, pin, direction):
        self.setmode(self.BCM)
        try:
            line = self.chip.get_line(pin)
            line.request(consumer=f"relay_{pin}", type=direction)
            self.lines[pin] = line
            # Initialize relay to OFF state
            relay_trigger = os.getenv("RELAY_TRIGGER", "LOW")
            off_state = self.HIGH if relay_trigger == "LOW" else self.LOW
            line.set_value(off_state)
        except Exception as e:
            logging.error(f"Failed to setup GPIO pin {pin}: {e}")
    
    def output(self, pin, value):
        if pin in self.lines:
            try:
                self.lines[pin].set_value(value)
            except Exception as e:
                logging.error(f"Failed to set GPIO {pin} to {value}: {e}")
    
    def cleanup(self):
        for pin, line in self.lines.items():
            try:
                # Turn off relay
                relay_trigger = os.getenv("RELAY_TRIGGER", "LOW")
                off_state = self.HIGH if relay_trigger == "LOW" else self.LOW
                line.set_value(off_state)
                line.release()
            except:
                pass
        self.lines.clear()

# Create GPIO instance
GPIO = OdroidGPIO()


class NoDeviceFoundError(Exception):
    pass


DIRECTION = os.getenv("DIRECTION")
if DIRECTION == "A":
    os.environ["ENTRANCE_UUID"] = os.getenv("ENTRANCE_UUID_A")
    # Use new I2C settings from .env
    os.environ["LCD_I2C_ADDRESS"] = os.getenv("I2C_ADDRESS", "0x27")
    os.environ["LCD_I2C_BUS"] = os.getenv("I2C_BUS", "0")
    os.environ["RELAY_PIN_DOOR"] = os.getenv("RELAY_PIN_A", "62")  # Updated for Odroid
    os.environ["RELAY_PIN_DISPLAY"] = os.getenv("RELAY_PIN_DISPLAY_A", "69")  # Updated for Odroid
    os.environ["IS_SERIAL_DEVICE"] = "True"
    devices = find_serial_devices()
    if devices:
        os.environ["QR_USB_DEVICE_PATH"] = devices[0].path
    else:
        raise NoDeviceFoundError("No serial device found.")
elif DIRECTION == "B":
    os.environ["ENTRANCE_UUID"] = os.getenv("ENTRANCE_UUID_B")
    os.environ["LCD_I2C_ADDRESS"] = "0x27"
    os.environ["LCD_I2C_BUS"] = "0"
    os.environ["RELAY_PIN_DOOR"] = os.getenv("RELAY_PIN_B", "10")
    os.environ["RELAY_PIN_DISPLAY"] = os.getenv("RELAY_PIN_DISPLAY_B", "20")
    os.environ["IS_SERIAL_DEVICE"] = "False"
    devices = find_qr_devices()
    if devices:
        os.environ["QR_USB_DEVICE_PATH"] = devices[0].path
    else:
        raise NoDeviceFoundError("No keyboard-QR device found.")


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


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Add direction filter
    direction_filter = DirectionFilter()
    logger.addFilter(direction_filter)
    
    # Journal handler for systemd
    journal_handler = JournalHandler()
    journal_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    journal_handler.setFormatter(formatter)
    logger.addHandler(journal_handler)
    
    # Stream handler for console output
    if ENABLE_STREAM_HANDLER:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    
    return logger

logger = setup_logging()

# Environment variables
HOSTNAME = os.getenv("HOSTNAME")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
ENTRANCE_UUID = os.getenv("ENTRANCE_UUID")
RELAY_PIN_DOOR = int(os.getenv("RELAY_PIN_DOOR"))
RELAY_PIN_DISPLAY = int(os.getenv("RELAY_PIN_DISPLAY"))
RELAY_TRIGGER = os.getenv("RELAY_TRIGGER", "LOW")
RELAY_TOGGLE_DURATION = float(os.getenv("RELAY_TOGGLE_DURATION", "1"))
LCD_I2C_ADDRESS = os.getenv("LCD_I2C_ADDRESS", "0x27")
LCD_I2C_BUS = int(os.getenv("LCD_I2C_BUS", "0"))
USE_LCD = os.getenv("USE_LCD", "1") == "1"
OPEN_N_TIMES = int(os.getenv("OPEN_N_TIMES", "1"))
QR_USB_DEVICE_PATH = os.getenv("QR_USB_DEVICE_PATH")
IS_SERIAL_DEVICE = os.getenv("IS_SERIAL_DEVICE", "True").lower() == "true"

# GPIO constants for Odroid
RELAY_ON = GPIO.LOW if RELAY_TRIGGER == "LOW" else GPIO.HIGH
RELAY_OFF = GPIO.HIGH if RELAY_TRIGGER == "LOW" else GPIO.LOW

logger.info("using relay pin %s for the door. My direction is %s", RELAY_PIN_DOOR, DIRECTION)

# Initialize Relay
relay_pin = RELAY_PIN_DOOR
GPIO.setmode(GPIO.BCM)
GPIO.setup(relay_pin, GPIO.OUT)

if USE_LCD and LCDController:
    try:
        lcd = LCDController(
            use_lcd=USE_LCD,
            lcd_address=LCD_I2C_ADDRESS,
            dark_mode=DARK_MODE,
            relay_pin=RELAY_PIN_DISPLAY,
            relay_trigger=RELAY_TRIGGER,
            i2c_bus=LCD_I2C_BUS
        )
        lcd.display_text_on_lcd("Inicializando...", "")
        logger.info("LCD initialized successfully for direction %s.", DIRECTION)
    except Exception as e:
        logger.error(f"Failed to initialize LCD: {e}")
        lcd = None
else:
    lcd = None


def toggle_relay(duration=RELAY_TOGGLE_DURATION, open_n_times=OPEN_N_TIMES):
    logger.info(f"Toggling relay PIN {relay_pin}")
    open_duration = duration / open_n_times
    for _ in range(open_n_times):
        GPIO.output(relay_pin, RELAY_ON)
        time.sleep(open_duration)
    for i in range(10):
        GPIO.output(relay_pin, RELAY_OFF)


def display_on_lcd(line1, line2, timeout=3):
    """Display text on LCD"""
    if lcd:
        lcd.display_text_on_lcd_async(line1, line2, timeout)
    else:
        logger.info(f"Display: {line1} | {line2}")


def unpack_barcode(barcode_data):
    try:
        login_data = json.loads(barcode_data)
        return login_data["customer_uuid"], login_data["timestamp"]
    except Exception as e:
        display_on_lcd("codigo", "QR invalido", timeout=2)
        logger.error(f"Error unpacking barcode: {e}")
        return None, None


def authenticate_user(customer_uuid, timestamp):
    """Authenticate user with the server"""
    logger.info(f"Authenticating customer {customer_uuid}")
    
    url = f"{HOSTNAME}/api/entrance_logs/"
    payload = {
        "customer_uuid": customer_uuid,
        "entrance_uuid": ENTRANCE_UUID,
        "timestamp": timestamp
    }
    
    try:
        response = requests.post(url, json=payload, auth=(USERNAME, PASSWORD), timeout=10)
        if response.status_code == 201:
            logger.info(f"User {customer_uuid} authenticated successfully")
            return True, "Acceso permitido"
        else:
            logger.warning(f"Authentication failed: {response.status_code}")
            return False, "Acceso denegado"
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False, "Error de conexion"


def open_door():
    """Open the turnstile door"""
    logger.info("Opening door")
    display_on_lcd("Acceso", "Permitido", timeout=2)
    
    # Start relay toggle in separate thread
    relay_thread = threading.Thread(target=toggle_relay, daemon=True)
    relay_thread.start()


def process_qr_code(qr_data):
    """Process scanned QR code"""
    logger.info(f"Processing QR code: {qr_data[:20]}...")
    
    customer_uuid, timestamp = unpack_barcode(qr_data)
    if not customer_uuid:
        return
    
    display_on_lcd("Verificando...", "Espere", timeout=1)
    
    success, message = authenticate_user(customer_uuid, timestamp)
    if success:
        open_door()
    else:
        display_on_lcd("Acceso", "Denegado", timeout=2)


def read_serial_qr():
    """Read QR codes from serial device"""
    try:
        ser = serial.Serial(QR_USB_DEVICE_PATH, 9600, timeout=1)
        logger.info(f"Serial QR reader connected to {QR_USB_DEVICE_PATH}")
        
        buffer = ""
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                buffer += data
                
                # Process complete lines
                while '\n' in buffer or '\r' in buffer:
                    if '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                    else:
                        line, buffer = buffer.split('\r', 1)
                    
                    line = line.strip()
                    if line:
                        process_qr_code(line)
            
            time.sleep(0.1)
            
    except Exception as e:
        logger.error(f"Serial QR reader error: {e}")
        raise


def read_keyboard_qr():
    """Read QR codes from keyboard device"""
    try:
        device = InputDevice(QR_USB_DEVICE_PATH)
        logger.info(f"Keyboard QR reader connected to {QR_USB_DEVICE_PATH}")
        
        qr_buffer = ""
        for event in device.read_loop():
            if event.type == evdev.ecodes.EV_KEY:
                key_event = categorize(event)
                if key_event.keystate == KeyEvent.key_down:
                    key = key_event.keycode
                    if key in KEYMAP:
                        qr_buffer += KEYMAP[key]
                    elif key == 'KEY_ENTER':
                        if qr_buffer.strip():
                            process_qr_code(qr_buffer.strip())
                        qr_buffer = ""
                        
    except Exception as e:
        logger.error(f"Keyboard QR reader error: {e}")
        raise


def create_heartbeat():
    """Create heartbeat file"""
    try:
        heartbeat_data = {
            "timestamp": time.time(),
            "direction": DIRECTION,
            "status": "running"
        }
        with open(HEARTBEAT_FILE_PATH, 'w') as f:
            json.dump(heartbeat_data, f)
    except Exception as e:
        logger.error(f"Failed to create heartbeat: {e}")


def main():
    """Main function"""
    logger.info(f"Starting turnstile controller for direction {DIRECTION}")
    
    try:
        # Show ready message
        display_on_lcd("Sistema", "Listo", timeout=2)
        
        # Create initial heartbeat
        create_heartbeat()
        
        # Start heartbeat thread
        def heartbeat_loop():
            while True:
                create_heartbeat()
                time.sleep(HEARTBEAT_INTERVAL)
        
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        # Start QR reader based on device type
        if IS_SERIAL_DEVICE:
            logger.info("Starting serial QR reader")
            read_serial_qr()
        else:
            logger.info("Starting keyboard QR reader") 
            read_keyboard_qr()
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        GPIO.cleanup()
        if lcd:
            lcd.cleanup()


if __name__ == "__main__":
    main()