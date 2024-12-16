import json
import logging
import os
import pathlib
import asyncio
import subprocess
from aiofiles import open as aio_open
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
MAX_HEARTBEAT_DELAY = 120
SLEEP_INTERVAL = 120
SERVICE_TO_RESTART = "qr_script.service"

logger.info(
    f"IS_BIDIRECT: {IS_BIDIRECT}, "
    f"HEARTBEAT_FILENAMES: {HEARTBEAT_FILENAMES}, "
    f"MAX_HEARTBEAT_DELAY: {MAX_HEARTBEAT_DELAY}, "
    f"SERVICE_TO_RESTART: {SERVICE_TO_RESTART}"
)

async def _is_alive(filepath: pathlib.Path) -> bool:
    if not filepath.exists():
        return False
    try:
        async with aio_open(filepath, mode='r') as f:
            content = await f.read()
            data = json.loads(content)
        timestamp = data.get("timestamp")
        if timestamp is None:
            raise ValueError("Missing 'timestamp' in heartbeat file")
        now = int(time.time())
        delay = now - timestamp
        return delay < MAX_HEARTBEAT_DELAY
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error reading or parsing heartbeat file {filepath}: {e}")
        return False

async def restart_service():
    """Restart the given systemd service."""
    logger.warning("Attempting to restart service qr_script.service...")
    process = await asyncio.create_subprocess_exec(
        "sudo", "systemctl", "restart", SERVICE_TO_RESTART,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        logger.warning(f"Service {SERVICE_TO_RESTART} restarted successfully: {stdout.decode().strip()}")
    else:
        logger.error(f"Failed to restart service {SERVICE_TO_RESTART}: {stderr.decode().strip()}")

async def monitor_heartbeat():
    while True:
        if IS_BIDIRECT:
            heartbeat_status = all(
                await asyncio.gather(*[_is_alive(filename) for filename in HEARTBEAT_FILENAMES])
            )
        else:
            a_alive, b_alive = await asyncio.gather(
                _is_alive(HEARTBEAT_FILENAMES[0]),
                _is_alive(HEARTBEAT_FILENAMES[1])
            )
            heartbeat_status = a_alive or b_alive

        if not heartbeat_status:
            logger.warning("One or more devices are not alive.")
            await restart_service()
        await asyncio.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    asyncio.run(monitor_heartbeat())
