from datetime import datetime, timedelta, timezone

from scripts.apply_visitbeaches_confidence import confidence


def base(flag="Yellow", purple=False, age_hours=1):
    now = datetime(2026, 9, 9, 19, tzinfo=timezone.utc)
    return now, {
        "flag": flag,
        "purple": purple,
        "last_verified_at": (now - timedelta(hours=age_hours)).isoformat(),
        "stale_after_hours": 24,
    }


def vb(flag="Yellow", purple=False, conflict=False):
    return {"flag": flag, "purple": purple, "flag_conflict": conflict}


def test_fresh_primary_agreement_is_corroborated():
    now, current = base("Yellow", True)
    state, _ = confidence(current, vb("Yellow", True), now)
    assert state == "corroborated"


def test_fresh_primary_disagreement_is_not_overridden():
    now, current = base("Red", False)
    state, _ = confidence(current, vb("Yellow", False), now)
    assert state == "source_disagreement"


def test_missing_primary_can_be_gap_filled():
    now, current = base(None, False)
    state, _ = confidence(current, vb("Green", False), now)
    assert state == "visitbeaches_gap_fill"


def test_stale_primary_can_be_replaced_by_fresh_ambassador():
    now, current = base("Yellow", False, age_hours=30)
    state, _ = confidence(current, vb("Green", False), now)
    assert state == "visitbeaches_newer_than_stale_primary"


def test_internal_visitbeaches_conflict_never_promotes():
    now, current = base(None, False)
    state, _ = confidence(current, vb(None, False, True), now)
    assert state == "conflict"
