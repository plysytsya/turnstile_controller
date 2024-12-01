import asyncio
import logging
import os
import aioboto3
from botocore.exceptions import ClientError
from systemd.journal import JournalHandler


logger = logging.getLogger("VideoUploader")
logger.setLevel(logging.INFO)
journal_handler = JournalHandler()
logger.addHandler(journal_handler)
logger.propagate = False
# Add stream handler
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
logger.addHandler(stream_handler)

class VideoUploader:
    def __init__(self, settings):
        self.settings = settings


    async def ensure_bucket_exists(self, s3_client):
        """Ensure the S3 bucket exists. Create it if not."""
        bucket_name = self.settings.GYM_UUID
        try:
            await s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} exists.")
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

    async def upload_file_to_s3(self, s3_client, file_path):
        """Upload a file to S3 with the gym_uuid prepended to the filename."""
        file_name = os.path.basename(file_path)
        bucket_name = self.settings.GYM_UUID
        s3_key = file_name

        try:
            logger.info(f"Uploading {file_name} as {s3_key} to bucket {bucket_name}...")
            await s3_client.upload_file(file_path, bucket_name, s3_key)
            logger.info(f"Successfully uploaded {file_name} to {bucket_name}/{s3_key}.")

            # Delete the file after successful upload
            os.remove(file_path)
            logger.info(f"Deleted local file: {file_path}")

        except ClientError as e:
            logger.error(f"Failed to upload {file_name}: {e}")
        except OSError as e:
            logger.error(f"Failed to delete file {file_path}: {e}")

    async def upload(self):
        """Main loop to check the directory and upload files."""
        try:
            session = aioboto3.Session()
            async with session.client(
                "s3",
                aws_access_key_id=self.settings.S3_ACCESS_KEY,
                aws_secret_access_key=self.settings.S3_SECRET_ACCESS_KEY,
                endpoint_url=self.settings.S3_ENDPOINT_URL,
            ) as s3_client:
                # Ensure the bucket exists on startup
                await self.ensure_bucket_exists(s3_client)

                # Start the upload loop
                # List all files in the recording directory
                files = [
                    os.path.join(self.settings.RECORDING_DIR, f)
                    for f in os.listdir(self.settings.RECORDING_DIR)
                    if os.path.isfile(os.path.join(self.settings.RECORDING_DIR, f))
                ]
                video_files = [f for f in files if f.endswith(".mp4") and not "temp" in f]

                if video_files:
                    logger.info(f"Found {len(video_files)} video files to upload...")
                    tasks = [self.upload_file_to_s3(s3_client, file) for file in video_files]
                    await asyncio.gather(*tasks)
                else:
                    logger.debug("No files found to upload.")
        except asyncio.CancelledError:
            logger.info("Upload cancelled.")
            raise
        except Exception as e:
            logger.exception(f"Exception in upload_loop {e}")
        finally:
            logger.info("Upload exiting.")


# Example Usage
if __name__ == "__main__":
    import dotenv

    # the path of the .env file which is in the deirectory that is one level up from the current directory
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

    settings = Settings()
    uploader = VideoUploader(settings)

    try:
        asyncio.run(uploader.upload())
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
