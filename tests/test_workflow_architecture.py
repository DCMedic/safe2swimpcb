from pathlib import Path

import pytest

import json

from scripts.validate_workflows import validate, validate_preview_boundary, validate_x_run_titles


def test_workflow_architecture_invariants():
    assert validate() == []


@pytest.mark.parametrize("filename,live_job,mode", [
    ("x-production-publisher.yml", "publish", "publish"),
    ("recover-stale-lanes.yml", "recover", "apply"),
])
@pytest.mark.parametrize("unsafe_change", ["write_default", "preview_secret", "live_branch", "preview_persistence"])
def test_preview_boundary_rejects_unsafe_changes(filename, live_job, mode, unsafe_change):
    text = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / filename).read_text()
    if unsafe_change == "write_default":
        text = text.replace("  contents: read", "  contents: write", 1)
    elif unsafe_change == "preview_secret":
        text = text.replace("  preview:\n", "  preview:\n    env: {TOKEN: '${{ secrets.TOKEN }}'}\n")
    elif unsafe_change == "live_branch":
        text = text.replace("github.ref == 'refs/heads/main'", "true")
    else:
        text = text.replace("  preview:\n", "  preview:\n    run: bash scripts/persist_paths.sh\n")
    errors = []
    validate_preview_boundary(text, live_job, mode, errors)
    assert errors


@pytest.mark.parametrize("unsafe_change", ["run_gate", "preview_title", "completion_gate", "policy_title"])
def test_x_preview_isolated_from_recovery(unsafe_change):
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/x-production-publisher.yml").read_text()
    recovery = (root / ".github/workflows/recover-stale-lanes.yml").read_text()
    cfg = json.loads((root / ".github/recovery/policy.json").read_text())["lanes"]["x"]
    if unsafe_change == "run_gate":
        workflow = workflow.replace("github.ref == 'refs/heads/main'", "true", 1)
    elif unsafe_change == "preview_title":
        workflow = workflow.replace("Know the Gulf X: preview", "Know the Gulf X: publish", 1)
    elif unsafe_change == "completion_gate":
        recovery = recovery.replace("github.event.workflow_run.display_title == 'Know the Gulf X: publish'", "true")
    else:
        cfg["run_titles"]["production"] = "different title"
    errors = []
    validate_x_run_titles(workflow, recovery, cfg, errors)
    assert errors
