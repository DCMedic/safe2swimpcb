from pathlib import Path

import pytest

from scripts.validate_workflows import validate, validate_preview_boundary


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
