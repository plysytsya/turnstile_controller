import time
from threading import Thread
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
    FRAME_WIDTH = 640  # Width of the video frames
    FRAME_HEIGHT = 480  # Height of the video frames

    # Video recording parameters
    VIDEO_CODEC = 'XVID'  # Codec used for recording video
    VIDEO_FORMAT = 'avi'  # Final format of the recorded video files
    DEFAULT_FPS = 5.0  # Default FPS for recording

    def __init__(self):
        # Initialize video capture
        self.video = cv2.VideoCapture(0)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

        # Initialize motion detection variables
        self.previous_frame = None
        self.last_motion_time = None

        # Recording variables
        self.recording = False
        self.out = None
        self.fps = self.DEFAULT_FPS  # Fixed FPS
        self.recording_file = None  # Temporary file path for recording

        # Frame count variables for debugging
        self.frame_count = 0
        self.last_fps_check_time = time.time()

        # Start frame update thread
        self.thread = Thread(target=self.update_frame, args=())
        self.thread.daemon = True
        self.thread.start()

    def cleanup(self):
        """Release resources properly on exit."""
        if self.video.isOpened():
            self.video.release()
        if self.out:
            self.out.release()

    def update_frame(self):
        """Continuously capture frames, detect motion, and handle recording."""
        while True:
            start_time = time.time()

            success, frame = self.video.read()
            if not success:
                break

            # Convert to grayscale and apply Gaussian blur to reduce noise and improve detection accuracy
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            # Initialize previous_frame if it's the first frame
            if self.previous_frame is None:
                self.previous_frame = gray
                continue

            # Compute absolute difference between current frame and previous frame
            frame_delta = cv2.absdiff(self.previous_frame, gray)

            # Select motion detection parameters based on recording state
            if not self.recording:
                # Use starting parameters (less sensitive)
                thresh_sensitivity = self.START_THRESHOLD_SENSITIVITY
                min_area = self.START_MIN_AREA
            else:
                # Use continuing parameters (more sensitive)
                thresh_sensitivity = self.CONTINUE_THRESHOLD_SENSITIVITY
                min_area = self.CONTINUE_MIN_AREA

            # Apply threshold to highlight differences exceeding the sensitivity
            thresh = cv2.threshold(frame_delta, thresh_sensitivity, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)  # Dilate to fill in gaps

            # Find contours (areas of motion) in the thresholded image
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = False
            for contour in contours:
                if cv2.contourArea(contour) >= min_area:
                    motion_detected = True
                    self.last_motion_time = time.time()  # Update last motion time
                    break  # No need to check other contours

            # Update previous_frame for the next iteration
            self.previous_frame = gray

            # Handle recording based on motion detection
            if motion_detected:
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

            # Debug: Calculate and log actual FPS
            self.frame_count += 1
            current_time = time.time()
            elapsed_time = current_time - self.last_fps_check_time
            if elapsed_time >= 1.0:  # Log every second
                actual_fps = self.frame_count / elapsed_time
                logger.info(f"Actual FPS captured: {actual_fps}")
                self.frame_count = 0
                self.last_fps_check_time = current_time

            # Add a sleep to maintain consistent frame rate
            time_to_sleep = max(0, (1.0 / self.fps) - (time.time() - start_time))
            time.sleep(time_to_sleep)

        # Clean up resources when done
        self.cleanup()

    def start_recording(self, frame):
        """Start video recording."""
        # Use a codec and name the file with 'temp' as the prefix
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

            # Log recording statistics
            logger.info(f"Recording completed: {new_filename}. Frame rate: {self.fps} FPS")

    def record_frame(self, frame):
        """Write frame to the video file."""
        if self.recording and self.out is not None:
            self.out.write(frame)


# Signal handling for graceful shutdown
def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    camera.cleanup()
    logger.info("Exiting...")
    os._exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Initialize and run the video camera
if __name__ == "__main__":
    setproctitle.setproctitle("videocamera")
    camera = VideoCamera()
    logger.info("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)  # Keep the script running
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Exiting...")
        signal_handler(None, None)
