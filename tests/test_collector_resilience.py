from datetime import datetime, timedelta, timezone
import json

import pytest

from scripts.collector_resilience import (
    fresh_cached_payload,
    mark_cached_official,
    retry_call,
)
from scripts.protect_current_flag import protect


def write_payload(path, *, verified_at, stale_after_hours=3, flag="Yellow", **extra):
    payload = {
        "flag": flag,
        "label": flag if flag else "Official flag status unavailable",
        "last_verified_at": verified_at.isoformat(),
        "stale_after_hours": stale_after_hours,
        "provenance_tier": "primary_official" if flag else "unavailable",
    }
    payload.update(extra)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fresh_cached_payload_uses_original_verification_age(tmp_path):
    now = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    path = tmp_path / "current_flag.json"
    write_payload(path, verified_at=now - timedelta(hours=1), stale_after_hours=3)

    payload, age = fresh_cached_payload(path, now)

    assert payload is not None
    assert payload["flag"] == "Yellow"
    assert age == pytest.approx(1.0)


def test_stale_cached_payload_is_rejected(tmp_path):
    now = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    path = tmp_path / "current_flag.json"
    write_payload(path, verified_at=now - timedelta(hours=4), stale_after_hours=3)

    payload, age = fresh_cached_payload(path, now)

    assert payload is None
    assert age == pytest.approx(4.0)


def test_mark_cached_does_not_refresh_last_verified_at():
    verified = "2026-08-20T16:00:00+00:00"
    now = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    previous = {
        "flag": "Yellow",
        "last_verified_at": verified,
        "stale_after_hours": 3,
        "provenance_tier": "primary_official",
    }

    cached = mark_cached_official(previous, now, "timeout")

    assert cached["last_verified_at"] == verified
    assert cached["last_checked_at"] == now.isoformat()
    assert cached["provenance_tier"] == "cached_official_observation"
    assert cached["cached_from_provenance_tier"] == "primary_official"
    assert cached["source_check_status"] == "degraded"


def test_retry_call_retries_fetch_and_parse_failures():
    calls = {"count": 0}

    def operation():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary parser mismatch")
        return "Yellow"

    value = retry_call(
        operation,
        attempts=3,
        base_delay_seconds=0,
        retry_exceptions=(RuntimeError,),
    )

    assert value == "Yellow"
    assert calls["count"] == 3


def test_regression_guard_restores_fresh_flag_when_new_output_is_unavailable(tmp_path):
    now = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    write_payload(previous, verified_at=now - timedelta(hours=1), stale_after_hours=3, flag="Yellow")
    write_payload(
        current,
        verified_at=now,
        stale_after_hours=0,
        flag=None,
        source_reachable=False,
        status="official_conditions_source_unavailable",
    )

    changed = protect(previous, current, max_age_hours=3, mode="unavailable", now=now)
    payload = json.loads(current.read_text(encoding="utf-8"))

    assert changed is True
    assert payload["flag"] == "Yellow"
    assert payload["last_verified_at"] == (now - timedelta(hours=1)).isoformat()
    assert payload["provenance_tier"] == "cached_official_observation"
    assert payload["source_reachable"] is False


def test_regression_guard_does_not_restore_expired_flag(tmp_path):
    now = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    write_payload(previous, verified_at=now - timedelta(hours=4), stale_after_hours=3, flag="Yellow")
    write_payload(
        current,
        verified_at=now,
        stale_after_hours=0,
        flag=None,
        source_reachable=False,
        status="official_conditions_source_unavailable",
    )

    changed = protect(previous, current, max_age_hours=3, mode="unavailable", now=now)
    payload = json.loads(current.read_text(encoding="utf-8"))

    assert changed is False
    assert payload["flag"] is None


def test_missing_flag_mode_protects_expected_flag_sources(tmp_path):
    now = datetime(2026, 8, 20, 18, 0, tzinfo=timezone.utc)
    previous = tmp_path / "previous.json"
    current = tmp_path / "current.json"
    write_payload(previous, verified_at=now - timedelta(hours=2), stale_after_hours=18, flag="Green")
    write_payload(
        current,
        verified_at=now,
        stale_after_hours=18,
        flag=None,
        source_reachable=True,
        status="official_conditions_source_reachable",
    )

    changed = protect(previous, current, max_age_hours=18, mode="missing-flag", now=now)
    payload = json.loads(current.read_text(encoding="utf-8"))

    assert changed is True
    assert payload["flag"] == "Green"
