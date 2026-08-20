from datetime import datetime

from scripts.update_eastern_panhandle import (
    EASTERN,
    hours_old,
    normalize_flag,
    parse_franklin_page,
    parse_franklin_updated,
    parse_nws_flag_table,
    parse_nws_issued,
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
    updated = parse_franklin_updated("Tuesday, August 18 at 12:00 PM EDT")
    assert updated is not None
    assert updated.month == 8
    assert updated.day == 18
    assert updated.hour == 12
    assert updated.tzinfo == EASTERN


def test_parse_franklin_live_condition_page():
    html = """
    <h2>Current Beach Conditions</h2>
    <div>Last updated: Thursday, August 20 at 10:00 AM EDT</div>
    <img alt="Yellow Flag" src="flag.svg">
    <div>Medium Hazard</div>
    """
    parsed = parse_franklin_page(html)
    assert parsed["flag"] == "Yellow"
    assert parsed["official_updated_text"] == "Thursday, August 20 at 10:00 AM EDT"
    assert parsed["official_updated_at"] is not None


def test_freshness_age_is_timezone_safe():
    source = datetime(2026, 8, 18, 12, 0, tzinfo=EASTERN)
    now = datetime(2026, 8, 18, 17, 30, tzinfo=EASTERN)
    assert hours_old(source, now) == 5.5
