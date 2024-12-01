import time
import asyncio
import os
import signal
import setproctitle
import sys
import logging
from systemd.journal import JournalHandler

# Import the upload_to_s3 module
from upload_to_s3 import VideoUploader

# Add the global Python library path to sys.path
sys.path.append("/usr/lib/python3/dist-packages")
import cv2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoCamera")
journal_handler = JournalHandler()
logger.addHandler(journal_handler)
logger.propagate = False


class VideoCamera:
    """Video camera class that records video upon QR data trigger."""

    # Video parameters
    FRAME_WIDTH = 480  # Width of the video frames
    FRAME_HEIGHT = 360  # Height of the video frames

    DEFAULT_FPS = 18  # Increased FPS for recording

    # Video recording parameters
    VIDEO_CODEC = "H264"  # Codec used for recording video
    VIDEO_FORMAT = "mp4"  # Final format of the recorded video files

    RECORDING_DURATION = 6  # Duration to record after trigger (in seconds)
    QR_DATA_CHECK_INTERVAL = 0.2  # Interval to check for QR data (in seconds)

    def __init__(self, settings):
        self.RECORDING_DIR = settings.RECORDING_DIR

        # Recording variables
        self.recording = False
        self.recording_start_time = None
        self.out = None
        self.video = None
        self.recording_file = None  # Temporary file path for recording
        self.current_qr_data = None  # Store QR data for filename

        # Adjust FPS based on actual camera performance during recording
        self.fps = self.DEFAULT_FPS
        self.uploader = VideoUploader(settings)

    def cleanup(self):
        """Release resources properly on exit."""
        if self.video and self.video.isOpened():
            self.video.release()
        if self.out:
            self.out.release()

    async def run(self, global_qr_data=None, lock=None):
        """Asynchronous method to check for QR data and start recording."""
        try:
            while True:
                # Check for QR data trigger
                qr_data = read_and_delete_multi_process_qr_data(global_qr_data, lock)
                if qr_data:
                    await self.start_recording(qr_data)
                await asyncio.sleep(self.QR_DATA_CHECK_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Run loop cancelled.")
            raise
        except Exception as e:
            logger.exception("Exception in VideoCamera.run")
        finally:
            # Clean up resources when done
            self.cleanup()

    async def start_recording(self, qr_data):
        """Start video recording."""
        start = time.time()
        self.video = cv2.VideoCapture(0)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

        fourcc = cv2.VideoWriter_fourcc(*self.VIDEO_CODEC)
        timestamp = int(time.time())
        self.recording_file = f"{self.RECORDING_DIR}/temp_{timestamp}_.{self.VIDEO_FORMAT}"
        self.current_qr_data = qr_data  # Store QR data for later use

        # Check if camera is opened successfully
        if not self.video.isOpened():
            logger.error("Failed to open camera.")
            return

        # Read the first frame to get frame dimensions
        ret, frame = self.video.read()
        if not ret:
            logger.error("Failed to read frame from camera.")
            self.video.release()
            return

        self.out = cv2.VideoWriter(
            self.recording_file,
            fourcc,
            self.fps,
            (int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))),
        )
        self.recording = True
        self.recording_start_time = time.time()
        logger.info(f"Started recording: {self.recording_file}. Took {time.time() - start:.2f} seconds to init.")

        # Record frames for RECORDING_DURATION seconds
        frame_interval = 1.0 / self.fps
        end_time = self.recording_start_time + self.RECORDING_DURATION

        while time.time() < end_time:
            frame_start_time = time.time()
            ret, frame = self.video.read()
            if not ret:
                logger.error("Failed to read frame from camera.")
                break
            self.out.write(frame)
            # Sleep to maintain FPS
            elapsed = time.time() - frame_start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        await self.stop_recording()

    async def stop_recording(self):
        """Stop video recording."""
        if self.recording:
            self.out.release()
            self.video.release()
            self.out = None
            self.video = None
            self.recording = False

            if self.current_qr_data:
                uuid = self.current_qr_data.get('uuid', 'unknown')
                new_filename = f"{self.RECORDING_DIR}/{uuid}.{self.VIDEO_FORMAT}"
                os.rename(self.recording_file, new_filename)
                self.recording_file = new_filename
                logger.info(f"Recording saved as {self.recording_file}")
            else:
                logger.warning("No QR data available to rename the recording file.")

            # Trigger uploader
            await self.uploader.upload()
        else:
            logger.info("No recording to stop.")


def read_and_delete_multi_process_qr_data(global_qr_data, lock):
    """
    Reads the value from multi_process_qr_data and deletes it.

    Args:
        global_qr_data (Manager.dict): The shared dictionary.
        lock (Manager.Lock): The lock to ensure thread-safe access.

    Returns:
        dict or None: The data that was read, or None if the dictionary is empty.
    """
    with lock:  # Acquire the lock to ensure thread safety
        if "qr_data" in global_qr_data:
            data = global_qr_data["qr_data"]
            del global_qr_data["qr_data"]  # Delete the data after reading
            return data
        else:
            return None  # No data available


# Initialize and run the video camera
async def main(settings, global_qr_data=None, lock=None):
    setproctitle.setproctitle("videocamera")
    camera = VideoCamera(settings)
    logger.info("Press Ctrl+C to stop.")

    # Start the run() coroutine as a task
    camera_task = asyncio.create_task(camera.run(global_qr_data, lock))

    # Handle signals
    loop = asyncio.get_running_loop()

    def shutdown():
        logger.info("Received shutdown signal.")
        for task in [camera_task]:
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    tasks = [camera_task]

    try:
        # Wait for tasks to complete
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Main tasks cancelled.")
    except Exception as e:
        logger.exception("Exception in main")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        camera.cleanup()
        logger.info("Exiting...")


def run_camera(settings, global_qr_data=None, lock=None):
    try:
        asyncio.run(main(settings, global_qr_data, lock))
    except Exception as e:
        logger.exception(f"Error running camera: {e}... Continuing")


if __name__ == "__main__":
    import dotenv

    # the path of the .env file which is in the deirectory that is one level up from the current directory
    path_to_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env")

    dotenv.load_dotenv(path_to_env)

    class CameraSettings:
        """Configuration settings for camera video uploads and S3 integration."""
        S3_BUCKET = os.getenv("S3_BUCKET")
        S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
        S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
        S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
        GYM_UUID = os.getenv("GYM_UUID")
        RECORDING_DIR = os.getenv("RECORDING_DIR")
        HOSTNAME = os.getenv("HOSTNAME")
        USERNAME = os.getenv("USERNAME")
        PASSWORD = os.getenv("PASSWORD")

    camera  = VideoCamera(CameraSettings())
    camera.start_recording()
