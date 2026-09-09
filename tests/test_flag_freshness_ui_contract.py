from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_asset(name: str) -> str:
    return (ROOT / "assets" / name).read_text(encoding="utf-8")


def test_global_ui_labels_stale_flags_as_last_verified():
    text = read_asset("site-ui.js")
    assert "Last verified flag:" in text
    assert "flagFreshness" in text
    assert "stale?`Last verified flag:" in text
    assert "${stale?'Last verified':'Current'} beach flag" in text


def test_eastern_ui_preserves_stale_flag_with_clear_label():
    text = read_asset("eastern-location.js")
    assert "Last verified flag:" in text
    assert "This is the last verified flag, not a claim that the flag is still current" in text
    assert "relatedCard" in text


def test_southwest_ui_preserves_stale_flag_with_clear_label():
    text = read_asset("southwest-location.js")
    assert "Last verified flag:" in text
    assert "this is the last verified flag, not a current-status claim" in text
    assert "verify the latest condition" in text
