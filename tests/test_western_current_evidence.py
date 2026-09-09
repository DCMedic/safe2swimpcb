from scripts.refresh_western_current_flags import parse_explicit_current_status


def test_definition_legend_is_not_current_status():
    html = """
    <html><body>
      <h2>Beach Warning Flag System</h2>
      <p>Green Flag - Low Hazard</p>
      <p>Yellow Flag - Medium Hazard</p>
      <p>Red Flag - High Hazard</p>
      <p>Double Red Flag - Water Closed to Public</p>
    </body></html>
    """
    flag, evidence = parse_explicit_current_status(html)
    assert flag is None
    assert evidence is None


def test_explicit_current_status_is_accepted():
    html = """
    <html><body>
      <h1>Today's Warning Condition: Beach Flags</h1>
      <h2>Current Status: Water Closed to Public</h2>
      <p>Beach Warning Flag System</p>
      <p>Yellow Flag - Medium Hazard</p>
    </body></html>
    """
    flag, evidence = parse_explicit_current_status(html)
    assert flag == "Double Red"
    assert "Current Status" in evidence


def test_current_status_wins_despite_other_legend_terms():
    html = """
    <html><body>
      <div>Current Flag: Medium Hazard</div>
      <section>
        <p>High Hazard means high surf and strong currents.</p>
        <p>Water Closed to Public means do not enter the water.</p>
      </section>
    </body></html>
    """
    flag, _ = parse_explicit_current_status(html)
    assert flag == "Yellow"
