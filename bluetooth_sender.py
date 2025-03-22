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

load_dotenv()

# Set up our special logger
logging.setLoggerClass(SentryLogger)
logger = logging.getLogger("bluetooth_sender")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

# Global socket variable (used by our retry routine)
sock = None

@retry(stop=stop_after_delay(2), wait=wait_fixed(0.1))
async def send_with_reconnect(payload: str):
    """
    Attempts to send the payload.
    If sending fails, tries to reconnect and re-raises the exception
    so that Tenacity can retry the send until 2 seconds have elapsed.
    """
    global sock
    try:
        sock.send(payload)
        logger.info(f"Sent payload: {payload}")
    except Exception as send_err:
        logger.error(f"Send failed: {send_err}. Attempting reconnect...")
        try:
            sock.close()
        except Exception as close_err:
            logger.error(f"Error closing socket: {close_err}")
        # Reconnect using environment parameters
        server_mac = os.getenv("BLUETOOTH_MAC")
        if not server_mac:
            logger.error("Error: BLUETOOTH_MAC environment variable is not set.")
            return
        port = int(os.getenv("BLUETOOTH_PORT", 1))
        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        sock.connect((server_mac, port))
        # Re-raise the exception to trigger a retry attempt
        raise send_err


async def scan_and_send(recording_dir: str):
    """
    Scans the specified directory for files matching the pattern and sends the JSON payload.
    Uses the send_with_reconnect function to enforce a 2-second send deadline.
    """
    while True:
        for filename in os.listdir(recording_dir):
            # Check for expected pattern: {entrance_log_uuid}_{timestamp}.txt
            import time  # ensure this import is present at the top

            # In scan_and_send, replace the old parsing block with:

            if filename.endswith('.txt') and filename != "record.txt":
                file_path = os.path.join(recording_dir, filename)

                # Extract the entrance_log_uuid from the filename (strip the .txt extension)
                entrance_log_uuid = filename[:-4]

                # Deduce the timestamp from the file's metadata (modification time)
                file_mtime = int(os.path.getmtime(file_path))
                now = int(time.time())

                # If the file is older than 3 seconds, delete it and skip processing
                if now - file_mtime > 3:
                    logger.warning(f"File {filename} is older than 3 seconds (age: {now - file_mtime}s), deleting.")
                    os.remove(file_path)
                    continue

                # Build JSON payload: [entrance_log_uuid, file_mtime]
                payload = [entrance_log_uuid, file_mtime]
                json_payload = json.dumps(payload)

                try:
                    # Attempt to send with retries (within a 2-second window)
                    await send_with_reconnect(json_payload)
                except RetryError as retry_err:
                    logger.error(f"Failed to send payload within 2 seconds: {retry_err}. Deleting file.")
                    # Delete the file and propagate error so journalctl can restart the process
                    os.remove(file_path)
                    raise retry_err
                else:
                    # If send was successful, remove the file
                    os.remove(file_path)
        # Async sleep for 30ms between scans
        await asyncio.sleep(0.03)


async def main():
    global sock
    # Get recording directory from environment variable
    recording_dir = os.getenv("RECORDING_DIR")
    if not recording_dir:
        logger.error("Error: RECORDING_DIR environment variable is not set.")
        return

    # Get Bluetooth connection parameters
    server_mac = os.getenv("BLUETOOTH_MAC", "B8:27:EB:A0:7E:6D")
    port = int(os.getenv("BLUETOOTH_PORT", 1))

    # Establish a Bluetooth RFCOMM connection that remains open
    try:
        sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        sock.connect((server_mac, port))
        logger.info(f"Connected to Bluetooth server at {server_mac}:{port}")
    except Exception as conn_err:
        logger.error(f"Failed to connect via Bluetooth: {conn_err}")
        raise conn_err

    try:
        await scan_and_send(recording_dir)
    except asyncio.CancelledError as e:
        logger.error(f"Scanner task cancelled: {e}")
    finally:
        sock.close()
        print("Bluetooth socket closed.")

if __name__ == "__main__":
    asyncio.run(main())
