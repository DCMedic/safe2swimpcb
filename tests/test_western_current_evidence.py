from scripts.refresh_western_current_flags import (
    eligible_current_flag_images,
    parse_explicit_current_status,
    parse_pensacola_api_payload,
)


def test_definition_legend_is_not_current_status():
    html = """
    <html><body>
      <h2>Beach Warning Flag System</h2>
      <p>Green Flag - Low Hazard</p>
      <p>Yellow Flag - Medium Hazard</p>
      <p>Red Flag - High Hazard</p>
      <p>Double Red Flag - Water Closed to Public</p>
    </body></html>
    """
    flag, evidence, purple = parse_explicit_current_status(html)
    assert flag is None
    assert evidence is None
    assert purple is False


def test_explicit_current_status_is_accepted():
    html = """
    <html><body>
      <h1>Today's Warning Condition: Beach Flags</h1>
      <h2>Current Status: Water Closed to Public</h2>
      <p>Beach Warning Flag System</p>
      <p>Yellow Flag - Medium Hazard</p>
    </body></html>
    """
    flag, evidence, purple = parse_explicit_current_status(html)
    assert flag == "Double Red"
    assert "Current Status" in evidence
    assert purple is False


def test_current_status_wins_despite_other_legend_terms():
    html = """
    <html><body>
      <div>Current Flag: Medium Hazard</div>
      <section>
        <p>High Hazard means high surf and strong currents.</p>
        <p>Water Closed to Public means do not enter the water.</p>
      </section>
    </body></html>
    """
    flag, _, purple = parse_explicit_current_status(html)
    assert flag == "Yellow"
    assert purple is False


def test_navarre_current_surf_conditions_maps_yellow_plus_purple():
    html = """
    <html><body>
      <div class="surf-condition-banner">
        <strong>Current Surf Conditions</strong>
        <span>Moderate Hazard</span>
        <span>Dangerous Marine Life</span>
      </div>
    </body></html>
    """
    flag, evidence, purple = parse_explicit_current_status(html)
    assert flag == "Yellow"
    assert "Current Surf Conditions" in evidence
    assert purple is True


def test_distant_purple_legend_does_not_attach_to_current_yellow():
    html = """
    <html><body>
      <div>Current Surf Conditions: Moderate Hazard</div>
      <div>""" + ("ordinary beach information " * 20) + """</div>
      <section><h2>Flag System</h2><p>Purple Flag - Dangerous Marine Life</p></section>
    </body></html>
    """
    flag, _, purple = parse_explicit_current_status(html)
    assert flag == "Yellow"
    assert purple is False


def test_pensacola_api_uses_current_level_not_tomorrow_forecast():
    payload = {
        "CurrentHazardLevel": 2,
        "CurrentWaterTemp": 86,
        "IsDangerousMarineLifePresent": False,
        "DateTimeCreated": "2026-09-09T14:35:00Z",
        "Level1ForecastPercentage": 30,
        "Level2ForecastPercentage": 70,
        "Level3ForecastPercentage": 0,
        "Level4ForecastPercentage": 0,
        "DangerousMarineLifeForecastPercentage": 20,
    }
    flag, purple, metadata = parse_pensacola_api_payload(payload)
    assert flag == "Yellow"
    assert purple is False
    assert metadata["current_hazard_level"] == 2
    assert metadata["current_water_temp_f"] == 86
    assert metadata["official_updated_at"].endswith("-05:00")


def test_pensacola_current_purple_is_independent_of_forecast_purple():
    payload = {
        "CurrentHazardLevel": 2,
        "IsDangerousMarineLifePresent": True,
        "DangerousMarineLifeForecastPercentage": 0,
    }
    flag, purple, _ = parse_pensacola_api_payload(payload)
    assert flag == "Yellow"
    assert purple is True


def test_pensacola_forecast_only_payload_cannot_publish_current_flag():
    payload = {
        "Level1ForecastPercentage": 30,
        "Level2ForecastPercentage": 70,
        "DangerousMarineLifeForecastPercentage": 20,
    }
    flag, purple, _ = parse_pensacola_api_payload(payload)
    assert flag is None
    assert purple is False


def test_pensacola_api_level_mapping():
    assert parse_pensacola_api_payload({"CurrentHazardLevel": 1})[0] == "Green"
    assert parse_pensacola_api_payload({"CurrentHazardLevel": 2})[0] == "Yellow"
    assert parse_pensacola_api_payload({"CurrentHazardLevel": 3})[0] == "Single Red"
    assert parse_pensacola_api_payload({"CurrentHazardLevel": 4})[0] == "Double Red"


def test_legend_images_are_never_current_candidates():
    html = """
    <html><body>
      <section>
        <h2>Beach Warning Flag System</h2>
        <p>What each flag means</p>
        <img src="/green.png" alt="Green flag - Low Hazard">
        <img src="/yellow.png" alt="Yellow flag - Medium Hazard">
        <img src="/red.png" alt="Red flag - High Hazard">
      </section>
    </body></html>
    """
    assert eligible_current_flag_images(html, "https://example.gov/page") == []


def test_explicit_current_condition_image_is_candidate():
    html = """
    <html><body>
      <section>
        <h2>Today's Beach Flag Conditions</h2>
        <div class="current-condition">
          <img src="/media/today-flag.png" alt="Current beach flag">
        </div>
      </section>
    </body></html>
    """
    images = eligible_current_flag_images(html, "https://example.gov/status")
    assert len(images) == 1
    assert images[0]["url"] == "https://example.gov/media/today-flag.png"


def test_current_heading_does_not_override_nested_legend():
    html = """
    <html><body>
      <main>
        <h1>Current Beach Information</h1>
        <section>
          <h2>Flag System</h2>
          <p>Safety guide and flag meanings</p>
          <img src="/chart.png" alt="Flag warning system chart">
        </section>
      </main>
    </body></html>
    """
    assert eligible_current_flag_images(html, "https://example.gov/") == []
