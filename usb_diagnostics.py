import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


SPAIN_TIMEZONE = ZoneInfo("Europe/Madrid")
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "usb_diagnostics.sqlite3"


def _database_path():
    configured_path = str(os.getenv("USB_DIAGNOSTICS_DB_PATH", "")).strip()
    if configured_path:
        return Path(configured_path)
    return DEFAULT_DB_PATH


def now_spain_iso():
    return datetime.now(SPAIN_TIMEZONE).isoformat()


def _connect():
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database():
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS usb_component_status (
                component TEXT PRIMARY KEY,
                connected INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usb_events (
                event_uuid TEXT PRIMARY KEY,
                component TEXT NOT NULL,
                connected INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                sent_at TEXT
            );

            CREATE INDEX IF NOT EXISTS usb_events_sent_at_idx
            ON usb_events (sent_at, occurred_at);

            CREATE INDEX IF NOT EXISTS usb_events_component_idx
            ON usb_events (component, occurred_at);
            """
        )


@contextmanager
def _transaction():
    initialize_database()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def record_component_state(component, connected):
    normalized_component = str(component or "").strip().lower()
    if not normalized_component:
        return False

    normalized_connected = bool(connected)
    occurred_at = now_spain_iso()

    with _transaction() as connection:
        current_row = connection.execute(
            "SELECT connected FROM usb_component_status WHERE component = ?",
            (normalized_component,),
        ).fetchone()

        if current_row is not None and bool(current_row["connected"]) == normalized_connected:
            connection.execute(
                "UPDATE usb_component_status SET updated_at = ? WHERE component = ?",
                (occurred_at, normalized_component),
            )
            return False

        connection.execute(
            """
            INSERT INTO usb_component_status (component, connected, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(component) DO UPDATE SET
                connected = excluded.connected,
                updated_at = excluded.updated_at
            """,
            (normalized_component, int(normalized_connected), occurred_at),
        )
        connection.execute(
            """
            INSERT INTO usb_events (event_uuid, component, connected, occurred_at, sent_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (str(uuid.uuid4()), normalized_component, int(normalized_connected), occurred_at),
        )
        return True


def get_usb_status_snapshot():
    initialize_database()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT component, connected, updated_at
            FROM usb_component_status
            ORDER BY component ASC
            """
        ).fetchall()

    return {
        "components": {
            row["component"]: {
                "connected": bool(row["connected"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        }
    }


def get_pending_events(limit=200):
    initialize_database()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT event_uuid, component, connected, occurred_at
            FROM usb_events
            WHERE sent_at IS NULL
            ORDER BY occurred_at ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()

    return [
        {
            "event_uuid": row["event_uuid"],
            "component": row["component"],
            "connected": bool(row["connected"]),
            "occurred_at": row["occurred_at"],
        }
        for row in rows
    ]


def mark_events_sent(event_uuids):
    uuids = [str(event_uuid).strip() for event_uuid in (event_uuids or []) if str(event_uuid).strip()]
    if not uuids:
        return 0

    sent_at = now_spain_iso()
    placeholders = ",".join("?" for _ in uuids)
    with _transaction() as connection:
        cursor = connection.execute(
            f"UPDATE usb_events SET sent_at = ? WHERE event_uuid IN ({placeholders})",
            [sent_at, *uuids],
        )
        return cursor.rowcount


def prune_events(retain_sent_days=14):
    cutoff = (datetime.now(SPAIN_TIMEZONE) - timedelta(days=int(retain_sent_days))).isoformat()
    with _transaction() as connection:
        cursor = connection.execute(
            """
            DELETE FROM usb_events
            WHERE sent_at IS NOT NULL
              AND occurred_at < ?
            """,
            (cutoff,),
        )
        return cursor.rowcount
