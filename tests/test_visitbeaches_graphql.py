from datetime import datetime, timezone

from scripts.visitbeaches_graphql import collect_location, normalize_report


def test_flag_and_purple_normalization():
    report = {
        "id": "r1",
        "createdAt": "2026-09-09T14:00:00Z",
        "user": {"id": "u1", "name": "Ambassador"},
        "beachReport": {
            "parameterCategory": {"name": "Conditions", "slug": "conditions"},
            "reportParameters": [
                {
                    "parameter": {"id": "p1", "name": "Beach Flag", "parameterCategory": {"name": "Conditions", "slug": "conditions"}},
                    "parameterValues": [{"id": "v1", "name": "Yellow Flag", "value": "yellow"}],
                    "value": None,
                },
                {
                    "parameter": {"id": "p2", "name": "Dangerous Marine Life", "parameterCategory": {"name": "Conditions", "slug": "conditions"}},
                    "parameterValues": [{"id": "v2", "name": "Purple Flag", "value": "true"}],
                    "value": None,
                },
                {
                    "parameter": {"id": "p3", "name": "Water Temperature", "unit": "F", "parameterCategory": {"name": "Water", "slug": "water"}},
                    "parameterValues": [],
                    "value": 86,
                },
            ],
        },
    }
    result = normalize_report(report)
    assert result["flag"] == "Yellow"
    assert result["purple"] is True
    assert result["normalized_conditions"]["water_temperature"]["value"] == 86


def test_non_flag_color_does_not_become_flag():
    report = {
        "id": "r2",
        "createdAt": "2026-09-09T14:00:00Z",
        "beachReport": {
            "parameterCategory": {"name": "Water", "slug": "water"},
            "reportParameters": [
                {
                    "parameter": {"name": "Water Color", "parameterCategory": {"name": "Water", "slug": "water"}},
                    "parameterValues": [{"name": "Green", "value": "green"}],
                    "value": None,
                }
            ],
        },
    }
    result = normalize_report(report)
    assert result["flag"] is None


class FakeClient:
    def search_beaches(self, search):
        return [{"id": search, "name": search, "location": search, "latitude": 1, "longitude": 2}]

    def beach(self, beach_id):
        flag = "Yellow Flag" if beach_id == "Beach A" else "Red Flag"
        return {
            "id": beach_id,
            "name": beach_id,
            "location": beach_id,
            "latitude": 1,
            "longitude": 2,
            "lastThreeDaysOfReports": [{
                "id": f"r-{beach_id}",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "user": {"id": "u", "name": "Ambassador"},
                "beachReport": {
                    "parameterCategory": {"name": "Conditions", "slug": "conditions"},
                    "reportParameters": [{
                        "parameter": {"name": "Beach Flag", "parameterCategory": {"name": "Conditions", "slug": "conditions"}},
                        "parameterValues": [{"name": flag, "value": flag.lower()}],
                        "value": None,
                    }],
                },
            }],
        }


def test_conflicting_fresh_ambassador_flags_do_not_emit_regional_flag():
    result = collect_location(["Beach A", "Beach B"], client=FakeClient())
    assert result["flag"] is None
    assert result["flag_conflict"] is True
    assert result["fresh_distinct_flags"] == ["Red", "Yellow"]
