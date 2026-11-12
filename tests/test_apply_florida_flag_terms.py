from scripts.apply_florida_flag_terms import (
    extract_page_state,
    state_from_current_text,
    state_from_structured,
    update_payload,
)


def test_current_status_high_hazard_maps_red():
    state, evidence = state_from_current_text('Current Status: High Hazard')
    assert state.primary == 'Red'
    assert 'High Hazard' in evidence


def test_current_status_bare_color_is_supported():
    state, evidence = state_from_current_text('Current Status: Yellow')
    assert state.primary == 'Yellow'
    assert 'Yellow' in evidence


def test_current_flag_phrasing_is_supported():
    state, evidence = state_from_current_text('Current Flag: Double Red')
    assert state.primary == 'Double Red'
    assert 'Double Red' in evidence

    state, evidence = state_from_current_text('Current Flag Conditions: Medium Hazard')
    assert state.primary == 'Yellow'
    assert 'Medium Hazard' in evidence

    state, evidence = state_from_current_text('Current Beach Flag Conditions: Low Hazard')
    assert state.primary == 'Green'
    assert 'Low Hazard' in evidence


def test_current_status_surf_words_map_primary_and_purple():
    state, _ = state_from_current_text(
        'Current Beach Conditions: Moderate Surf and/or Currents; Dangerous Marine Life'
    )
    assert state.primary == 'Yellow'
    assert state.purple is True


def test_static_legend_is_not_current_status():
    state, evidence = state_from_current_text(
        'Florida Beach Warning Flag System. Green Flag = Low Hazard. '
        'Yellow Flag = Medium Hazard. Red Flag = High Hazard. Double Red = Water Closed.'
    )
    assert state.primary is None
    assert state.purple is False
    assert evidence is None


def test_current_heading_cannot_reach_later_warning_section():
    state, evidence = state_from_current_text(
        'Current Conditions: For Gulf conditions and flag updates text SAFETY to 31279. '
        'Beach Flag Warnings Image Entering the Gulf during double red flag conditions can result in a fine.'
    )
    assert state.primary is None
    assert state.purple is False
    assert evidence is None


def test_current_heading_cannot_reach_later_rules_or_faq():
    state, evidence = state_from_current_text(
        'Current Conditions: Check the local authority. Rules Double Red means water closed. '
        'Frequently Asked Questions What do purple flags mean? Dangerous Marine Life.'
    )
    assert state.primary is None
    assert state.purple is False
    assert evidence is None


def test_generic_forecast_risk_is_not_a_flag():
    state, evidence = state_from_current_text('Current rip current risk: High')
    assert state.primary is None
    assert evidence is None


def test_red_tide_wording_is_not_a_red_flag():
    state, evidence = state_from_current_text('Current Conditions: no red tide observed; water clear')
    assert state.primary is None
    assert evidence is None


def test_structured_status_is_beach_scoped():
    payload = {
        'reports': [
            {'beach': 'Other Beach', 'status': 'High Hazard'},
            {'beach': 'Siesta Beach', 'status': 'Medium Hazard', 'marineLife': 'Dangerous Marine Life'},
        ]
    }
    state, evidence = state_from_structured(payload, ['Siesta Beach'])
    assert state.primary == 'Yellow'
    assert state.purple is True
    assert evidence is not None


def test_structured_legend_without_target_beach_is_ignored():
    payload = {'legend': {'red': {'status': 'High Hazard'}, 'yellow': {'status': 'Medium Hazard'}}}
    state, evidence = state_from_structured(payload, ['Siesta Beach'])
    assert state.primary is None
    assert evidence is None


def test_html_current_status_is_accepted_but_legend_is_ignored():
    html = '''
    <html><body>
      <h2>Current Status: Low Hazard</h2>
      <section><h3>Flag meanings</h3><p>Red Flag High Hazard</p></section>
    </body></html>
    '''
    state, _ = extract_page_state(html, [])
    assert state.primary == 'Green'


class _Response:
    text = '<html><body><h2>Current Status: High Hazard</h2></body></html>'

    def raise_for_status(self):
        return None


class _Session:
    def get(self, *_args, **_kwargs):
        return _Response()


def test_fresh_official_current_status_overrides_older_cached_primary():
    payload = {
        'flag': 'Yellow',
        'label': 'Yellow',
        'source_name': 'Older secondary report',
        'source_url': 'https://secondary.example/report',
        'official_authority': 'Official Beach Safety',
        'official_authority_url': 'https://official.example/current',
    }
    normalized, _ = update_payload('destin', payload, _Session())
    assert normalized['flag'] == 'Red'
    assert normalized['primary_flag'] == 'Red'
    assert normalized['source_name'] == 'Official Beach Safety'
    assert normalized['source_url'] == 'https://official.example/current'
    assert normalized['secondary_source_url'] == 'https://secondary.example/report'
    assert normalized['provenance_tier'] == 'primary_official_terminology'


def test_fresh_primary_does_not_inherit_stale_purple_overlay():
    payload = {
        'flag': 'Yellow',
        'label': 'Yellow + Purple',
        'purple': True,
        'source_name': 'Official Beach Safety',
        'source_url': 'https://official.example/current',
        'official_authority_url': 'https://official.example/current',
    }
    normalized, _ = update_payload('destin', payload, _Session())
    assert normalized['flag'] == 'Red'
    assert normalized['purple'] is False
    assert normalized['label'] == 'Red'


def test_successful_official_verification_clears_degraded_cache_metadata():
    payload = {
        'flag': 'Yellow',
        'label': 'Yellow',
        'cached': True,
        'source_check_status': 'degraded',
        'source_error': 'parser miss',
        'cache_age_hours': 1.5,
        'cached_from_provenance_tier': 'primary_official',
        'stale_reason': 'live verification failed',
        'source_name': 'Visit PCB',
        'source_url': 'https://official.example/current',
        'official_authority_url': 'https://official.example/current',
    }
    normalized, _ = update_payload('destin', payload, _Session())
    assert normalized['cached'] is False
    assert normalized['source_check_status'] == 'verified'
    assert normalized['stale_reason'] is None
    assert normalized['last_checked_at'] == normalized['last_verified_at']
    assert 'source_error' not in normalized
    assert 'cache_age_hours' not in normalized
    assert 'cached_from_provenance_tier' not in normalized


def test_direct_verification_replaces_gap_fill_timestamp_and_lineage():
    from scripts.source_evidence import visitbeaches_lineage
    payload = {'flag': 'Green', 'observed_at': '2000-01-01T00:00:00Z',
               'observation_at': None, 'source_lineage': 'visitbeaches',
               'source_url': 'https://visitbeaches.org/map',
               'source_data_url': 'https://api.visitbeaches.org/graphql',
               'source_name': 'VisitBeaches', 'official_authority': 'Local authority',
               'official_authority_url': 'https://authority.example', 'stale_after_hours': 3}
    result, _ = update_payload('test', payload, _Session())
    assert result['observed_at'] == result['last_verified_at']
    assert 'observation_at' not in result
    assert not visitbeaches_lineage(result)


def test_current_text_conflict_is_not_first_flag_wins():
    state, _ = state_from_current_text('Current Status: Green; Double Red; Purple Flag')
    assert state.primary is None
    assert state.conflict
    assert state.distinct_flags == ('Double Red', 'Green')
    assert state.purple


def test_structured_matching_records_are_all_checked_for_conflicts():
    state, _ = state_from_structured({'reports': [
        {'beach': 'Test Beach', 'status': 'Green'},
        {'beach': 'Test Beach', 'status': 'Double Red', 'marineLife': 'Dangerous Marine Life'},
    ]}, ['Test Beach'])
    assert state.primary is None
    assert state.conflict
    assert state.purple


def test_structured_beach_legend_is_not_observation():
    state, _ = state_from_structured({'beach': 'Test Beach', 'legend': {'flag': 'Double Red'}}, ['Test Beach'])
    assert state.primary is None


def test_new_conflict_clears_old_current_flag_and_checks_all_urls():
    class Session:
        def get(self, url, **kwargs):
            response = _Response()
            response.text = '<h2>Current Status: ' + ('Green; Purple Flag' if 'one' in url else 'Double Red') + '</h2>'
            return response
    payload = {'flag': 'Green', 'last_verified_at': '2026-11-11T00:00:00Z',
               'official_authority_url': 'https://one.example', 'source_url': 'https://two.example'}
    result, _ = update_payload('test', payload, Session())
    assert result['flag'] is None
    assert result['primary_flag'] is None
    assert result['flag_conflict'] is True
    assert result['fresh_distinct_flags'] == ['Double Red', 'Green']
    assert result['purple'] is True
    assert result['source_check_status'] == 'conflict'


def test_bare_current_color_list_is_conflict():
    state, _ = state_from_current_text('Current Status: Green; Red')
    assert state.primary is None
    assert state.conflict
    state, _ = state_from_structured({'beach': 'Test Beach', 'status': 'Green; Double Red'}, ['Test Beach'])
    assert state.primary is None
    assert state.conflict


def test_terminology_recheck_never_rejuvenates_dated_official_evidence():
    old_stamp = '2020-01-01T00:00:00Z'
    payload = {'flag': 'Green', 'official_authority_url': 'https://authority.example',
               'source_url': 'https://authority.example', 'official_updated_at': old_stamp,
               'stale_after_hours': 24}
    result, _ = update_payload('test', payload, _Session())
    assert result['observed_at'] == old_stamp
    assert result['official_updated_at'] == old_stamp
    assert result['last_checked_at'] != old_stamp
