from usb_diagnostics import (
    get_pending_events,
    get_usb_status_snapshot,
    mark_events_sent,
    prune_events,
    record_component_state,
)


def test_record_component_state_creates_snapshot_and_transition(monkeypatch, tmp_path):
    monkeypatch.setenv("USB_DIAGNOSTICS_DB_PATH", str(tmp_path / "usb.sqlite3"))

    changed = record_component_state("qr_a", True)

    assert changed is True
    assert get_usb_status_snapshot() == {
        "components": {
            "qr_a": {
                "connected": True,
                "updated_at": get_usb_status_snapshot()["components"]["qr_a"]["updated_at"],
            }
        }
    }

    events = get_pending_events()
    assert len(events) == 1
    assert events[0]["component"] == "qr_a"
    assert events[0]["connected"] is True


def test_record_component_state_does_not_duplicate_same_status(monkeypatch, tmp_path):
    monkeypatch.setenv("USB_DIAGNOSTICS_DB_PATH", str(tmp_path / "usb.sqlite3"))

    assert record_component_state("qr_a", True) is True
    assert record_component_state("qr_a", True) is False

    events = get_pending_events()
    assert len(events) == 1
    assert events[0]["connected"] is True


def test_mark_events_sent_and_prune(monkeypatch, tmp_path):
    monkeypatch.setenv("USB_DIAGNOSTICS_DB_PATH", str(tmp_path / "usb.sqlite3"))

    record_component_state("qr_a", True)
    event_uuid = get_pending_events()[0]["event_uuid"]

    assert mark_events_sent([event_uuid]) == 1
    assert get_pending_events() == []
    assert prune_events(retain_sent_days=0) == 1
