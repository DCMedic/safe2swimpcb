from scripts.run_x_publisher import classify


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
