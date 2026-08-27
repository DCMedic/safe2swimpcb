import json
from datetime import datetime, timezone

import scripts.write_workflow_health as health


def test_write_workflow_health(tmp_path, monkeypatch):
    path = tmp_path / "health.json"
    now = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    payload = health.write_health(path, "Example Workflow", now=now)

    assert payload["status"] == "success"
    assert payload["last_success_at"] == now.isoformat()
    assert payload["run_id"] == "123"
    assert json.loads(path.read_text(encoding="utf-8"))["workflow"] == "Example Workflow"
