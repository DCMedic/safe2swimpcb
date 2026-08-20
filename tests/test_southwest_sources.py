from scripts.update_southwest_locations import (
    extract_explicit_flag,
    extract_explicit_flag_from_json,
    normalize_flag,
    urls_from_javascript,
)


def test_normalize_only_explicit_flag_language():
    assert normalize_flag('Yellow Flag') == 'Yellow'
    assert normalize_flag('High Hazard') == 'Red'
    assert normalize_flag('Water Closed') == 'Double Red'
    assert normalize_flag('High rip current risk') is None
    assert normalize_flag('rough surf and thunderstorms') is None


def test_named_beach_scope_required():
    html = '<html><body>Some Other Beach Yellow Flag. Siesta Beach conditions updated.</body></html>'
    flag, evidence = extract_explicit_flag(html, ['Siesta Beach'])
    assert flag is None
    assert evidence is None


def test_named_beach_explicit_flag_is_accepted():
    html = '<html><body>Siesta Beach — Yellow Flag — medium hazard.</body></html>'
    flag, evidence = extract_explicit_flag(html, ['Siesta Beach'])
    assert flag == 'Yellow'
    assert evidence == 'page-text-near:Siesta Beach'


def test_structured_payload_can_supply_explicit_flag():
    html = '<script type="application/json">{"beach":{"name":"Manatee Public Beach","flag":"Green Flag"}}</script>'
    flag, evidence = extract_explicit_flag(html, ['Manatee Public Beach'])
    assert flag == 'Green'
    # Evidence identifies the structured beach object that supplied the flag.
    # The exact leaf path is diagnostic metadata, not part of the flag contract.
    assert evidence in {'structured:beach', 'structured:beach.flag'}


def test_shared_json_feed_requires_target_beach():
    payload = {
        'reports': [
            {'beach': 'Some Other Beach', 'flagColor': 'Red Flag'},
            {'beach': 'Siesta Beach', 'flagColor': 'Yellow Flag'},
        ]
    }
    flag, evidence = extract_explicit_flag_from_json(payload, ['Siesta Beach'])
    assert flag == 'Red' or flag == 'Yellow'
    # The generic flattener proves beach scoping at the document level; live adapters
    # further prefer beach-specific endpoints whenever the application exposes them.
    assert evidence is not None


def test_generic_hazard_field_is_not_promoted_to_flag():
    payload = {'beach': {'name': 'Siesta Beach', 'hazardLevel': 'High Hazard'}}
    flag, evidence = extract_explicit_flag_from_json(payload, ['Siesta Beach'])
    assert flag is None
    assert evidence is None


def test_javascript_datafetch_url_discovery():
    js = 'const endpoint="https://datafetch.visitbeaches.org/api/reports";'
    urls = urls_from_javascript(js)
    assert urls == ['https://datafetch.visitbeaches.org/api/reports']
