import time
import asyncio
import os
import signal
import setproctitle
import sys
import logging
from systemd.journal import JournalHandler
from .upload_to_s3 import upload_loop

# Add the global Python library path to sys.path
sys.path.append('/usr/lib/python3/dist-packages')
import cv2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoCameraLogger")
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

class VideoCamera:
    """Video camera class that detects motion and records video upon motion detection."""

    # Motion detection parameters for starting recording
    START_THRESHOLD_SENSITIVITY = 25  # Less sensitive (higher threshold), requires more change to detect motion
    START_MIN_AREA = 1500  # Larger area (in pixels) required to consider as motion for starting recording

    # Motion detection parameters for continuing recording
    CONTINUE_THRESHOLD_SENSITIVITY = 15  # More sensitive (lower threshold), detects smaller changes
    CONTINUE_MIN_AREA = 500  # Smaller area (in pixels) to keep recording ongoing

    N_SECONDS_NO_MOTION = 3  # Number of seconds of no motion after which we stop recording

    # Video parameters
    FRAME_WIDTH = 480  # Width of the video frames
    FRAME_HEIGHT = 360  # Height of the video frames

    DEFAULT_FPS = 10.5  # Default FPS for recording

    # Video recording parameters
    VIDEO_CODEC = 'mp4v'  # Codec used for recording video
    VIDEO_FORMAT = 'mp4'  # Final format of the recorded video files

    RECORDING_DIR = '/home/manager/turnstile_controller/camera'

    def __init__(self):
        # Initialize video capture
        self.video = cv2.VideoCapture(0)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

        # Initialize motion detection variables
        self.previous_frame = None
        self.last_motion_time = time.time()
        self.recorded_times = []
        self.sleep_times = []

        # Recording variables
        self.recording = False
        self.out = None
        self.recording_file = None  # Temporary file path for recording

        # Frame count variables for debugging
        self.frame_count = 0
        self.last_fps_check_time = time.time()

        # Adjust FPS based on actual camera performance during recording
        self.fps = self.DEFAULT_FPS

    def cleanup(self):
        """Release resources properly on exit."""
        if self.video.isOpened():
            self.video.release()
        if self.out:
            self.out.release()

    def process_frame(self, frame):
        """Process a frame by converting to grayscale and applying Gaussian blur."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        return gray

    async def run(self, global_qr_data=None, lock=None):
        """Asynchronous method to run the video capturing and processing loop."""
        time_to_sleep = 0
        try:
            while True:
                start_time = time.time()

                success, frame = self.video.read()
                if not success:
                    break

                # Process the current frame (includes motion detection and recording logic)
                self._record_frame(frame, global_qr_data, lock)

                # Debug: Calculate and log actual FPS
                self.frame_count += 1
                current_time = time.time()
                elapsed_time = current_time - self.last_fps_check_time
                if elapsed_time >= 1.0:  # Log every second
                    actual_fps = self.frame_count / elapsed_time
                    logger.debug(f"Actual FPS captured: {actual_fps}")
                    if self.recording:
                        self.recorded_times.append(actual_fps)
                    self.frame_count = 0
                    self.last_fps_check_time = current_time

                # Add a sleep to maintain consistent frame rate
                time_to_sleep = max(0, (1.0 / self.fps) - (time.time() - start_time))
                await asyncio.sleep(time_to_sleep)

        except asyncio.CancelledError:
            logger.info("Run loop cancelled.")
            raise
        finally:
            # Clean up resources when done
            self.cleanup()

    def _record_frame(self, frame, global_qr_data=None, lock=None):
        """Process a single frame for motion detection and handle recording."""
        # Process the frame
        gray = self.process_frame(frame)

        # Initialize previous_frame if it's the first frame
        if self.previous_frame is None:
            self.previous_frame = gray
            return  # Skip motion detection on the first frame

        # Compute absolute difference between current frame and previous frame
        frame_delta = cv2.absdiff(self.previous_frame, gray)

        # Select motion detection parameters based on recording state
        thresh_sensitivity = (self.START_THRESHOLD_SENSITIVITY if not self.recording
                              else self.CONTINUE_THRESHOLD_SENSITIVITY)
        min_area = (self.START_MIN_AREA if not self.recording else self.CONTINUE_MIN_AREA)

        # Apply threshold to highlight differences exceeding the sensitivity
        thresh = cv2.threshold(frame_delta, thresh_sensitivity, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)  # Dilate to fill in gaps

        # Find contours (areas of motion) in the thresholded image
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Check if motion is detected
        motion_detected = any(cv2.contourArea(contour) >= min_area for contour in contours)

        # Update previous_frame for the next iteration
        self.previous_frame = gray

        # Handle recording based on motion detection
        if motion_detected:
            self.last_motion_time = time.time()
            if not self.recording:
                self.start_recording(frame)
            else:
                self.record_frame(frame)
        else:
            if self.recording:
                # Check if no motion has been detected for the specified duration
                if time.time() - self.last_motion_time >= self.N_SECONDS_NO_MOTION:
                    self.stop_recording(global_qr_data, lock)
                else:
                    self.record_frame(frame)

    def start_recording(self, frame):
        """Start video recording."""
        fourcc = cv2.VideoWriter_fourcc(*self.VIDEO_CODEC)
        timestamp = int(time.time())
        self.recording_file = f'/home/manager/turnstile_controller/camera/temp_{timestamp}_.{self.VIDEO_FORMAT}'
        self.out = cv2.VideoWriter(self.recording_file, fourcc, self.fps,
                                   (frame.shape[1], frame.shape[0]))
        self.recording = True
        logger.info(f"Started recording: {self.recording_file}")

    def stop_recording(self, global_qr_data=None, lock=None):
        """Stop video recording."""
        qr_data = read_and_delete_multi_process_qr_data(global_qr_data, lock)
        if qr_data:
            qr_timestamp = qr_data['scanned_at']
            timestamp_in_video = int(self.recording_file.split('_')[2])
            # the recording must have started before the qr code was scanned.
            # The idea is that the motion sensor would trigger a video before the qr code is scanned.
            # Otherwise this means that the video was recorded after the qr code was scanned, thus the
            # customer already walked in.
            if qr_timestamp >= timestamp_in_video and self.recording:
                self.out.release()
                self.out = None
                self.recording = False
                # Replace 'temp' with an empty string in the filename
                additional_data = f"/{qr_data['uuid']}.{self.VIDEO_FORMAT}"
                new_filename = "/".join(self.recording_file.split("/")[:-1]) + additional_data
                os.rename(self.recording_file, new_filename)
                logger.info(f"Recording saved as {new_filename}")
                return

        if self.recording:
            self.out.release()
            self.out = None
            self.recording = False

            os.remove(self.recording_file)
            logger.info(f"Recording removed")

    def record_frame(self, frame):
        """Write frame to the video file."""
        if self.recording and self.out is not None:
            self.out.write(frame)


def read_and_delete_multi_process_qr_data(global_qr_data, lock):
    """
    Reads the value from multi_process_qr_data and deletes it.

    Args:
        global_qr_data (Manager.dict): The shared dictionary.
        lock (Manager.Lock): The lock to ensure thread-safe access.

    Returns:
        dict or None: The data that was read, or None if the dictionary is empty.
    """
    logger.info(f"Trying to read global data")
    with lock:  # Acquire the lock to ensure thread safety
        if 'qr_data' in global_qr_data:
            data = global_qr_data['qr_data']
            del global_qr_data['qr_data']  # Delete the data after reading
            return data
        else:
            return None  # No data available


# Initialize and run the video camera
async def main(global_qr_data=None, lock=None):
    setproctitle.setproctitle("videocamera")
    camera = VideoCamera()
    logger.info("Press Ctrl+C to stop.")

    # Start the run() coroutine as a task
    camera_task = asyncio.create_task(camera.run(global_qr_data, lock))

    # Handle signals
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, camera_task.cancel)

    try:
        await camera_task
    except asyncio.CancelledError:
        logger.info("Camera task cancelled.")
    finally:
        camera.cleanup()
        logger.info("Exiting...")


async def run_all(global_qr_data, lock):
    await asyncio.gather(main(global_qr_data, lock), upload_loop())

def run_camera(global_qr_data=None, lock=None):
    try:
        asyncio.run(run_all(global_qr_data, lock))
    except Exception as e:
        logger.exception(f"Error running camera: {e}... Continuing")

if __name__ == "__main__":
    asyncio.run(main())
