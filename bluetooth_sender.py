import logging
import os
import asyncio
import json
import time

import bluetooth
from dotenv import load_dotenv
from tenacity import retry, stop_after_delay, wait_fixed, RetryError

from utils import SentryLogger
from systemd.journal import JournalHandler

# Load environment variables
load_dotenv()

# === Constants ===
SCAN_INTERVAL_MS = 30          # Interval between scan cycles
PING_INTERVAL_SECONDS = 20     # Interval between connection health pings
MAX_TRANSMISSION_TIME = 1.0    # Max allowed time (in seconds) for a Bluetooth send operation

# Set up our special logger
logging.setLoggerClass(SentryLogger)
logger = logging.getLogger("bluetooth_sender")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

# Global socket variable (used by our retry routine)
sock = None
sock_lock = asyncio.Lock()

@retry(stop=stop_after_delay(2), wait=wait_fixed(0.1))
async def send_with_reconnect(payload: str):
    global sock
    async with sock_lock:
        try:
            # Append a newline as a delimiter to ensure messages don't get concatenated.
            payload_with_delimiter = payload + "\n"
            sock.send(payload_with_delimiter.encode('utf-8'))
            logger.info(f"Sent payload: {payload}")
        except Exception as send_err:
            logger.error(f"Send failed: {send_err}. Attempting reconnect...")
            try:
                sock.close()
            except Exception as close_err:
                logger.error(f"Error closing socket: {close_err}")
            server_mac = os.getenv("BLUETOOTH_MAC")
            if not server_mac:
                logger.error("Error: BLUETOOTH_MAC environment variable is not set.")
                return
            port = int(os.getenv("BLUETOOTH_PORT", 1))
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((server_mac, port))
            raise send_err


async def scan_and_send(recording_dir: str):
    """
    Scans the specified directory for files matching the pattern and sends the JSON payload.
    Uses the send_with_reconnect function to enforce a 2-second send deadline.
    If the transmission takes longer than MAX_TRANSMISSION_TIME seconds, the script exits.
    """
    while True:
        for filename in os.listdir(recording_dir):
            if filename.endswith('.txt') and filename != "record.txt":
                file_path = os.path.join(recording_dir, filename)
                entrance_log_uuid = filename[:-4]
                file_mtime = int(os.path.getmtime(file_path))
                now = int(time.time())

                if now - file_mtime > 3:
                    logger.warning(f"File {filename} is older than 3 seconds (age: {now - file_mtime}s), deleting.")
                    os.remove(file_path)
                    continue

                payload = [entrance_log_uuid, file_mtime]
                json_payload = json.dumps(payload)

                try:
                    start_time = time.time()
                    await send_with_reconnect(json_payload)
                    elapsed = time.time() - start_time
                    if elapsed > MAX_TRANSMISSION_TIME:
                        logger.error(f"Transmission took too long: {elapsed:.3f}s, exiting to force restart.")
                        raise Exception("Transmission timeout")
                except RetryError as retry_err:
                    logger.error(f"Failed to send payload within 2 seconds: {retry_err}. Deleting file.")
                    os.remove(file_path)
                    raise retry_err
                else:
                    os.remove(file_path)
        await asyncio.sleep(SCAN_INTERVAL_MS / 1000)

async def send_ping():
    """
    Sends a ping payload every PING_INTERVAL_SECONDS to verify Bluetooth connection.
    Exits if ping takes too long, so journalctl can restart the service.
    """
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        try:
            ping_payload = json.dumps(["ping", int(time.time())])
            start_time = time.time()
            await send_with_reconnect(ping_payload)
            elapsed = time.time() - start_time
            if elapsed > MAX_TRANSMISSION_TIME:
                logger.error(f"Ping transmission took too long: {elapsed:.3f}s, exiting to force restart.")
                raise Exception("Ping transmission timeout")
            logger.info("Ping sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send ping: {e}. Exiting to force restart.")
            raise e

async def main():
    global sock
    recording_dir = os.getenv("RECORDING_DIR")
    if not recording_dir:
        logger.error("Error: RECORDING_DIR environment variable is not set.")
        return

    server_mac = os.getenv("BLUETOOTH_MAC", "B8:27:EB:A0:7E:6D")
    port = int(os.getenv("BLUETOOTH_PORT", 1))

    try:
        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        sock.connect((server_mac, port))
        logger.info(f"Connected to Bluetooth server at {server_mac}:{port}")
    except Exception as conn_err:
        logger.error(f"Failed to connect via Bluetooth: {conn_err}")
        raise conn_err

    try:
        await asyncio.gather(
            scan_and_send(recording_dir),
            send_ping()
        )
    except asyncio.CancelledError as e:
        logger.error(f"Task cancelled: {e}")
    finally:
        sock.close()
        logger.info("Bluetooth socket closed.")

if __name__ == "__main__":
    asyncio.run(main())
