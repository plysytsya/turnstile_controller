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

IS_BIDIRECT = bool(os.getenv("IS_BIDIRECT"))
CURRENT_DIR = pathlib.Path(__file__).parent
HEARTBEAT_FILENAMES = [
    CURRENT_DIR / "heartbeat-A.json",
    CURRENT_DIR / "heartbeat-B.json",
]
MAX_HEARTBEAT_DELAY = 60
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
    logger.warning(f"Restarting service {SERVICE_TO_RESTART}...")
    try:
        subprocess.run(["systemctl", "restart", SERVICE_TO_RESTART], check=True)
        logger.warning(f"Service {SERVICE_TO_RESTART} restarted successfully.")
    except subprocess.CalledProcessError as e:
        logger.exception(f"Failed to restart service {SERVICE_TO_RESTART}: {e}")


if __name__ == "__main__":
    if IS_BIDIRECT == "1":
        heartbeat_status = all(_is_alive(filename) for filename in HEARTBEAT_FILENAMES)
    else:
        heartbeat_status = _is_alive(HEARTBEAT_FILENAMES[0]) or _is_alive(
            HEARTBEAT_FILENAMES[1]
        )

    if heartbeat_status:
        logger.info("All devices are alive.")
    else:
        logger.warning("One or more devices are not alive.")
        exit(1)
