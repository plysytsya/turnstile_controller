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


MODULE_PATH = Path(__file__).resolve().parents[1] / "device_configurator_service.py"
SPEC = importlib.util.spec_from_file_location("device_configurator_service_module", MODULE_PATH)
device_configurator_service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(device_configurator_service)


def test_reconcile_camera_services_enables_expected_services(monkeypatch):
    calls = []

    monkeypatch.setattr(device_configurator_service, "camera_services_enabled", lambda: True)
    monkeypatch.setattr(device_configurator_service, "has_upload_configuration", lambda: True)

    def fake_set_service_enabled(service_name, enabled):
        calls.append((service_name, enabled))
        return {
            "service": service_name,
            "managed": "enable" if enabled else "disable",
            "ok": True,
            "active": enabled,
        }

    monkeypatch.setattr(device_configurator_service, "set_service_enabled", fake_set_service_enabled)

    result = device_configurator_service.reconcile_camera_services()

    assert result["status"] == "succeeded"
    assert result["error_message"] == ""
    assert calls == [
        ("videorecorder", True),
        ("mqtt-receiver", True),
        ("upload", True),
    ]


def test_reconcile_camera_services_disables_all_when_camera_toggle_is_off(monkeypatch):
    calls = []

    monkeypatch.setattr(device_configurator_service, "camera_services_enabled", lambda: False)

    def fake_set_service_enabled(service_name, enabled):
        calls.append((service_name, enabled))
        return {
            "service": service_name,
            "managed": "enable" if enabled else "disable",
            "ok": True,
            "active": enabled,
        }

    monkeypatch.setattr(device_configurator_service, "set_service_enabled", fake_set_service_enabled)

    result = device_configurator_service.reconcile_camera_services()

    assert result["status"] == "succeeded"
    assert result["error_message"] == ""
    assert calls == [
        ("videorecorder", False),
        ("mqtt-receiver", False),
        ("upload", False),
    ]


def test_reconcile_camera_services_respects_runtime_override(monkeypatch):
    calls = []

    monkeypatch.setattr(device_configurator_service, "camera_services_enabled", lambda: False)
    monkeypatch.setattr(device_configurator_service, "has_upload_configuration", lambda: True)

    def fake_set_service_enabled(service_name, enabled):
        calls.append((service_name, enabled))
        return {
            "service": service_name,
            "managed": "enable" if enabled else "disable",
            "ok": True,
            "active": enabled,
        }

    monkeypatch.setattr(device_configurator_service, "set_service_enabled", fake_set_service_enabled)

    result = device_configurator_service.reconcile_camera_services(enabled_override=True)

    assert result["status"] == "succeeded"
    assert calls == [
        ("videorecorder", True),
        ("mqtt-receiver", True),
        ("upload", True),
    ]


def test_persist_env_values_does_not_store_camera_enabled(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text('HOSTNAME="https://example.com"\nCAMERA_ENABLED="False"\n')

    monkeypatch.setattr(device_configurator_service, "ENV_PATH", env_path)
    monkeypatch.setenv("CAMERA_ENABLED", "False")

    device_configurator_service.persist_env_values({"CAMERA_ENABLED": True, "HOSTNAME": "https://new.example.com"})

    rendered = env_path.read_text()
    assert 'HOSTNAME="https://new.example.com"' in rendered
    assert 'CAMERA_ENABLED="False"' in rendered
    assert os.environ["CAMERA_ENABLED"] == "False"


def test_current_device_settings_reports_camera_enabled_from_service_state(monkeypatch):
    monkeypatch.setenv("HOSTNAME", "https://example.com")
    monkeypatch.setattr(
        device_configurator_service,
        "current_camera_services",
        lambda: [
            {"service": "videorecorder", "active": "active", "enabled": "enabled"},
            {"service": "mqtt-receiver", "active": "active", "enabled": "enabled"},
            {"service": "upload", "active": "inactive", "enabled": "disabled"},
        ],
    )

    settings = device_configurator_service.current_device_settings()

    assert settings["CAMERA_ENABLED"] is True


def test_ensure_service_unit_installed_skips_copy_when_unit_matches(tmp_path, monkeypatch):
    source_path = tmp_path / "videorecorder.service"
    target_dir = tmp_path / "etc/systemd/system"
    target_dir.mkdir(parents=True)
    target_path = target_dir / "videorecorder.service"
    rendered = "[Unit]\nDescription=Video Recorder\n"
    source_path.write_text(rendered)
    target_path.write_text(rendered)

    monkeypatch.setattr(device_configurator_service, "CURRENT_DIR", tmp_path)
    monkeypatch.setattr(device_configurator_service, "SYSTEMD_UNIT_DIR", target_dir)

    result = device_configurator_service.ensure_service_unit_installed("videorecorder")

    assert result is None


def test_get_device_identifier_prefers_hardware_mac(monkeypatch):
    monkeypatch.setattr(device_configurator_service, "get_hardware_mac_address", lambda: "e0:e1:a9:3d:41:43")
    monkeypatch.setenv("DEVICE_IDENTIFIER", "from-env")
    monkeypatch.setattr(device_configurator_service.socket, "gethostname", lambda: "odroid")

    assert device_configurator_service.get_device_identifier() == "e0:e1:a9:3d:41:43"


def test_get_device_identifier_falls_back_to_env_then_hostname(monkeypatch):
    monkeypatch.setattr(device_configurator_service, "get_hardware_mac_address", lambda: "")
    monkeypatch.setenv("DEVICE_IDENTIFIER", "from-env")
    monkeypatch.setattr(device_configurator_service.socket, "gethostname", lambda: "odroid")

    assert device_configurator_service.get_device_identifier() == "from-env"

    monkeypatch.setenv("DEVICE_IDENTIFIER", " ")
    assert device_configurator_service.get_device_identifier() == "odroid"
