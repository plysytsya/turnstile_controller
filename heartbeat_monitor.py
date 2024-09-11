# sudo apt-get install python3-dbus
import json
import logging
import dbus
import os
import pathlib
import time

from dotenv import load_dotenv
from systemd.journal import JournalHandler

logger = logging.getLogger("heartbeat_monitor_logger")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

load_dotenv()

IS_BIDIRECT = bool(os.getenv("IS_BIDIRECT"))
CURRENT_DIR = pathlib.Path(__file__).parent
HEARTBEAT_FILENAMES = [
    CURRENT_DIR / "heartbeat-A.json",
    CURRENT_DIR / "heartbeat-B.json",
]
MAX_HEARTBEAT_DELAY = 60
SLEEP_INTERVAL = 20
SERVICE_TO_RESTART = "qr_script.service"

logger.info(
    f"IS_BIDIRECT: {IS_BIDIRECT}, "
    f"HEARTBEAT_FILENAMES: {HEARTBEAT_FILENAMES}, "
    f"MAX_HEARTBEAT_DELAY: {MAX_HEARTBEAT_DELAY}, "
    f"SERVICE_TO_RESTART: {SERVICE_TO_RESTART}"
)


def _is_alive(filepath: pathlib.Path) -> bool:
    if not filepath.exists():
        return False
    try:
        data = json.loads(filepath.read_text())
        timestamp = data.get("timestamp")
        if timestamp is None:
            raise ValueError("Missing 'timestamp' in heartbeat file")
        now = int(time.time())
        delay = now - timestamp
        return delay < MAX_HEARTBEAT_DELAY
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error reading or parsing heartbeat file {filepath}: {e}")
        return False


def restart_service_via_dbus(service_name):
    """Restart the given systemd service via D-Bus API."""
    try:
        # Establish connection to the system bus
        sysbus = dbus.SystemBus()

        # Get systemd1 object from the system bus
        systemd1 = sysbus.get_object('org.freedesktop.systemd1', '/org/freedesktop/systemd1')

        # Get the Manager interface from the systemd1 object
        manager = dbus.Interface(systemd1, 'org.freedesktop.systemd1.Manager')

        # Restart the service using D-Bus method RestartUnit
        manager.RestartUnit(service_name, 'fail')

        logging.info(f"Service {service_name} restarted successfully via D-Bus.")
    except dbus.DBusException as e:
        logging.error(f"Failed to restart service {service_name} via D-Bus: {e}")


if __name__ == "__main__":
    while True:
        if IS_BIDIRECT:
            heartbeat_status = all(
                _is_alive(filename) for filename in HEARTBEAT_FILENAMES
            )
        else:
            heartbeat_status = _is_alive(HEARTBEAT_FILENAMES[0]) or _is_alive(
                HEARTBEAT_FILENAMES[1]
            )

        if heartbeat_status:
            logger.info("All devices are alive.")
        else:
            logger.warning("One or more devices are not alive.")
            exit(1)
        time.sleep(20)
