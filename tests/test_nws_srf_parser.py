from scripts.backfill_nws_srf import parse_product

SAMPLE = """
FZUS52 KTAE 251627
SRFTAE

Surf Zone Forecast
National Weather Service Tallahassee FL
1127 AM EST Thu Jan 25 2024

Based on communication with area beach officials, the following flags
are flying at area beaches:

Walton........................Red
Bay...........................Red
State Park Gulf Beaches.......Double Red
West Facing Gulf Beaches......Not Available
South Facing Gulf Beaches.....Not Available
Franklin......................Red

FLZ112-260900-
Coastal Bay-
Including the beaches of Panama City Beach and Magnolia Beach
1027 AM CST Thu Jan 25 2024

.REST OF TODAY...
Rip Current Risk............High.
Surf Height.................Around 4 feet.
UV Index**..................High.
Water Temperature...........56 degrees.
Weather.....................Mostly cloudy.
High Temperature............In the upper 60s.
Winds.......................Southeast winds around 15 mph.
Tides...
None.
Sunrise.....................7:37 AM.
Sunset......................6:08 PM.

.FRIDAY...
Rip Current Risk............High.
Surf Height.................Around 3 feet.

&&
$$
"""


def test_parse_explicit_bay_and_state_flags():
    row = parse_product("202401251627-KTAE-FZUS52-SRFTAE.txt", SAMPLE)
    assert row is not None
    assert row["bay_flag"] == "Single Red"
    assert row["bay_purple_overlay"] is False
    assert row["state_park_flag"] == "Double Red"
    assert row["state_park_purple_overlay"] is False
    assert row["rip_current_risk"] == "High"
    assert row["rip_current_risk_score"] == 3
    assert row["surf_height_min_ft"] == 4
    assert row["surf_height_max_ft"] == 4
    assert row["water_temperature_f"] == 56
    assert row["wind_speed_max_mph"] == 15


def test_parse_purple_overlay_independently_from_base_flag():
    purple = SAMPLE.replace("Bay...........................Red", "Bay...........................Yellow and Purple")
    row = parse_product("202401251627-KTAE-FZUS52-SRFTAE.txt", purple)
    assert row["bay_flag"] == "Yellow"
    assert row["bay_purple_overlay"] is True


def test_local_date_and_source_product_id():
    row = parse_product("202401251627-KTAE-FZUS52-SRFTAE.txt", SAMPLE)
    assert row["date"] == "2024-01-25"
    assert row["source_product_id"].endswith("SRFTAE")
