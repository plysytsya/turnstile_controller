import time
import asyncio
import os
import signal
import setproctitle
import sys
import logging

# Add the global Python library path to sys.path
sys.path.append('/usr/lib/python3/dist-packages')
import cv2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoCameraLogger")

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

    # Video recording parameters
    VIDEO_CODEC = 'XVID'  # Codec used for recording video
    VIDEO_FORMAT = 'avi'  # Final format of the recorded video files

    def __init__(self):
        # Initialize video capture
        self.video = cv2.VideoCapture(0)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

        # Initialize motion detection variables
        self.previous_frame = None
        self.last_motion_time = time.time()
        self.recorded_times = []

        # Recording variables
        self.recording = False
        self.out = None
        self.recording_file = None  # Temporary file path for recording

        # Frame count variables for debugging
        self.frame_count = 0
        self.last_fps_check_time = time.time()

        # Adjust FPS based on actual camera performance during recording
        self.fps = 12  # Default FPS
        logger.info("finally set the fps to {}".format(self.fps))

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

    async def run(self):
        """Asynchronous method to run the video capturing and processing loop."""
        time_to_sleep = 0
        try:
            while True:
                start_time = time.time()

                success, frame = self.video.read()
                if not success:
                    break

                # Process the current frame (includes motion detection and recording logic)
                self._record_frame(frame)

                # Debug: Calculate and log actual FPS
                self.frame_count += 1
                current_time = time.time()
                elapsed_time = current_time - self.last_fps_check_time
                if elapsed_time >= 1.0:  # Log every second
                    actual_fps = self.frame_count / (elapsed_time - time_to_sleep)
                    logger.info(f"Actual FPS captured: {actual_fps}. Time slept (ms): {time_to_sleep * 1000}")
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

    def _record_frame(self, frame):
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
                    self.stop_recording()
                else:
                    self.record_frame(frame)

    def start_recording(self, frame):
        """Start video recording."""
        fourcc = cv2.VideoWriter_fourcc(*self.VIDEO_CODEC)
        timestamp = int(time.time())
        self.recording_file = f'temp_{timestamp}.avi'
        self.out = cv2.VideoWriter(self.recording_file, fourcc, self.fps,
                                   (frame.shape[1], frame.shape[0]))
        self.recording = True
        logger.info(f"Started recording: {self.recording_file}")

    def stop_recording(self):
        """Stop video recording."""
        if self.recording:
            self.out.release()
            self.out = None
            self.recording = False

            # Replace 'temp' with an empty string in the filename
            new_filename = self.recording_file.replace('temp_', '')
            os.rename(self.recording_file, new_filename)
            logger.info(f"Recording saved as {new_filename}")
            self._recalculate_fps()

    def _recalculate_fps(self):
        """Recalculate the FPS based on the actual recorded frame rates."""
        if self.recorded_times:
            self.fps = sum(self.recorded_times) / len(self.recorded_times)
            logger.info(f"New FPS calculated: {self.fps}")
            self.recorded_times = []

    def record_frame(self, frame):
        """Write frame to the video file."""
        if self.recording and self.out is not None:
            self.out.write(frame)


# Initialize and run the video camera
async def main():
    setproctitle.setproctitle("videocamera")
    camera = VideoCamera()
    logger.info("Press Ctrl+C to stop.")

    # Start the run() coroutine as a task
    camera_task = asyncio.create_task(camera.run())

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

if __name__ == "__main__":
    asyncio.run(main())
