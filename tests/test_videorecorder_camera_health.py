import importlib.util
import logging
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

fake_cv2 = types.ModuleType("cv2")
fake_cv2.CAP_PROP_FRAME_WIDTH = 3
fake_cv2.CAP_PROP_FRAME_HEIGHT = 4
fake_cv2.VideoWriter_fourcc = lambda *args: 0
sys.modules["cv2"] = fake_cv2


MODULE_PATH = Path(__file__).resolve().parents[1] / "camera" / "videorecorder.py"
SPEC = importlib.util.spec_from_file_location("videorecorder_module", MODULE_PATH)
videorecorder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(videorecorder)


class FakeVideo:
    def __init__(self, read_result=True):
        self.read_result = read_result
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        return self.read_result, object()

    def release(self):
        self.released = True


class FakeWriter:
    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


def make_camera():
    camera = videorecorder.VideoCamera.__new__(videorecorder.VideoCamera)
    camera.recording = False
    camera.CAMERA_HEALTH_CHECK_INTERVAL = 0
    camera.last_camera_health_check = 0
    camera.video = None
    camera.out = None
    return camera


def test_camera_health_reinitializes_when_capture_is_not_ready(monkeypatch):
    camera = make_camera()
    init_calls = []

    monkeypatch.setattr(camera, "init_camera", lambda: init_calls.append(True))

    camera.check_camera_health()

    assert init_calls == [True]


def test_camera_health_marks_disconnected_and_releases_on_read_failure(monkeypatch):
    camera = make_camera()
    camera.video = FakeVideo(read_result=False)
    camera.out = FakeWriter()
    state_calls = []

    monkeypatch.setattr(
        videorecorder,
        "record_component_state",
        lambda component, connected: state_calls.append((component, connected)),
    )

    camera.check_camera_health()

    assert state_calls == [("camera", False)]
    assert camera.video is None
    assert camera.out is None


def test_camera_health_marks_connected_on_successful_read(monkeypatch):
    camera = make_camera()
    camera.video = FakeVideo(read_result=True)
    camera.out = FakeWriter()
    state_calls = []

    monkeypatch.setattr(
        videorecorder,
        "record_component_state",
        lambda component, connected: state_calls.append((component, connected)),
    )

    camera.check_camera_health()

    assert state_calls == [("camera", True)]
