import asyncio
import json
import os
import time
import logging
import socket
import bluetooth
from systemd.journal import JournalHandler
from dotenv import load_dotenv
from tenacity import retry, stop_after_delay, wait_fixed, RetryError

# Load environment variables and ensure RECORDING_DIR is set
load_dotenv()
RECORDING_DIR = os.getenv("RECORDING_DIR")
if not RECORDING_DIR:
    raise ValueError("RECORDING_DIR environment variable not set.")

# Constants
POLL_INTERVAL_MS = 30  # Poll interval in milliseconds (not used for socket timeout)

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bluetooth receiver")
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

@retry(stop=stop_after_delay(5), wait=wait_fixed(0.5), reraise=True)
async def accept_connection(server_sock):
    """
    Attempt to accept a connection using the Bluetooth server socket.
    Retries for up to 5 seconds with a 0.5 second wait between attempts.
    """
    return await asyncio.to_thread(server_sock.accept)

async def handle_client(client_sock):
    """
    Handles a connected Bluetooth client.
    Receives data using a blocking call via asyncio.to_thread.
    When valid data is received, writes a file named {uuid}.txt containing the timestamp,
    and touches record.txt in the RECORDING_DIR.
    """
    while True:
        try:
            # Block until data is received (similar to the working bluez_listener.py)
            data = await asyncio.to_thread(client_sock.recv, 1024)
        except Exception as e:
            logger.error("Error receiving data: %s", e)
            break

        if not data:
            logger.info("Client disconnected.")
            break

        try:
            decoded = data.decode().strip()
            payload = json.loads(decoded)
            # Expect payload of format: [uuid, timestamp]
            if isinstance(payload, list) and len(payload) == 2:
                uuid_val = payload[0]
                timestamp_val = payload[1]
                file_path = os.path.join(RECORDING_DIR, f"{uuid_val}.txt")
                with open(file_path, "w") as f:
                    json.dump({"timestamp": timestamp_val}, f)

                record_path = os.path.join(RECORDING_DIR, "record.txt")
                with open(record_path, "w") as f:
                    f.write("")

                logger.info("Received data for UUID: %s with timestamp: %s", uuid_val, timestamp_val)
            else:
                logger.warning("Payload not in expected format: %s", decoded)
        except Exception as e:
            logger.exception("Failed to process received data: %s", e)

    try:
        client_sock.close()
    except Exception:
        pass

async def bluetooth_service():
    """
    Main asynchronous loop that starts the Bluetooth server, waits for client connections,
    and uses tenacity to handle reconnects for up to 5 seconds after a connection failure.
    """
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", 1))
    server_sock.listen(1)
    logger.info("Bluetooth service started, waiting for connection on RFCOMM channel 1...")

    while True:
        try:
            client_sock, address = await accept_connection(server_sock)
            logger.info("Accepted connection from %s", address)
            await handle_client(client_sock)
        except RetryError as e:
            logger.error("Failed to accept connection within retry period: %s", e)
            break
        except Exception as e:
            logger.exception("Error in bluetooth service loop: %s", e)
            await asyncio.sleep(1)

    server_sock.close()

def main():
    try:
        asyncio.run(bluetooth_service())
    except Exception as e:
        logger.exception("Bluetooth service encountered an error: %s", e)

if __name__ == "__main__":
    main()