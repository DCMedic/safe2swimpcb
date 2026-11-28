import json
from scripts import prerender_current_status as renderer
from scripts import verify_prerender_consistency as verifier

HTML = '<div id="flagPole" class="flagpole"><span class="flagshape"></span></div><div id="currentFlag" class="flagname">Loading</div><div id="currentMeaning" class="muted"></div><div id="flagFreshness" class="status flag-status">Loading</div>'


def test_prerender_is_snapshot_even_with_recent_double_red_purple(monkeypatch, tmp_path):
    data = {'flag': 'Double Red', 'purple': True, 'last_verified_at': '2026-11-11T12:00:00Z'}
    file = tmp_path / 'current_flag.json'
    file.write_text(json.dumps(data))
    monkeypatch.setattr(verifier, 'DATA', file)
    output = renderer.render_snapshot(HTML, data)
    assert 'Cached flag snapshot: Double Red + Purple' in output
    assert 'class="flagpole" hidden></div>' in output
    assert 'This snapshot may have expired' in output
    assert verifier.check_text(output) == []
    assert verifier.check_text(output.replace(' hidden', ''))
    assert verifier.check_text(output.replace('Double Red + Purple', 'Green'))
    assert renderer.render_snapshot(output, data) == output


def test_prerender_does_not_invent_flag_from_label():
    assert 'Green' not in renderer.snapshot_label({'label': 'Green'})
    assert renderer.snapshot_label({'flag': 'Single Red'}) == 'Cached flag snapshot: Red'


def test_prerender_preserves_conflict_and_rejects_malformed_flag():
    label = renderer.snapshot_label({'primary_flag': 'Green', 'flag': 'Double Red', 'flag_conflict': True, 'purple': True})
    assert 'Conflicting' in label and 'Double Red' in label and 'Purple' in label
    assert 'Cached flag snapshot: Green' not in label
    for flag in [['Green'], {}, True]:
        assert 'unavailable' in renderer.snapshot_label({'flag': flag})


def test_prerender_never_substitutes_poll_time_for_invalid_observation():
    for stamp in [None, 'malformed']:
        output = renderer.render_snapshot(HTML, {'flag': 'Green', 'observed_at': stamp, 'last_verified_at': '2026-11-11T12:00:00Z'})
        assert 'Evidence time unavailable' in output
        assert '2026-11-11T12:00:00Z' not in output


def test_build_gate_can_publish_unavailable_records_without_fabricated_freshness(monkeypatch, tmp_path):
    from scripts import site_health_check as health
    monkeypatch.setattr(health, 'ROOT', tmp_path)
    (tmp_path / 'data').mkdir()
    file = tmp_path / 'data/current_flag.json'
    data = {'flag': None, 'primary_flag': None, 'purple': False, 'label': 'Official flag unavailable',
            'source_name': 'Authority', 'source_url': 'https://example.org/current',
            'source_check_status': 'unavailable', 'last_verified_at': None, 'stale_after_hours': 0}
    file.write_text(json.dumps(data))
    errors = []
    health.validate_json(errors)
    assert errors == []
    data['flag'] = 'Green'
    file.write_text(json.dumps(data))
    health.validate_json(errors)
    assert any('stale_after_hours' in error for error in errors)
    assert any('missing last_verified_at' in error for error in errors)
