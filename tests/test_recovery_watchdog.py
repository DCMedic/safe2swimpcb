from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.recovery_watchdog import heartbeat_age_minutes, in_active_window


def test_active_window_same_day():
    now = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    window = {"timezone": "America/Chicago", "start_hour": 6, "end_hour": 23}
    assert in_active_window(now, window) is True


def test_active_window_excludes_overnight():
    now = datetime(2026, 8, 27, 5, 0, tzinfo=timezone.utc)
    window = {"timezone": "America/Chicago", "start_hour": 6, "end_hour": 23}
    assert in_active_window(now, window) is False


def test_heartbeat_age_minutes(tmp_path: Path):
    path = tmp_path / "heartbeat.json"
    path.write_text(json.dumps({"last_verified_at": "2026-08-26T17:00:00+00:00"}), encoding="utf-8")
    now = datetime(2026, 8, 26, 18, 30, tzinfo=timezone.utc)
    assert heartbeat_age_minutes(path, "last_verified_at", now) == 90


def test_missing_heartbeat_field_is_unreadable(tmp_path: Path):
    path = tmp_path / "heartbeat.json"
    path.write_text("{}", encoding="utf-8")
    now = datetime(2026, 8, 26, 18, 30, tzinfo=timezone.utc)
    assert heartbeat_age_minutes(path, "last_verified_at", now) is None
