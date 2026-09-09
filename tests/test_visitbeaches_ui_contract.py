from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_shared_ui_renders_visitbeaches_observations_without_replacing_flag_status():
    text = (ROOT / "assets/site-ui.js").read_text(encoding="utf-8")
    assert "VISITBEACHES_SLUGS" in text
    assert "/data/visitbeaches/${slug}.json" in text
    assert "Beach Ambassador Observation" in text
    assert "do not replace posted flags or lifeguard instructions" in text
    assert "Mote Marine Laboratory" in text
    assert "Source comparison:" in text


def test_shared_ui_surfaces_high_value_ambassador_fields():
    text = (ROOT / "assets/site-ui.js").read_text(encoding="utf-8")
    for label in (
        "Water temperature",
        "Surf height",
        "Rip currents",
        "Wind",
        "Tides",
        "Water color",
        "Jellyfish",
        "Respiratory irritation",
        "Dead fish",
        "Crowds",
        "Drift algae",
        "Beach debris",
    ):
        assert label in text


def test_shared_ui_prefers_fresh_observation_but_can_show_last_known():
    text = (ROOT / "assets/site-ui.js").read_text(encoding="utf-8")
    assert "x&&x.fresh&&observationMetrics(x).length" in text
    assert "Last Beach Ambassador observation" in text
