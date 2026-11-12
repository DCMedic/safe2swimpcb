from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_quality_ui_does_not_independently_fetch_or_assert_confidence():
    text = (ROOT / "assets" / "quality-ui.js").read_text(encoding="utf-8")
    assert "fetch(" not in text
    assert "High confidence" not in text
    state = (ROOT / "assets" / "safety-state.js").read_text()
    for value in ("corroborated", "partial_corroboration", "source_disagreement"):
        assert value in state


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
