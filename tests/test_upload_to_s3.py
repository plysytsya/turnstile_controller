import importlib.util
import logging
import os
import sys
import types
from pathlib import Path


class FakeJournalHandler(logging.Handler):
    def emit(self, record):
        return None


fake_journal_module = types.ModuleType("systemd.journal")
fake_journal_module.JournalHandler = FakeJournalHandler
sys.modules.setdefault("systemd", types.ModuleType("systemd"))
sys.modules["systemd.journal"] = fake_journal_module

fake_sentry_module = types.ModuleType("sentry_sdk")
fake_sentry_module.init = lambda *args, **kwargs: None
sys.modules["sentry_sdk"] = fake_sentry_module

fake_cv2_module = types.ModuleType("cv2")
sys.modules["cv2"] = fake_cv2_module

fake_boto3_module = types.ModuleType("boto3")
fake_boto3_module.client = lambda *args, **kwargs: None
sys.modules["boto3"] = fake_boto3_module


MODULE_PATH = Path(__file__).resolve().parents[1] / "camera" / "upload_to_s3.py"
SPEC = importlib.util.spec_from_file_location("upload_to_s3_module", MODULE_PATH)
upload_to_s3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload_to_s3)


class DummySettings:
    GYM_UUID = "gym-uuid"
    S3_ACCESS_KEY = "key"
    S3_SECRET_ACCESS_KEY = "secret"
    S3_ENDPOINT_URL = "https://gateway.storjshare.io"
    FLIP_VIDEO = False
    VIDEO_CODEC = ""


class RecordingS3Client:
    def __init__(self):
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


def test_s3_config_uses_storj_safe_checksum_mode():
    uploader = upload_to_s3.VideoUploader(DummySettings())
    config = uploader._build_s3_config()

    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"
    assert config.s3["addressing_style"] == "path"


def test_upload_file_to_s3_sends_fixed_content_length(tmp_path):
    uploader = upload_to_s3.VideoUploader(DummySettings())
    s3_client = RecordingS3Client()
    video_path = tmp_path / "clip.mp4"
    video_bytes = b"fake video bytes"
    video_path.write_bytes(video_bytes)

    upload_to_s3.asyncio.run(uploader.upload_file_to_s3(s3_client, os.fspath(video_path)))

    assert len(s3_client.calls) == 1
    call = s3_client.calls[0]
    assert call["Bucket"] == DummySettings.GYM_UUID
    assert call["Key"] == "clip.mp4"
    assert call["Body"] == video_bytes
    assert call["ContentType"] == "video/mp4"
    assert call["ContentLength"] == len(video_bytes)
    assert not video_path.exists()
