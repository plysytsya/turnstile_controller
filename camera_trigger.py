from pathlib import Path


def queue_camera_trigger(recording_dir, entrance_log_uuid, *, mode="mqtt"):
    recording_path = Path(recording_dir)
    recording_path.mkdir(parents=True, exist_ok=True)

    trigger_file_path = recording_path / f"{entrance_log_uuid}.txt"
    trigger_file_path.write_text("")
    if str(mode or "").strip().lower() == "filesystem":
        (recording_path / "record.txt").write_text("")
    return trigger_file_path
