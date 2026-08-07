from scripts.update_ndbc_measured import _parse_ndbc_text
from scripts.update_tropical_cyclones import parse_hurdat2, haversine_miles
from scripts.hunt_pre2017_flags import parse_current_condition


def test_parse_ndbc_standard_met():
    text = """#YYYY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP
#yr mo dy hr mn degT m/s m/s m sec sec degT hPa degC degC
2024 08 01 12 00 180 5.0 7.0 1.2 6.0 5.0 190 1012.0 30.0 29.0
"""
    d = _parse_ndbc_text(text, "42039", "https://example.test/42039.txt")
    assert len(d) == 1
    assert d.iloc[0].station == "42039"
    assert float(d.iloc[0].WVHT) == 1.2
    assert float(d.iloc[0].WSPD) == 5.0
    assert d.iloc[0].date == "2024-08-01"


def test_parse_hurdat_and_distance():
    text = """AL092024, HELENE, 2,
20240926, 1200, L, HU, 29.0N, 84.0W, 105, 960,
20240926, 1800, L, HU, 30.2N, 84.5W, 110, 955,
"""
    d = parse_hurdat2(text)
    assert len(d) == 2
    assert d.iloc[0].storm_name == "HELENE"
    assert d.iloc[0].category == "Category 3"
    assert d.distance_to_pcb_mi.min() < 200
    assert haversine_miles(30.125, -85.730, 30.125, -85.730) == 0


def test_pre2017_current_condition_parser_avoids_legend():
    html = """
    <html><body>
      <h3>Current Beach Conditions:</h3><div>Yellow Flag</div>
      <h2>Beach Warning Flags</h2>
      <p>Double Red Flag: Water Closed</p><p>Red Flag: High Hazard</p>
    </body></html>
    """
    parsed = parse_current_condition(html)
    assert parsed is not None
    base, purple, evidence = parsed
    assert base == "Yellow"
    assert purple is False
    assert "Current Beach Conditions" in evidence
