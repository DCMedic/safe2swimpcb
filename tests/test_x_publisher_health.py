import json
from datetime import datetime
from zoneinfo import ZoneInfo

import scripts.mark_x_publisher_failure as failure_health
from scripts.run_x_publisher import classify, fit_post


def test_classifies_published_run():
    outcome, detail = classify(0, "PUBLISHED_URL=https://x.com/knowthegulf/status/123\n", "")
    assert outcome == "published"
    assert detail is None


def test_classifies_guardrail_no_post():
    outcome, detail = classify(0, "NO_POST: duplicate fingerprint\n", "")
    assert outcome == "no_post"
    assert detail == "duplicate fingerprint"


def test_classifies_dry_run():
    outcome, detail = classify(0, "SELECTED_KIND=education\nDRY_RUN_ONLY\n", "")
    assert outcome == "dry_run"
    assert detail is None


def test_classifies_api_failure_with_diagnostic_tail():
    outcome, detail = classify(1, "", "WARNING: media upload failed\nRuntimeError: X API returned HTTP 429")
    assert outcome == "failed"
    assert detail == "RuntimeError: X API returned HTTP 429"


def test_compacts_long_flag_change_and_preserves_safety_instruction():
    text = "⚠️ NORTHWEST FLORIDA FLAG CHANGES — " + ("Panama City Beach: Official flag status unavailable → Double Red; " * 6) + "Follow locally posted flags and lifeguard instructions."
    compact = fit_post(text, kind="flag-change")
    assert len(compact) <= 280
    assert compact.endswith("Follow locally posted flags and lifeguard instructions.")


def test_compacts_url_post_without_breaking_url():
    url = "https://knowthegulf.com/rip-current-safety/?utm_source=x&utm_medium=social&utm_campaign=test&utm_content=rotation_1"
    text = ("A very long acquisition hook about Gulf safety and preparation. " * 8).strip() + " → " + url
    compact = fit_post(text, kind="acquisition", contains_url=True)
    assert len(compact) <= 280
    assert compact.endswith(url)


def test_pre_publisher_failure_records_failed_health(tmp_path, monkeypatch):
    health = tmp_path / "x_publisher_health.json"
    health.write_text(json.dumps({
        "last_published_at": "2026-08-26T09:09:44-05:00",
        "forced_slot": None,
    }), encoding="utf-8")
    monkeypatch.setattr(failure_health, "HEALTH_PATH", health)
    now = datetime(2026, 8, 27, 9, 0, tzinfo=ZoneInfo("America/Chicago"))

    payload = failure_health.write_failure(
        "environment fetch failed",
        publish_requested=True,
        now=now,
    )

    assert payload["last_outcome"] == "failed"
    assert payload["exit_code"] == 1
    assert payload["publish_requested"] is True
    assert payload["last_failure_at"] == now.isoformat()
    assert payload["last_published_at"] == "2026-08-26T09:09:44-05:00"
