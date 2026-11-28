"""Previews must not consume posting state or impersonate live health."""
import json
import sys
from types import SimpleNamespace

import pytest

from scripts import mark_x_publisher_failure as failure
from scripts import run_x_publisher as publisher
from scripts import x_content_engine as engine


@pytest.fixture
def publisher_files(tmp_path, monkeypatch):
    state = tmp_path / "x_posting_state.json"
    health = tmp_path / "x_publisher_health.json"
    state.write_text(json.dumps(engine.initial_state()))
    health.write_text('{"last_evaluated_at":"2026-01-01T00:00:00Z"}\n')
    monkeypatch.setattr(engine, "STATE_PATH", state)
    monkeypatch.setattr(publisher, "HEALTH_PATH", health)
    monkeypatch.setattr(failure, "HEALTH_PATH", health)
    monkeypatch.setitem(sys.modules, "x_content_engine", engine)

    def unexpected_publish(*args, **kwargs):
        pytest.fail("A preview attempted to contact X")

    monkeypatch.setitem(sys.modules, "post_to_x", SimpleNamespace(publish=unexpected_publish))
    return state, health


@pytest.mark.parametrize("mode", [[], ["--dry-run"]])
@pytest.mark.parametrize("scenario", ["selected", "no_slot", "guardrail", "too_long", "exception"])
def test_preview_never_writes_state_or_health(publisher_files, monkeypatch, mode, scenario):
    state, health = publisher_files
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (state, health)}

    def choose(s, now, forced):
        # Real candidate selection mutates the in-memory flag baseline.
        s["flag_state"]["Panama City Beach"] = "Double Red"
        if scenario == "exception":
            raise RuntimeError("fixture failure")
        if scenario == "no_slot":
            return None
        return engine.Candidate("education", "x" * 300 if scenario == "too_long" else "Follow posted flags.")

    monkeypatch.setattr(engine, "choose_candidate", choose)
    if scenario == "guardrail":
        monkeypatch.setattr(engine, "guardrails_allow", lambda *args: (False, "daily post cap"))
    if scenario == "too_long":
        monkeypatch.setattr(publisher, "fit_post", lambda text, *args: text)
    monkeypatch.setattr(sys, "argv", ["run_x_publisher.py", *mode])
    assert publisher.main() == (1 if scenario in {"exception", "too_long"} else 0)
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (state, health)} == before


def test_preview_does_not_create_missing_files(publisher_files, monkeypatch):
    state, health = publisher_files
    state.unlink()
    health.unlink()
    monkeypatch.setattr(engine, "LOCATIONS", {})
    monkeypatch.setattr(sys, "argv", ["run_x_publisher.py", "--dry-run", "--force-slot", "afternoon"])
    assert publisher.main() == 0
    assert not state.exists()
    assert not health.exists()


def test_preview_preserves_flag_change_for_next_live_evaluation(publisher_files, monkeypatch, capsys):
    state, _ = publisher_files
    payload = engine.initial_state()
    payload["flag_state"] = {"Test Beach": "Yellow"}
    state.write_text(json.dumps(payload))
    monkeypatch.setattr(engine, "LOCATIONS", {"Test Beach": state.parent / "flag.json"})
    monkeypatch.setattr(engine, "fresh_flag", lambda *args: {"label": "Red"})
    monkeypatch.setattr(sys, "argv", ["run_x_publisher.py", "--dry-run"])
    assert publisher.main() == 0
    assert "SELECTED_KIND=flag-change" in capsys.readouterr().out
    assert publisher.main() == 0
    assert "SELECTED_KIND=flag-change" in capsys.readouterr().out
    assert json.loads(state.read_text())["flag_state"]["Test Beach"] == "Yellow"


def test_failed_preview_does_not_replace_live_health(publisher_files):
    _, health = publisher_files
    before = health.read_bytes()
    failure.write_failure("preview failed", publish_requested=False)
    assert health.read_bytes() == before


def test_publish_still_records_state_and_health(publisher_files, monkeypatch):
    state, health = publisher_files
    monkeypatch.setattr(engine, "LOCATIONS", {})
    monkeypatch.setitem(sys.modules, "post_to_x", SimpleNamespace(publish=lambda text: ("fixture-id", {})))
    monkeypatch.setattr(sys, "argv", ["run_x_publisher.py", "--publish", "--force-slot", "afternoon"])
    assert publisher.main() == 0
    assert json.loads(state.read_text())["sequence"] == 1
    assert json.loads(health.read_text())["last_outcome"] == "published"


@pytest.mark.parametrize("module", [engine, publisher])
def test_conflicting_modes_rejected(module, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["publisher", "--dry-run", "--publish"])
    with pytest.raises(SystemExit) as exc:
        module.parse_args()
    assert exc.value.code == 2
