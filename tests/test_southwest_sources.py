from scripts.update_southwest_locations import extract_explicit_flag, normalize_flag


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
    assert evidence == 'structured:beach.flag'
