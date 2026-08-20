from scripts.update_destin_current import parse_destin_flag


def page(status: str) -> str:
    return f"""
    <html><body>
      <h2>Today's Warning Condition</h2>
      <div class="current-condition">Current Status: {status}</div>
      <section class="legend">
        Low Hazard Green Flag Medium Hazard Yellow Flag High Hazard Red Flag
      </section>
    </body></html>
    """


def test_destin_low_hazard():
    assert parse_destin_flag(page("Low Hazard")) == "Green"


def test_destin_medium_hazard():
    assert parse_destin_flag(page("Medium Hazard")) == "Yellow"


def test_destin_moderate_hazard_variant():
    assert parse_destin_flag(page("Moderate Hazard")) == "Yellow"


def test_destin_high_hazard():
    assert parse_destin_flag(page("High Hazard")) == "Single Red"


def test_destin_water_closed_variants():
    assert parse_destin_flag(page("Water Closed")) == "Double Red"
    assert parse_destin_flag(page("Water Closed to Public")) == "Double Red"
