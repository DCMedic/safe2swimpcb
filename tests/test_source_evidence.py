from datetime import datetime, timezone
import pytest
from scripts.source_evidence import fresh_at, current_visitbeaches, observation_time

NOW = datetime(2026, 9, 9, 19, tzinfo=timezone.utc)

@pytest.mark.parametrize('ttl', [None, 0, -1, float('nan'), float('inf'), 25, '24', True])
def test_invalid_ttl_fails_closed(ttl):
    assert not fresh_at('2026-09-09T18:00:00Z', ttl, NOW)

@pytest.mark.parametrize('stamp', [None, '', 'bad', '2026-09-09T18:00:00', '2026-09-09T19:00:01Z', '2026-09-08T19:00:00Z'])
def test_invalid_future_or_expired_stamp_fails_closed(stamp):
    assert not fresh_at(stamp, 24, NOW)


def test_check_time_never_replaces_observation():
    assert observation_time({'last_checked_at': NOW.isoformat()}) is None
    assert observation_time({'observed_at': None, 'last_verified_at': NOW.isoformat()}) is None


def test_conflict_preserves_closure_and_purple_evidence():
    result = current_visitbeaches({'freshness_hours': 24, 'observations': [
        {'created_at': '2026-09-09T18:00:00Z', 'flag': None, 'reported_flags': ['Green', 'Double Red'], 'flag_conflict': True, 'purple': True}
    ]}, NOW)
    assert result['flag'] is None
    assert result['flag_conflict']
    assert result['purple']
    assert 'Double Red' in result['fresh_distinct_flags']


def test_null_secondary_report_time_cannot_fallback():
    result = current_visitbeaches({'flag': 'Green', 'freshness_hours': 24, 'report_at': None,
                                  'newest_flag_report': {'created_at': NOW.isoformat()}}, NOW)
    assert result['flag'] is None


def test_direct_primary_resets_old_gap_fill_identity_and_times():
    from scripts.source_evidence import reset_primary_evidence, visitbeaches_lineage
    record = {'observed_at': 'old', 'observation_at': 'old', 'official_updated_at': 'old',
              'source_lineage': 'visitbeaches', 'source_data_url': 'https://api.visitbeaches.org/graphql',
              'source_url': 'https://authority.example', 'source_name': 'Authority',
              'visitbeaches_flag_conflict': True}
    reset_primary_evidence(record, NOW.isoformat(), record['source_url'])
    assert observation_time(record) == NOW.isoformat()
    assert not visitbeaches_lineage(record)
    assert 'visitbeaches_flag_conflict' not in record


def test_shared_cross_language_fixtures():
    import json
    from pathlib import Path
    from scripts.source_evidence import canonical_flag, parse_time, visitbeaches_lineage
    fixture = json.loads((Path(__file__).parent / 'fixtures/source_evidence.json').read_text())
    now = parse_time(fixture['now'])
    for case in fixture['freshness']:
        assert fresh_at(case['stamp'], case['hours'], now) == case['fresh'], case['name']
    for case in fixture['flags']:
        assert canonical_flag(case['input']) == case['canonical']
    for case in fixture['observations']:
        assert observation_time(case['record']) == case['stamp']
    for case in fixture['lineages']:
        assert visitbeaches_lineage(case['record']) == case['visitbeaches']


def test_aggregate_timestamp_includes_older_purple_only_report():
    record = {'freshness_hours': 24, 'observations': [
        {'created_at': '2026-09-08T20:00:00Z', 'purple': True},
        {'created_at': '2026-09-09T18:00:00Z', 'flag': 'Green'},
    ]}
    result = current_visitbeaches(record, NOW)
    assert result['flag'] == 'Green'
    assert result['purple'] is True
    assert result['report_at'] == '2026-09-08T20:00:00Z'
    later = datetime(2026, 9, 9, 20, tzinfo=timezone.utc)
    assert not fresh_at(result['report_at'], result['freshness_hours'], later)
    assert current_visitbeaches(record, later)['purple'] is False
