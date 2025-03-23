import logging
import os
import asyncio
import json
import time

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from tenacity import retry, stop_after_delay, wait_fixed, RetryError

from utils import SentryLogger
from systemd.journal import JournalHandler
import sentry_sdk

# Load environment variables
load_dotenv()

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("SENTRY_ENV"),
    traces_sample_rate=1.0,
)

# === Constants ===
SCAN_INTERVAL_MS = 30          # Interval between scan cycles
PING_INTERVAL_SECONDS = 20     # Unused with MQTT, kept here for reference
MAX_TRANSMISSION_TIME = 1.0    # Max allowed time (in seconds) for a send operation

# Set up our special logger
logging.setLoggerClass(SentryLogger)
logger = logging.getLogger("mqtt_sender")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

# Global MQTT client and lock
client = None
client_lock = asyncio.Lock()

@retry(stop=stop_after_delay(2), wait=wait_fixed(0.1))
async def send_with_reconnect(topic: str, payload: str):
    """
    Attempts to publish the payload to the specified MQTT topic.
    On failure, it will try to reconnect the client and then re-raise the error.
    """
    global client
    async with client_lock:
        try:
            # Publish asynchronously by offloading to a thread
            info = await asyncio.to_thread(client.publish, topic, payload)
            # Wait for the publish to complete
            await asyncio.to_thread(info.wait_for_publish)
            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                raise Exception(f"Publish returned error code: {info.rc}")
            logger.info(f"Sent payload: {payload} to topic: {topic}")
        except Exception as send_err:
            logger.error(f"Publish failed: {send_err}. Attempting reconnect...")
            try:
                await asyncio.to_thread(client.disconnect)
                await asyncio.to_thread(client.loop_stop)
            except Exception as disconnect_err:
                logger.error(f"Error disconnecting client: {disconnect_err}")
            mqtt_broker = os.getenv("MQTT_BROKER")
            if not mqtt_broker:
                logger.error("Error: MQTT_BROKER environment variable is not set.")
                return
            port = int(os.getenv("MQTT_PORT", 1883))
            # Create a new client instance and reconnect
            client = mqtt.Client()
            try:
                await asyncio.to_thread(client.connect, mqtt_broker, port, 60)
                client.loop_start()  # Start the network loop in a background thread
                logger.info(f"Reconnected to MQTT broker at {mqtt_broker}:{port}")
            except Exception as conn_err:
                logger.error(f"Failed to connect via MQTT: {conn_err}")
            raise send_err

async def scan_and_send(recording_dir: str):
    """
    Scans the specified directory for files matching the pattern and sends the JSON payload
    over MQTT using the send_with_reconnect function. If transmission takes too long, an exception
    is raised to force a restart.
    """
    # Use MQTT topic from environment variable; default to "home/raspberry"
    mqtt_topic = os.getenv("MQTT_TOPIC", "home/raspberry")
    while True:
        for filename in os.listdir(recording_dir):
            if filename.endswith('.txt') and filename != "record.txt":
                logger.info(f"Found file: {filename}")
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
                    await send_with_reconnect(mqtt_topic, json_payload)
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

async def main():
    global client
    recording_dir = os.getenv("RECORDING_DIR")
    if not recording_dir:
        logger.error("Error: RECORDING_DIR environment variable is not set.")
        return

    mqtt_broker = os.getenv("MQTT_BROKER")
    if not mqtt_broker:
        logger.error("Error: MQTT_BROKER environment variable is not set.")
        return
    port = int(os.getenv("MQTT_PORT", 1883))

    try:
        client = mqtt.Client()
        client.connect(mqtt_broker, port, 60)
        client.loop_start()  # Start MQTT network loop in a background thread
        logger.info(f"Connected to MQTT broker at {mqtt_broker}:{port}")
    except Exception as conn_err:
        logger.error(f"Failed to connect via MQTT: {conn_err}")
        raise conn_err

    try:
        # Since MQTT manages keep-alives internally, we no longer need to send pings manually.
        await scan_and_send(recording_dir)
    except asyncio.CancelledError as e:
        logger.error(f"Task cancelled: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info("MQTT client disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
