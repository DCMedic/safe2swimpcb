from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.recovery_watchdog import (
    heartbeat_age_minutes,
    in_active_window,
    recovery_suppression_reason,
)


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


def test_active_normal_run_suppresses_duplicate_recovery():
    now = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
    runs = [{"id": 42, "event": "schedule", "status": "in_progress", "created_at": "2026-08-27T02:59:00Z"}]
    reason = recovery_suppression_reason(runs, 120, 90, now)
    assert "already in_progress" in reason


def test_recent_dispatch_honors_cooldown():
    now = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
    runs = [{"id": 43, "event": "workflow_dispatch", "status": "completed", "conclusion": "success", "created_at": "2026-08-27T02:30:00Z"}]
    reason = recovery_suppression_reason(runs, 120, 90, now)
    assert "within 120m cooldown" in reason


def test_old_completed_schedule_does_not_block_recovery():
    now = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
    runs = [{"id": 44, "event": "schedule", "status": "completed", "created_at": "2026-08-27T00:00:00Z"}]
    assert recovery_suppression_reason(runs, 120, 90, now) is None


def test_failed_dispatch_retries_after_failure_delay():
    now = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
    runs = [{"id": 45, "event": "workflow_dispatch", "status": "completed", "conclusion": "failure", "created_at": "2026-08-27T01:00:00Z"}]
    assert recovery_suppression_reason(runs, 120, 90, now) is None


def test_recent_failed_dispatch_uses_short_retry_delay():
    now = datetime(2026, 8, 27, 3, 0, tzinfo=timezone.utc)
    runs = [{"id": 46, "event": "workflow_dispatch", "status": "completed", "conclusion": "failure", "created_at": "2026-08-27T02:30:00Z"}]
    reason = recovery_suppression_reason(runs, 120, 90, now)
    assert "failure retry delay" in reason
