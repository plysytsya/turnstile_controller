import time
from threading import Thread
import os
import signal
import setproctitle
import sys
import logging
import io
import numpy as np

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

    def __init__(self):
        # Initialize video capture
        self.video = cv2.VideoCapture(0)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, self.FRAME_WIDTH)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, self.FRAME_HEIGHT)

        # Adjust FPS based on actual camera performance during recording
        self.fps = self.measure_average_fps_during_recording()

        # Initialize motion detection variables
        self.previous_frame = None
        self.last_motion_time = None

        # Recording variables
        self.recording = False
        self.buffer = io.BytesIO()  # Buffer to store video in memory initially
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

    def measure_average_fps_during_recording(self, duration=10):
        """Measure the average FPS of the camera while performing motion detection and writing to a temporary buffer."""
        logger.info("Measuring average FPS for initial adjustment during recording...")
        frame_count = 0
        start_time = time.time()

        # Set up a temporary buffer to mimic recording conditions
        self.buffer = io.BytesIO()
        fourcc = cv2.VideoWriter_fourcc(*self.VIDEO_CODEC)
        temp_writer = cv2.VideoWriter('temp.avi', fourcc, 10.0, (self.FRAME_WIDTH, self.FRAME_HEIGHT))

        self.previous_frame = None  # Reset previous_frame for accurate measurement

        while time.time() - start_time < duration:
            success, frame = self.video.read()
            if not success:
                break

            # Process the frame
            gray = self.process_frame(frame)

            # Initialize previous_frame if it's the first frame
            if self.previous_frame is None:
                self.previous_frame = gray
                continue

            # Compute absolute difference between current frame and previous frame
            frame_delta = cv2.absdiff(self.previous_frame, gray)

            # Use starting parameters for motion detection
            thresh_sensitivity = self.START_THRESHOLD_SENSITIVITY
            min_area = self.START_MIN_AREA

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

            # Write the frame to the temporary buffer
            temp_writer.write(frame)
            frame_count += 1

            # Debug: Log FPS for each iteration
            iteration_elapsed_time = time.time() - start_time
            if iteration_elapsed_time > 0:
                iteration_fps = frame_count / iteration_elapsed_time
                logger.info(f"Iteration FPS: {iteration_fps}")

        elapsed_time = time.time() - start_time
        temp_writer.release()

        average_fps = frame_count / elapsed_time if elapsed_time > 0 else 1.0
        logger.info(f"Measured average FPS during recording: {average_fps}")
        return average_fps

    def process_frame(self, frame):
        """Process a frame by converting to grayscale and applying Gaussian blur."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        return gray

    def update_frame(self):
        """Continuously capture frames, detect motion, and handle recording."""
        while True:
            start_time = time.time()

            success, frame = self.video.read()
            if not success:
                break

            # Process the frame
            gray = self.process_frame(frame)

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
                    self.start_recording()
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

    def start_recording(self):
        """Start video recording."""
        self.buffer = io.BytesIO()  # Start with a fresh buffer
        self.recording = True
        logger.info("Started recording in memory buffer.")

    def stop_recording(self):
        """Stop video recording and write buffer to a file."""
        if self.recording:
            self.recording = False
            self.buffer.seek(0)

            # Save the buffer to a file
            timestamp = int(time.time())
            self.recording_file = f'temp_{timestamp}.avi'
            with open(self.recording_file, 'wb') as f:
                f.write(self.buffer.getvalue())

            new_filename = self.recording_file.replace('temp_', '')
            os.rename(self.recording_file, new_filename)
            logger.info(f"Recording saved as {new_filename}")

            # Log recording statistics
            logger.info(f"Recording completed: {new_filename}. Frame rate: {self.fps} FPS")

    def record_frame(self, frame):
        """Write frame to the video buffer."""
        if self.recording:
            # Encode the frame as a video frame and write to the buffer
            success, encoded_image = cv2.imencode('.avi', frame)
            if success:
                self.buffer.write(encoded_image.tobytes())


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
