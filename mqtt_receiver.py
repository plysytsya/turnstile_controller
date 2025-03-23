import json
import os
import logging
from uuid import UUID

import paho.mqtt.client as mqtt
from systemd.journal import JournalHandler
from dotenv import load_dotenv
import sentry_sdk

# Load environment variables and ensure RECORDING_DIR is set
load_dotenv()

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("SENTRY_ENV"),
    traces_sample_rate=1.0,
)

RECORDING_DIR = os.getenv("RECORDING_DIR")
if not RECORDING_DIR:
    raise ValueError("RECORDING_DIR environment variable not set.")

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mqtt_receiver")
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

def on_connect(client, userdata, flags, rc):
    logger.info("Connected with result code " + str(rc))
    # Subscribe to the MQTT topic where messages are published
    client.subscribe("home/raspberry")

def on_message(client, userdata, msg):
    try:
        decoded = msg.payload.decode().strip()
        payload = json.loads(decoded)
        # Expect payload in the format: [uuid, timestamp]
        if isinstance(payload, list) and len(payload) == 2:
            uuid_val = payload[0]
            try:
                # Validate that the first element is a proper UUID
                UUID(uuid_val)
            except ValueError:
                logger.info("Invalid UUID received: %s", uuid_val)
                return
            timestamp_val = payload[1]
            # Write the timestamp to a file named {uuid}.txt in the RECORDING_DIR
            file_path = os.path.join(RECORDING_DIR, f"{uuid_val}.txt")
            with open(file_path, "w") as f:
                json.dump({"timestamp": timestamp_val}, f)
            # Touch record.txt in the same directory
            record_path = os.path.join(RECORDING_DIR, "record.txt")
            with open(record_path, "w") as f:
                f.write("")
            logger.info("Received data for UUID: %s with timestamp: %s", uuid_val, timestamp_val)
        else:
            logger.warning("Payload not in expected format: %s", decoded)
    except Exception as e:
        logger.exception("Failed to process received data: %s", e)

def main():
    client = mqtt.Client()
    # Set MQTT username and password if provided in the environment variables
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    if username and password:
        client.username_pw_set(username, password)

    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the MQTT broker (defaults to 127.0.0.1:1883 if not set in env)
    mqtt_broker = os.getenv("MQTT_BROKER", "127.0.0.1")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    client.connect(mqtt_broker, mqtt_port, 60)

    # Start the network loop; this call blocks and handles reconnects automatically
    client.loop_forever()

if __name__ == "__main__":
    main()