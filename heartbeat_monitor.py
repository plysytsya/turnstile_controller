import json
import logging
import os
import pathlib
import subprocess
import time

from dotenv import load_dotenv
from systemd.journal import JournalHandler

logger = logging.getLogger("heartbeat_monitor_logger")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

load_dotenv()

IS_BIDIRECT = os.getenv("IS_BIDIRECT").lower() in ("true", "1", "yes")
CURRENT_DIR = pathlib.Path(__file__).parent
HEARTBEAT_FILENAMES = [
    CURRENT_DIR / "heartbeat-A.json",
    CURRENT_DIR / "heartbeat-B.json",
]
MAX_HEARTBEAT_DELAY = 30
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


def restart_service():
    """Restart the given systemd service."""
    logging.warning("Attempting to restart service qr_script.service...")
    # Use sudo to restart the service
    result = subprocess.run(
        ["sudo", "systemctl", "restart", "qr_script.service"],
        check=True,
        capture_output=True,
        text=True,
    )
    logging.warning(
        f"Service qr_script.service restarted successfully: {result.stdout}"
    )


if __name__ == "__main__":
    while True:
        if IS_BIDIRECT:
            heartbeat_status = all(
                _is_alive(filename) for filename in HEARTBEAT_FILENAMES
            )
        else:
            a_alive = _is_alive(HEARTBEAT_FILENAMES[0])
            b_alive = _is_alive(HEARTBEAT_FILENAMES[1])
            heartbeat_status = a_alive or b_alive

        if not heartbeat_status:
            logger.warning("One or more devices are not alive.")
            restart_service()
        time.sleep(20)
