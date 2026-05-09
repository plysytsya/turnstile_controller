import asyncio
import json
import logging
import os
import sys
import time
import types
import uuid

from camera_trigger import queue_camera_trigger


fake_mqtt_module = types.ModuleType("paho.mqtt.client")
fake_mqtt_module.Client = lambda *args, **kwargs: None
sys.modules.setdefault("paho", types.ModuleType("paho"))
sys.modules.setdefault("paho.mqtt", types.ModuleType("paho.mqtt"))
sys.modules["paho.mqtt.client"] = fake_mqtt_module

fake_dotenv_module = types.ModuleType("dotenv")
fake_dotenv_module.load_dotenv = lambda *args, **kwargs: None
sys.modules["dotenv"] = fake_dotenv_module

fake_sentry_module = types.ModuleType("sentry_sdk")
fake_sentry_module.init = lambda *args, **kwargs: None
fake_sentry_module.capture_exception = lambda *args, **kwargs: None
fake_sentry_module.flush = lambda *args, **kwargs: None
sys.modules["sentry_sdk"] = fake_sentry_module

class FakeJournalHandler(logging.Handler):
    def emit(self, record):
        return None

fake_journal_module = types.ModuleType("systemd.journal")
fake_journal_module.JournalHandler = FakeJournalHandler
sys.modules.setdefault("systemd", types.ModuleType("systemd"))
sys.modules["systemd.journal"] = fake_journal_module

fake_tenacity_module = types.ModuleType("tenacity")
fake_tenacity_module.retry = lambda *args, **kwargs: (lambda func: func)
fake_tenacity_module.stop_after_delay = lambda *args, **kwargs: None
fake_tenacity_module.wait_fixed = lambda *args, **kwargs: None
fake_tenacity_module.RetryError = RuntimeError
sys.modules["tenacity"] = fake_tenacity_module

os.environ.setdefault("RECORDING_DIR", "/tmp")

import mqtt_receiver
import mqtt_sender


def test_qr_trigger_is_forwarded_to_local_camera_via_mqtt(monkeypatch, tmp_path):
    entrance_log_uuid = str(uuid.uuid4())
    queue_camera_trigger(tmp_path, entrance_log_uuid)

    published_messages = []
    mqtt_receiver.RECORDING_DIR = str(tmp_path)

    async def fake_send_with_reconnect(topic, payload):
        published_messages.append((topic, payload))
        mqtt_receiver.process_message_payload(payload)

    monkeypatch.setattr(mqtt_sender, "send_with_reconnect", fake_send_with_reconnect)

    asyncio.run(mqtt_sender.scan_and_send_once(str(tmp_path), mqtt_topic="home/raspberry"))

    assert published_messages, "Expected mqtt_sender to publish a camera trigger."
    published_topic, published_payload = published_messages[0]
    decoded_payload = json.loads(published_payload)

    assert published_topic == "home/raspberry"
    assert decoded_payload[0] == entrance_log_uuid
    assert isinstance(decoded_payload[1], int)
    assert (tmp_path / "record.txt").exists()
    assert (tmp_path / f"{entrance_log_uuid}.txt").exists()


def test_sender_ignores_receiver_metadata_files(monkeypatch, tmp_path):
    entrance_log_uuid = str(uuid.uuid4())
    metadata_file = tmp_path / f"{entrance_log_uuid}.txt"
    metadata_file.write_text(json.dumps({"timestamp": 1773882604}))

    sent = []

    async def fake_send_with_reconnect(topic, payload):
        sent.append((topic, payload))

    monkeypatch.setattr(mqtt_sender, "send_with_reconnect", fake_send_with_reconnect)

    asyncio.run(mqtt_sender.scan_and_send_once(str(tmp_path), mqtt_topic="home/raspberry"))

    assert sent == []
    assert metadata_file.exists()


def test_sender_keeps_old_trigger_files_until_published(monkeypatch, tmp_path):
    entrance_log_uuid = str(uuid.uuid4())
    trigger_file = tmp_path / f"{entrance_log_uuid}.txt"
    trigger_file.write_text("")
    old_time = int(time.time()) - 60
    os.utime(trigger_file, (old_time, old_time))

    sent = []

    async def fake_send_with_reconnect(topic, payload):
        sent.append((topic, payload))
        return True

    monkeypatch.setattr(mqtt_sender, "send_with_reconnect", fake_send_with_reconnect)

    asyncio.run(mqtt_sender.scan_and_send_once(str(tmp_path), mqtt_topic="home/raspberry"))

    assert sent, "Expected old trigger files to be published instead of deleted."
    assert not trigger_file.exists()


def test_sender_restores_trigger_file_when_publish_fails(monkeypatch, tmp_path):
    entrance_log_uuid = str(uuid.uuid4())
    trigger_file = tmp_path / f"{entrance_log_uuid}.txt"
    trigger_file.write_text("")

    async def fake_send_with_reconnect(topic, payload):
        return False

    monkeypatch.setattr(mqtt_sender, "send_with_reconnect", fake_send_with_reconnect)

    asyncio.run(mqtt_sender.scan_and_send_once(str(tmp_path), mqtt_topic="home/raspberry"))

    assert trigger_file.exists()
    assert not (tmp_path / f"{entrance_log_uuid}.txt.sending").exists()


def test_sender_recovers_incomplete_sending_file_after_restart(monkeypatch, tmp_path):
    entrance_log_uuid = str(uuid.uuid4())
    sending_file = tmp_path / f"{entrance_log_uuid}.txt.sending"
    sending_file.write_text("")

    sent = []

    async def fake_send_with_reconnect(topic, payload):
        sent.append((topic, payload))
        return True

    monkeypatch.setattr(mqtt_sender, "send_with_reconnect", fake_send_with_reconnect)

    asyncio.run(mqtt_sender.scan_and_send_once(str(tmp_path), mqtt_topic="home/raspberry"))

    assert sent
    assert not sending_file.exists()


def test_filesystem_camera_trigger_touches_record_file(tmp_path):
    entrance_log_uuid = str(uuid.uuid4())

    queue_camera_trigger(tmp_path, entrance_log_uuid, mode="filesystem")

    assert (tmp_path / f"{entrance_log_uuid}.txt").exists()
    assert (tmp_path / "record.txt").exists()
