import logging
import os
import asyncio
import aioboto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
import setproctitle
from systemd.journal import JournalHandler

# Load environment variables
load_dotenv()

# Read environment variables
GYM_UUID = os.getenv("gym_uuid")
ACCESS_KEY = os.getenv("access_key")
SECRET_ACCESS_KEY = os.getenv("secret_access_key")
ENDPOINT_URL = os.getenv("endpoint")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoUpload")
journal_handler = JournalHandler()
logger.addHandler(journal_handler)

RECORDING_DIR = '/home/manager/turnstile_controller/camera'

if not all([GYM_UUID, ACCESS_KEY, SECRET_ACCESS_KEY, ENDPOINT_URL]):
    raise ValueError("Missing required environment variables in .env file.")

async def ensure_bucket_exists(s3_client, bucket_name):
    """Ensure the S3 bucket exists. Create it if not."""
    try:
        await s3_client.head_bucket(Bucket=bucket_name)
        logger.info(f"Bucket {bucket_name} exists.")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
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

async def upload_file_to_s3(s3_client, bucket_name, file_path):
    """Upload a file to S3 with the gym_uuid prepended to the filename."""
    file_name = os.path.basename(file_path)
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

async def upload_loop():
    """Main loop to check the directory and upload files."""
    try:
        bucket_name = GYM_UUID
        session = aioboto3.Session()
        async with session.client(
                "s3",
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_ACCESS_KEY,
                endpoint_url=ENDPOINT_URL,
        ) as s3_client:
            # Ensure the bucket exists on startup
            await ensure_bucket_exists(s3_client, bucket_name)

            # Start the upload loop
            while True:
                # List all files in the recording directory
                files = [
                    os.path.join(RECORDING_DIR, f)
                    for f in os.listdir(RECORDING_DIR)
                    if os.path.isfile(os.path.join(RECORDING_DIR, f))
                ]
                video_files = [f for f in files if f.endswith(".mp4") and not "temp" in f]

                if video_files:
                    logger.info(f"Found {len(video_files)} video files to upload...")
                    tasks = [upload_file_to_s3(s3_client, bucket_name, file) for file in video_files]
                    await asyncio.gather(*tasks)
                else:
                    pass

                # Sleep for n seconds
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Upload loop cancelled.")
        raise
    except Exception as e:
        logger.exception(f"Exception in upload_loop {e}")
    finally:
        logger.info("Upload loop exiting.")

if __name__ == "__main__":
    setproctitle.setproctitle("videouploader")
    try:
        asyncio.run(upload_loop())
    except KeyboardInterrupt:
        logger.info("Terminating upload loop.")
