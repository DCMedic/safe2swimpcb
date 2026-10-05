from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.verify_persisted_heartbeat import (
    lane_config,
    read_heartbeat_text,
    verify_advanced,
)


def test_read_heartbeat_accepts_offset_timestamp():
    value = read_heartbeat_text('{"last_verified_at":"2026-10-05T17:37:04-05:00"}', "last_verified_at")
    assert value.utcoffset().total_seconds() == -5 * 3600


def test_read_heartbeat_rejects_missing_field():
    with pytest.raises(ValueError, match="missing or empty"):
        read_heartbeat_text("{}", "last_verified_at")


def test_read_heartbeat_rejects_malformed_timestamp():
    with pytest.raises(ValueError):
        read_heartbeat_text('{"last_verified_at":"not-a-time"}', "last_verified_at")


def test_verify_requires_strict_advancement():
    before = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)
    with pytest.raises(RuntimeError, match="did not advance"):
        verify_advanced(before, before, "pcb")


def test_verify_accepts_newer_heartbeat():
    before = datetime(2026, 10, 5, 20, 0, tzinfo=timezone.utc)
    after = datetime(2026, 10, 5, 20, 1, tzinfo=timezone.utc)
    verify_advanced(before, after, "pcb")


def test_lane_config_is_policy_driven(tmp_path: Path):
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"lanes":{"demo":{"heartbeat_path":"data/demo.json","heartbeat_field":"stamp"}}}))
    cfg = lane_config("demo", policy)
    assert cfg["heartbeat_path"] == "data/demo.json"


def test_unknown_lane_fails(tmp_path: Path):
    policy = tmp_path / "policy.json"
    policy.write_text('{"lanes":{}}')
    with pytest.raises(ValueError, match="unknown recovery lane"):
        lane_config("missing", policy)
