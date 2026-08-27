from datetime import datetime

from scripts.update_eastern_panhandle import (
    EASTERN,
    hours_old,
    normalize_flag,
    parse_franklin_page,
    parse_franklin_updated,
    parse_nws_flag_table,
    parse_nws_issued,
    verification_state,
)


def test_normalize_flag_variants():
    assert normalize_flag("DOUBLE RED.") == "Double Red"
    assert normalize_flag("Red") == "Red"
    assert normalize_flag("Yellow.") == "Yellow"
    assert normalize_flag("Green") == "Green"
    assert normalize_flag("Not Available") is None


def test_parse_nws_issue_timestamp():
    text = """
Surf Zone Forecast
National Weather Service Tallahassee FL
1136 AM EDT Tue Aug 18 2026
"""
    issued = parse_nws_issued(text)
    assert issued == datetime(2026, 8, 18, 11, 36, tzinfo=EASTERN)


def test_parse_nws_official_flag_table():
    text = """
Based on communication with area beach officials, the following flags
are flying at area beaches:

Walton........................Yellow
Bay...........................Yellow.
State Park Gulf Beaches.......Red
West Facing Gulf Beaches......Red.
South Facing Gulf Beaches.....Yellow
Franklin......................Green
"""
    flags = parse_nws_flag_table(text)
    assert flags["Walton"] == "Yellow"
    assert flags["State Park Gulf Beaches"] == "Red"
    assert flags["West Facing Gulf Beaches"] == "Red"
    assert flags["Franklin"] == "Green"


def test_parse_franklin_update_timestamp():
    now = datetime(2026, 8, 20, 18, 0, tzinfo=EASTERN)
    updated = parse_franklin_updated("Tuesday, August 18 at 12:00 PM EDT", now=now)
    assert updated == datetime(2026, 8, 18, 12, 0, tzinfo=EASTERN)


def test_parse_franklin_update_timestamp_tolerates_format_variants():
    now = datetime(2026, 8, 20, 18, 0, tzinfo=EASTERN)
    assert parse_franklin_updated("August 20, 2026 12:00 PM EDT", now=now) == datetime(2026, 8, 20, 12, 0, tzinfo=EASTERN)
    assert parse_franklin_updated("Thursday August 20 at 12:00 PM", now=now) == datetime(2026, 8, 20, 12, 0, tzinfo=EASTERN)


def test_parse_franklin_live_condition_page():
    fetched_at = datetime(2026, 8, 20, 18, 0, tzinfo=EASTERN)
    html = """
    <section>
      <h2>Current Beach Conditions</h2>
      <div>Last updated: Thursday, August 20 at 10:00 AM EDT</div>
      <img alt="Yellow Flag" src="flag.svg">
      <div>Medium Hazard</div>
    </section>
    """
    parsed = parse_franklin_page(html, fetched_at=fetched_at)
    assert parsed["flag"] == "Yellow"
    assert parsed["official_updated_text"] == "Thursday, August 20 at 10:00 AM EDT"
    assert parsed["official_updated_at"] == datetime(2026, 8, 20, 10, 0, tzinfo=EASTERN)
    assert parsed["timestamp_basis"] == "official_page"


def test_franklin_explicit_flag_survives_timestamp_markup_change():
    fetched_at = datetime(2026, 8, 20, 18, 0, tzinfo=EASTERN)
    html = """
    <section>
      <h2>Current Beach Conditions</h2>
      <div>Updated moments ago by Parks &amp; Recreation</div>
      <img alt="Yellow Flag" src="flag.svg">
      <div>Medium Hazard</div>
    </section>
    """
    parsed = parse_franklin_page(html, fetched_at=fetched_at)
    assert parsed["flag"] == "Yellow"
    assert parsed["official_updated_at"] is None
    assert parsed["fetched_at"] == fetched_at
    assert parsed["timestamp_basis"] == "fetch_time"


def test_franklin_parser_ignores_legend_outside_current_conditions():
    fetched_at = datetime(2026, 8, 20, 18, 0, tzinfo=EASTERN)
    html = """
    <section>
      <h2>Current Beach Conditions</h2>
      <div>Last updated: Thursday, August 20 at 12:00 PM EDT</div>
      <img alt="Yellow Flag" src="yellow.svg">
      <div>Medium Hazard</div>
      <h2>What the flags mean</h2>
      <div>High Hazard</div>
      <img alt="Red Flag" src="red.svg">
    </section>
    """
    parsed = parse_franklin_page(html, fetched_at=fetched_at)
    assert parsed["flag"] == "Yellow"


def test_freshness_age_is_timezone_safe():
    source = datetime(2026, 8, 18, 12, 0, tzinfo=EASTERN)
    now = datetime(2026, 8, 18, 17, 30, tzinfo=EASTERN)
    assert hours_old(source, now) == 5.5


def test_eastern_unavailable_output_does_not_advance_verification():
    now = datetime(2026, 8, 27, 10, 0, tzinfo=EASTERN)
    previous = {"last_verified_at": "2026-08-27T08:00:00-04:00"}
    verified, checked, status = verification_state(
        previous, now, None, cached=False, nws_flag=None, nws_fresh=False
    )
    assert verified == previous["last_verified_at"]
    assert checked == now.isoformat()
    assert status == "unavailable"


def test_cached_franklin_advances_only_when_fresh_nws_corroborates():
    now = datetime(2026, 8, 27, 10, 0, tzinfo=EASTERN)
    previous = {"last_verified_at": "2026-08-27T08:00:00-04:00"}

    verified, _, status = verification_state(
        previous, now, "Yellow", cached=True, nws_flag="Yellow", nws_fresh=True
    )
    assert verified == now.isoformat()
    assert status == "verified"

    verified, _, status = verification_state(
        previous, now, "Yellow", cached=True, nws_flag="Red", nws_fresh=True
    )
    assert verified == previous["last_verified_at"]
    assert status == "degraded"
