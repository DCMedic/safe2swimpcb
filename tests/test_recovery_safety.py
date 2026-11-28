import json
import sys
import urllib.error
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import recovery_watchdog as watchdog

REPO = "DCMedic/safe2swimpcb"
WORKFLOW = ".github/workflows/example.yml"
NOW = datetime(2026, 11, 11, 18, tzinfo=timezone.utc)
RUN_TITLES = {"production": "Know the Gulf X: publish", "preview": "Know the Gulf X: preview"}


@pytest.fixture
def policy(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "ROOT", tmp_path)
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"repository": REPO, "lanes": {"test": {
        "heartbeat_path": "missing.json", "heartbeat_field": "at",
        "workflow_path": WORKFLOW, "overdue_minutes": 30,
    }}}))
    return path


def run_record(**overrides):
    return {"id": 7, "workflow_id": 55, "head_branch": "main",
            "head_repository": {"full_name": REPO}, "event": "schedule",
            "status": "queued", "created_at": "2026-11-11T12:00:00Z", **overrides}


def test_default_cli_is_offline_even_with_token(policy, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fixture")
    monkeypatch.setattr(sys, "argv", ["watchdog", "--policy", str(policy), "--repo", REPO])
    monkeypatch.setattr(watchdog.urllib.request, "urlopen", lambda *a, **k: pytest.fail("preview used network"))
    before = policy.read_bytes()
    assert watchdog.main() == 0
    assert policy.read_bytes() == before
    assert list(policy.parent.iterdir()) == [policy]


def test_apply_rejects_development_ref(policy, monkeypatch):
    monkeypatch.setenv("GITHUB_REF", "refs/heads/dev/test")
    monkeypatch.setattr(sys, "argv", ["watchdog", "--apply", "--policy", str(policy)])
    with pytest.raises(SystemExit) as exc:
        watchdog.main()
    assert exc.value.code == 2


def test_wrong_repository_is_rejected(policy, monkeypatch):
    monkeypatch.setattr(watchdog, "workflow_recovery_state", lambda *a: pytest.fail("wrong repo queried"))
    assert watchdog.evaluate(policy, NOW, "other/repo", "fixture", False) == 1


def test_disabled_lane_does_not_touch_github(policy, monkeypatch):
    value = json.loads(policy.read_text())
    value["lanes"]["test"]["enabled"] = False
    policy.write_text(json.dumps(value))
    monkeypatch.setattr(watchdog, "github_json", lambda *a: pytest.fail("disabled lane queried"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0


@pytest.mark.parametrize("state", ["disabled_manually", "disabled_inactivity", "deleted", None])
def test_disabled_workflow_never_recovers(state, monkeypatch):
    monkeypatch.setattr(watchdog, "github_json", lambda *a: {"state": state})
    reason, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 120, 90, 60, NOW, "fixture")
    assert "not active" in reason
    assert stuck == []


def test_run_queries_scope_branch_repo_workflow_and_event(monkeypatch):
    calls = []
    records = [run_record(), run_record(id=8, head_branch="dev/test"),
               run_record(id=9, head_repository={"full_name": "fork/repo"}),
               run_record(id=10, event="pull_request"), run_record(id=11, workflow_id=99)]

    def read(url, token):
        calls.append(url)
        if not urlparse(url).query:
            return {"state": "active", "path": WORKFLOW, "id": 55}
        query = parse_qs(urlparse(url).query)
        assert query["branch"] == ["main"]
        return {"workflow_runs": records}

    monkeypatch.setattr(watchdog, "github_json", read)
    reason, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 120, 90, 60, NOW, "fixture")
    assert reason is None
    assert [r["id"] for r in stuck] == [7]
    assert len(calls) == 7


def test_active_runs_beyond_recent_page_are_found(monkeypatch):
    def read(url, token):
        query = parse_qs(urlparse(url).query)
        if not query:
            return {"state": "active", "path": WORKFLOW, "id": 55}
        return {"workflow_runs": [run_record()] if query.get("status") == ["queued"] else []}

    monkeypatch.setattr(watchdog, "github_json", read)
    _, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 120, 90, 60, NOW, "fixture")
    assert len(stuck) == 1


def test_active_run_pagination_is_complete(monkeypatch):
    pages = []

    def read(url, token):
        query = parse_qs(urlparse(url).query)
        if not query:
            return {"state": "active", "path": WORKFLOW, "id": 55}
        if query.get("status") != ["queued"]:
            return {"workflow_runs": []}
        page = int(query["page"][0])
        pages.append(page)
        return {"workflow_runs": [run_record(id=i + 1) for i in range(100)] if page == 1 else [run_record(id=101)]}

    monkeypatch.setattr(watchdog, "github_json", read)
    _, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 120, 90, 60, NOW, "fixture")
    assert len(stuck) == 101
    assert pages == [1, 2]


@pytest.mark.parametrize("response", [{}, {"workflow_runs": None}, {"workflow_runs": [{}]}])
def test_incomplete_run_results_fail_closed(response, policy, monkeypatch):
    def read(url, token):
        if not urlparse(url).query:
            return {"state": "active", "path": WORKFLOW, "id": 55}
        return response

    monkeypatch.setattr(watchdog, "github_json", read)
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: pytest.fail("dispatched with incomplete data"))
    monkeypatch.setattr(watchdog, "cancel_workflow_run", lambda *a: pytest.fail("canceled with incomplete data"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 1


def test_apply_without_token_does_not_mutate(policy, monkeypatch):
    monkeypatch.setattr(watchdog, "workflow_recovery_state", lambda *a: pytest.fail("queried without token"))
    assert watchdog.evaluate(policy, NOW, REPO, None, False) == 1


def test_failed_cancel_does_not_dispatch(policy, monkeypatch):
    monkeypatch.setattr(watchdog, "workflow_recovery_state", lambda *a: (None, [run_record()]))

    def failed_cancel(*args):
        raise urllib.error.HTTPError("https://api.github.com/", 403, "Forbidden", {}, None)

    monkeypatch.setattr(watchdog, "cancel_workflow_run", failed_cancel)
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: pytest.fail("dispatched after cancellation failure"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 1


@pytest.mark.parametrize("code", [202, 409, 422])
@pytest.mark.parametrize("status,completed", [("in_progress", False), ("completed", True)])
def test_cancel_needs_confirmed_completion(monkeypatch, code, status, completed):
    class Response:
        status = code
        def __enter__(self): return self
        def __exit__(self, *args): return False

    def open_url(request, **kwargs):
        if code != 202:
            raise urllib.error.HTTPError(request.full_url, code, "fixture", {}, None)
        return Response()

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", open_url)
    monkeypatch.setattr(watchdog, "github_json", lambda *args: {"status": status})
    assert watchdog.cancel_workflow_run(REPO, 7, "fixture") is completed


def test_pending_cancellation_defers_dispatch(policy, monkeypatch):
    monkeypatch.setattr(watchdog, "workflow_recovery_state", lambda *a: (None, [run_record()]))
    monkeypatch.setattr(watchdog, "cancel_workflow_run", lambda *a: False)
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: pytest.fail("dispatched before completion"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0


def test_new_run_or_pause_before_dispatch_suppresses_recovery(policy, monkeypatch):
    snapshots = iter([(None, []), ("new active run", [])])
    monkeypatch.setattr(watchdog, "workflow_recovery_state", lambda *a: next(snapshots))
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: pytest.fail("dispatched despite new run"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0


def test_clear_live_check_dispatches_once(policy, monkeypatch):
    calls = []
    monkeypatch.setattr(watchdog, "workflow_recovery_state", lambda *a: (None, []))
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: calls.append(a))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0
    assert len(calls) == 1


def test_protected_environment_wait_never_becomes_cancellation_candidate():
    run = run_record(status="waiting")
    recent, stuck = watchdog.split_active_runs([run], 30, NOW)
    assert recent == [run]
    assert stuck == []
    assert "already waiting" in watchdog.recovery_suppression_reason([run], 120, 90, NOW)


def mock_run_api(monkeypatch, records):
    def read(url, token):
        query = parse_qs(urlparse(url).query)
        if not query:
            return {"state": "active", "path": WORKFLOW, "id": 55}
        status = query.get("status", [None])[0]
        return {"workflow_runs": [run for run in records if status is None or run.get("status") == status]}
    monkeypatch.setattr(watchdog, "github_json", read)


@pytest.mark.parametrize("status,conclusion", [("completed", "success"), ("completed", "failure"), ("queued", None)])
def test_x_preview_never_suppresses_or_becomes_cancellation_target(monkeypatch, status, conclusion):
    preview = run_record(event="workflow_dispatch", status=status, conclusion=conclusion,
                         display_title=RUN_TITLES["preview"], created_at="2026-11-11T17:30:00Z")
    mock_run_api(monkeypatch, [preview])
    reason, stuck = watchdog.workflow_recovery_state(
        REPO, WORKFLOW, 360, 90, 25, NOW, "fixture",
        datetime(2026, 11, 11, 12, tzinfo=timezone.utc), RUN_TITLES,
    )
    assert reason is None
    assert stuck == []


def test_x_live_dispatch_still_honors_cooldown(monkeypatch):
    run = run_record(event="workflow_dispatch", status="completed", conclusion="success",
                     display_title=RUN_TITLES["production"], created_at="2026-11-11T17:50:00Z")
    mock_run_api(monkeypatch, [run])
    reason, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 360, 90, 45, NOW, "fixture", None, RUN_TITLES)
    assert "within 360m cooldown" in reason
    assert stuck == []


@pytest.mark.parametrize("status,conclusion", [("queued", None), ("completed", "success")])
def test_scheduled_recovery_is_not_blocked_by_x_preview(policy, monkeypatch, status, conclusion):
    value = json.loads(policy.read_text())
    value["lanes"]["test"].update(run_titles=RUN_TITLES, cooldown_minutes=360, stuck_run_minutes=25)
    policy.write_text(json.dumps(value))
    mock_run_api(monkeypatch, [run_record(event="workflow_dispatch", status=status, conclusion=conclusion,
                                       display_title=RUN_TITLES["preview"], created_at="2026-11-11T17:30:00Z")])
    dispatched = []
    monkeypatch.setattr(watchdog, "cancel_workflow_run", lambda *a: pytest.fail("preview was cancelled"))
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: dispatched.append(a))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0
    assert len(dispatched) == 1


def test_unmarked_legacy_active_run_is_not_auto_cancelled(monkeypatch):
    mock_run_api(monkeypatch, [run_record(event="workflow_dispatch")])
    reason, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 360, 90, 45, NOW, "fixture", None, RUN_TITLES)
    assert "already queued" in reason
    assert stuck == []


@pytest.mark.parametrize("created,delayed", [("2026-11-11T17:50:00Z", True), ("2026-11-11T11:00:00Z", False)])
def test_unmarked_legacy_completed_dispatch_has_bounded_conservative_delay(monkeypatch, created, delayed):
    mock_run_api(monkeypatch, [run_record(event="workflow_dispatch", status="completed", conclusion="success", created_at=created)])
    reason, stuck = watchdog.workflow_recovery_state(REPO, WORKFLOW, 360, 90, 45, NOW, "fixture", None, RUN_TITLES)
    assert bool(reason) is delayed
    if delayed:
        assert "unclassified legacy dispatch" in reason
    assert stuck == []


def test_watchdog_cancelled_dispatch_can_be_replaced_immediately(policy, monkeypatch):
    value = json.loads(policy.read_text())
    value["lanes"]["test"]["stuck_run_minutes"] = 25
    policy.write_text(json.dumps(value))
    records = [run_record(event="workflow_dispatch", created_at="2026-11-11T17:30:00Z")]
    mock_run_api(monkeypatch, records)
    dispatched = []

    def cancel(*args):
        records[0].update(status="completed", conclusion="cancelled")
        return True

    monkeypatch.setattr(watchdog, "cancel_workflow_run", cancel)
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: dispatched.append(a))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0
    assert len(dispatched) == 1


@pytest.mark.parametrize("race", ["other_cancelled", "completed_successfully", "new_active_attempt"])
def test_cancel_exception_does_not_ignore_other_suppression(policy, monkeypatch, race):
    value = json.loads(policy.read_text())
    value["lanes"]["test"]["stuck_run_minutes"] = 25
    policy.write_text(json.dumps(value))
    records = [run_record(event="workflow_dispatch", created_at="2026-11-11T17:30:00Z")]
    mock_run_api(monkeypatch, records)

    def cancel(*args):
        records[0].update(status="completed", conclusion="cancelled")
        if race == "other_cancelled":
            records.append(run_record(id=8, event="workflow_dispatch", status="completed", conclusion="cancelled", created_at="2026-11-11T17:50:00Z"))
        elif race == "completed_successfully":
            records[0]["conclusion"] = "success"
        else:
            records[0].update(status="in_progress", conclusion=None, created_at="2026-11-11T17:55:00Z")
        return True

    monkeypatch.setattr(watchdog, "cancel_workflow_run", cancel)
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: pytest.fail("ignored unrelated or racing run"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 0


@pytest.mark.parametrize("overrides", [
    {"status": None}, {"status": "unknown"}, {"created_at": None},
    {"created_at": "broken"}, {"status": "completed", "conclusion": None},
    {"status": "completed", "conclusion": "unknown"},
])
def test_partial_run_state_fails_closed(policy, monkeypatch, overrides):
    mock_run_api(monkeypatch, [run_record(**overrides)])
    monkeypatch.setattr(watchdog, "dispatch_workflow", lambda *a: pytest.fail("dispatched with uncertain run state"))
    monkeypatch.setattr(watchdog, "cancel_workflow_run", lambda *a: pytest.fail("cancelled with uncertain run state"))
    assert watchdog.evaluate(policy, NOW, REPO, "fixture", False) == 1
