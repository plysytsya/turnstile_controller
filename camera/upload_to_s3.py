import aiohttp
import logging
import os
import asyncio
import aioboto3
from botocore.exceptions import ClientError
from systemd.journal import JournalHandler
from tenacity import retry, stop_after_attempt, wait_exponential


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VideoUpload")
journal_handler = JournalHandler()
logger.addHandler(journal_handler)


async def ensure_bucket_exists(s3_client, bucket_name):
    """Ensure the S3 bucket exists. Create it if not."""
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


async def upload_file_to_s3(s3_client, file_path, settings):
    """Upload a file to S3 with the gym_uuid prepended to the filename."""
    file_name = os.path.basename(file_path)
    bucket_name = settings.GYM_UUID
    s3_key = file_name

    try:
        logger.info(f"Uploading {file_name} as {s3_key} to bucket {bucket_name}...")
        await s3_client.upload_file(file_path, bucket_name, s3_key)
        logger.info(f"Successfully uploaded {file_name} to {bucket_name}/{s3_key}.")

        # Delete the file after successful upload
        os.remove(file_path)
        logger.info(f"Deleted local file: {file_path}")

        entrance_log_uuid = os.path.splitext(file_name)[0]
        await set_has_video_to_true_in_db(entrance_log_uuid, settings)
    except ClientError as e:
        logger.error(f"Failed to upload {file_name}: {e}")
    except OSError as e:
        logger.error(f"Failed to delete file {file_path}: {e}")


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2), reraise=True)
async def set_has_video_to_true_in_db(entrance_log_uuid, settings):
    url = f"{settings.HOSTNAME}/verify_customer/"
    payload = {"has_video": True, "uuid": str(entrance_log_uuid)}
    headers = {
        "Authorization": f"Bearer {settings.JWT_TOKEN}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, headers=headers, json=payload) as response:
            response_text = await response.text()
            if response.status == 200:
                logger.info(f"Successfully updated has_video for UUID {entrance_log_uuid}. Response: {response_text}")
            else:
                logger.error(
                    f"Failed to update has_video for UUID {entrance_log_uuid}. "
                    f"Status: {response.status}, Response: {response_text}"
                )
                response.raise_for_status()  # Raise an exception to trigger retry


async def upload_loop(settings):
    """Main loop to check the directory and upload files."""
    try:
        bucket_name = settings.GYM_UUID
        session = aioboto3.Session()
        async with session.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL,
        ) as s3_client:
            # Ensure the bucket exists on startup
            await ensure_bucket_exists(s3_client, bucket_name)

            # Start the upload loop
            while True:
                # List all files in the recording directory
                files = [
                    os.path.join(settings.RECORDING_DIR, f)
                    for f in os.listdir(settings.RECORDING_DIR)
                    if os.path.isfile(os.path.join(settings.RECORDING_DIR, f))
                ]
                video_files = [f for f in files if f.endswith(".mp4") and not "temp" in f]

                if video_files:
                    logger.info(f"Found {len(video_files)} video files to upload...")
                    tasks = [upload_file_to_s3(s3_client, file, settings) for file in video_files]
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
