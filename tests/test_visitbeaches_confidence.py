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
    return {"flag": flag, "purple": purple, "flag_conflict": conflict, "report_at": "2026-09-09T18:00:00Z", "freshness_hours": 24}


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


def test_alias_is_not_disagreement():
    now, current = base("Single Red")
    assert confidence(current, vb("Red"), now)[0] == "corroborated"


def test_visitbeaches_cannot_corroborate_itself():
    now, current = base()
    current["source_url"] = "https://visitbeaches.org/map"
    assert confidence(current, vb(), now)[0] == "same_source"


def test_secondary_expires_at_decision_time():
    now, current = base(None)
    secondary = vb("Green")
    secondary["report_at"] = (now - timedelta(hours=24)).isoformat()
    assert confidence(current, secondary, now)[0] == "primary_only"


def test_cached_summary_never_overrides_observations():
    now, current = base(None)
    secondary = vb("Green")
    secondary["observations"] = [{"flag": "Green", "fresh": True, "created_at": "2026-09-01T18:00:00Z"}]
    assert confidence(current, secondary, now)[0] == "primary_only"


def test_apply_preserves_last_known_closure_and_purple(tmp_path, monkeypatch):
    import json
    from scripts import apply_visitbeaches_confidence as module
    now, current = base('Double Red', True, age_hours=30)
    primary = tmp_path / 'current.json'
    primary.write_text(json.dumps(current))
    (tmp_path / 'pcb.json').write_text(json.dumps(vb('Green')))
    monkeypatch.setattr(module, 'VB', tmp_path)
    monkeypatch.setattr(module, 'current_path', lambda slug: primary)
    module.apply('pcb', now=now)
    result = json.loads(primary.read_text())
    assert result['flag'] == 'Double Red'
    assert result['purple'] is True
    assert result['last_verified_at'] == current['last_verified_at']


def test_apply_gap_fill_retains_observation_not_check_time(tmp_path, monkeypatch):
    import json
    from scripts import apply_visitbeaches_confidence as module
    now, current = base(None)
    secondary = vb('Green')
    secondary['checked_at'] = now.isoformat()
    primary = tmp_path / 'current.json'
    primary.write_text(json.dumps(current))
    (tmp_path / 'pcb.json').write_text(json.dumps(secondary))
    monkeypatch.setattr(module, 'VB', tmp_path)
    monkeypatch.setattr(module, 'current_path', lambda slug: primary)
    assert module.apply('pcb', now=now) == 'visitbeaches_gap_filled'
    result = json.loads(primary.read_text())
    assert result['observed_at'] == secondary['report_at']
    assert result['last_checked_at'] == secondary['checked_at']
    assert result['source_lineage'] == 'visitbeaches'
    assert result['visitbeaches_evidence']['freshness_hours'] == 24


def test_failed_primary_check_cannot_corroborate():
    now, current = base()
    current['source_check_status'] = 'unavailable'
    assert confidence(current, vb(), now)[0] == 'primary_unverified'
