from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quality_ui_exposes_confidence_states():
    text = (ROOT / "assets" / "quality-ui.js").read_text(encoding="utf-8")
    for state in ("corroborated", "partial_corroboration", "source_disagreement", "visitbeaches_gap_filled"):
        assert state in text
    assert "High confidence" in text
    assert "local authority remains primary" in text


def test_quality_polish_has_mobile_and_touch_targets():
    text = (ROOT / "assets" / "quality-polish.css").read_text(encoding="utf-8")
    assert "min-height:44px" in text
    assert "@media(max-width:520px)" in text
    assert "grid-template-columns:1fr" in text
    assert "prefers-reduced-motion" in text


def test_injector_includes_quality_assets():
    text = (ROOT / "scripts" / "inject_social_meta.py").read_text(encoding="utf-8")
    assert "/assets/quality-ui.js" in text
    assert "/assets/quality-polish.css" in text
