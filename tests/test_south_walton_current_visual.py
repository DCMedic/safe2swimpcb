from scripts.refresh_south_walton_current_flag import (
    eligible_current_images,
    extract_semantic_current_state,
)


def test_south_walton_current_region_reads_yellow_and_purple():
    html = """
    <html><body>
      <h1>Safely Enjoy South Walton's Beaches</h1>
      <div>Current Conditions:</div>
      <div class="current-flags">
        <span class="flag yellow" aria-label="Yellow flag"></span>
        <span class="flag purple" aria-label="Purple flag"></span>
      </div>
      <h3>Beach Flag Warnings</h3>
      <p>Entering the Gulf during double red flag conditions can result in a fine.</p>
    </body></html>
    """
    primary, purple, evidence = extract_semantic_current_state(html)
    assert primary == "Yellow"
    assert purple is True
    assert "semantic:yellow" in evidence
    assert "semantic:purple" in evidence


def test_south_walton_legend_double_red_does_not_override_current_yellow():
    html = """
    <html><body>
      <div>Current Conditions:</div>
      <div class="flag-yellow"></div>
      <h3>Beach Flag Warnings</h3>
      <img src="/legend.png" alt="Double Red Yellow Green Purple beach flag warnings">
      <p>Water Closed to Public</p>
    </body></html>
    """
    primary, purple, _ = extract_semantic_current_state(html)
    assert primary == "Yellow"
    assert purple is False


def test_current_images_stop_before_beach_flag_warnings():
    html = """
    <html><body>
      <div>Current Conditions:</div>
      <img src="/today.png" alt="Current beach flags">
      <h3>Beach Flag Warnings</h3>
      <img src="/legend.png" alt="Beach flag warning system">
    </body></html>
    """
    images = eligible_current_images(html, "https://www.visitsouthwalton.com/beach-safety/")
    assert images == ["https://www.visitsouthwalton.com/today.png"]


def test_bare_red_semantic_token_is_not_publishable():
    html = """
    <html><body>
      <div>Current Conditions:</div>
      <div class="flag red"></div>
      <h3>Beach Flag Warnings</h3>
    </body></html>
    """
    primary, purple, _ = extract_semantic_current_state(html)
    assert primary is None
    assert purple is False
