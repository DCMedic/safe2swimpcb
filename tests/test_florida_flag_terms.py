from scripts.florida_flag_terms import interpret_florida_flag_terms, primary_flag


def test_standard_primary_terms():
    assert primary_flag('Water Closed to Public') == 'Double Red'
    assert primary_flag('High Hazard') == 'Red'
    assert primary_flag('High Surf and/or Currents') == 'Red'
    assert primary_flag('Medium Hazard') == 'Yellow'
    assert primary_flag('Moderate Hazard') == 'Yellow'
    assert primary_flag('Moderate Surf and/or Currents') == 'Yellow'
    assert primary_flag('Low Hazard') == 'Green'
    assert primary_flag('Calm Conditions, Exercise Caution') == 'Green'


def test_literal_color_terms_are_supported():
    assert primary_flag('Double Red Flag') == 'Double Red'
    assert primary_flag('Single Red Flag') == 'Red'
    assert primary_flag('Yellow Flag') == 'Yellow'
    assert primary_flag('Green Flag') == 'Green'
    assert primary_flag('Double Red') == 'Double Red'
    assert primary_flag('Red') == 'Red'
    assert primary_flag('Yellow') == 'Yellow'
    assert primary_flag('Green') == 'Green'
    assert interpret_florida_flag_terms('Purple').purple is True


def test_purple_is_independent_overlay():
    state = interpret_florida_flag_terms('Medium Hazard. Dangerous Marine Life.')
    assert state.primary == 'Yellow'
    assert state.purple is True
    assert state.label == 'Yellow + Purple'

    purple_only = interpret_florida_flag_terms('Dangerous Marine Life')
    assert purple_only.primary is None
    assert purple_only.purple is True
    assert purple_only.label == 'Purple'


def test_forecast_risk_is_not_promoted_to_flag():
    assert primary_flag('High rip current risk') is None
    assert primary_flag('Moderate rip current risk') is None
    assert primary_flag('High surf advisory') is None
    assert primary_flag('Hazard score: high') is None


def test_legend_can_be_interpreted_but_context_must_be_enforced_by_collectors():
    # The terminology layer answers only what a phrase means. Collectors are
    # responsible for proving that the phrase is a current beach status and
    # not merely an educational legend.
    assert primary_flag('High Hazard') == 'Red'
