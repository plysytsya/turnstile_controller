import asyncio
import logging
import os
import sys
import aioboto3
from botocore.exceptions import ClientError
from systemd.journal import JournalHandler
from botocore.config import Config

# Add the global Python library path to sys.path to use cv2 just like in the videorecorder
sys.path.append("/usr/lib/python3/dist-packages")
import cv2


logger = logging.getLogger("VideoUploader")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)
logger.propagate = False


class VideoUploader:
    def __init__(self, settings):
        self.settings = settings

    async def ensure_bucket_exists(self, s3_client):
        """Ensure the S3 bucket exists. Create it if not."""
        bucket_name = self.settings.GYM_UUID
        try:
            await s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.info(f"Bucket {bucket_name} does not exist. Creating it...")
                try:
                    await s3_client.create_bucket(Bucket=bucket_name)
                    logger.info(f"Bucket {bucket_name} created successfully.")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket {bucket_name}: {create_error}")
                    raise
            else:
                logger.error(f"Error checking bucket {bucket_name}: {e}")
                raise

    async def flip_video(self, input_file_path, output_file_path):
        """Flip the video upside down and mirror it left to right."""
        cap = cv2.VideoCapture(input_file_path)
        if not cap.isOpened():
            logger.error(f"Could not open video file: {input_file_path}")
            return False

        # Read video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"avc1")

        out = cv2.VideoWriter(output_file_path, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # First flip upside down (vertical flip)
            flipped_frame = cv2.flip(frame, 0)
            # Then mirror left to right (horizontal flip)
            flipped_frame = cv2.flip(flipped_frame, 1)
            out.write(flipped_frame)

        cap.release()
        out.release()
        return True

    async def upload_file_to_s3(self, s3_client, file_path):
        """Upload a file to S3, optionally flipping and mirroring it first if configured."""
        file_name = os.path.basename(file_path)
        bucket_name = self.settings.GYM_UUID
        s3_key = file_name

        # If flipping is required
        if getattr(self.settings, "FLIP_VIDEO", False) and "flipped" not in file_name:
            # Create a temporary flipped file
            flipped_file_path = file_path + ".flipped.mp4"
            logger.info(f"Flipping and mirroring video {file_name} before upload...")
            success = await self.flip_video(file_path, flipped_file_path)
            if success:
                # Replace the file_path with the flipped one for uploading
                file_path_to_upload = flipped_file_path
            else:
                logger.error("Flipping video failed, uploading original.")
                file_path_to_upload = file_path
        else:
            file_path_to_upload = file_path

        logger.info(f"Uploading {os.path.basename(file_path_to_upload)} as {s3_key} to bucket {bucket_name}...")

        # Upload the file to S3
        await s3_client.upload_file(file_path_to_upload, bucket_name, s3_key)
        logger.info(f"Successfully uploaded {file_name} to {bucket_name}/{s3_key}.")

        # Add 90-day expiration lifecycle
        await self.set_lifecycle_policy(s3_client, bucket_name, s3_key)

        # Delete local files
        os.remove(file_path)
        if file_path_to_upload != file_path:
            os.remove(file_path_to_upload)
        logger.info(f"Deleted local file(s) related to {file_name}")

    async def set_lifecycle_policy(self, s3_client, bucket_name, s3_key):
        """Set a 90-day expiration lifecycle policy for the uploaded file."""
        lifecycle_policy = {
            'Rules': [
                {
                    'ID': 'Delete after 90 days',
                    'Filter': {'Prefix': s3_key},
                    'Status': 'Enabled',
                    'Expiration': {'Days': 90},
                },
            ]
        }
        try:
            logger.info(f"Setting lifecycle policy for bucket {bucket_name}...")
            await s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_policy
            )
            logger.info("Lifecycle policy set successfully.")
        except ClientError as e:
            logger.error(f"Failed to set lifecycle policy: {e}")
            raise

    async def upload(self, video_files):
        """Main loop to check the directory and upload files."""
        config = Config(
            retries={"max_attempts": 1, "mode": "standard"},
            connect_timeout=30,  # Seconds
            read_timeout=300,  # Seconds
        )

        session = aioboto3.Session()
        async with session.client(
            "s3",
            aws_access_key_id=self.settings.S3_ACCESS_KEY,
            aws_secret_access_key=self.settings.S3_SECRET_ACCESS_KEY,
            endpoint_url=self.settings.S3_ENDPOINT_URL,
            config=config,
        ) as s3_client:
            # Ensure the bucket exists on startup
            await self.ensure_bucket_exists(s3_client)

            logger.info(f"Found {len(video_files)} video files to upload...")
            for file in video_files:
                logger.info(f"Uploading {file}...")
                await self.upload_file_to_s3(s3_client, file)
                break  # better to not keep uploading because there might be a newer one with higher prio
    async def upload_loop(self):
        """Run the upload loop continuously."""
        while True:
                # List all files in the recording directory and sort them by modification time (newest first)
            files = sorted(
                [
                    os.path.join(self.settings.RECORDING_DIR, f)
                    for f in os.listdir(self.settings.RECORDING_DIR)
                    if os.path.isfile(os.path.join(self.settings.RECORDING_DIR, f))
                ],
                key=lambda x: os.path.getmtime(x),
                reverse=True
            )
            video_files = [f for f in files if f.endswith(".mp4") and not "temp" in f]
            if video_files:
                await self.upload(video_files)
            await asyncio.sleep(5)


# Example Usage
if __name__ == "__main__":
    import dotenv

    # the path of the .env file which is in the directory that is one level up from the current directory
    path_to_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.env")

    dotenv.load_dotenv(path_to_env)

    class Settings:
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
        FLIP_VIDEO = os.getenv("FLIP_VIDEO", "False").lower() == "true"

    settings = Settings()
    uploader = VideoUploader(settings)

    try:
        asyncio.run(uploader.upload_loop())
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
