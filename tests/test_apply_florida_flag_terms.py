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
        'source_url': 'https://example.com/current',
        'official_authority_url': 'https://example.com/current',
    }
    normalized, _ = update_payload('destin', payload, _Session())
    assert normalized['flag'] == 'Red'
    assert normalized['primary_flag'] == 'Red'
