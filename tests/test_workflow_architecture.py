from scripts.validate_workflows import validate


def test_workflow_architecture_invariants():
    assert validate() == []
