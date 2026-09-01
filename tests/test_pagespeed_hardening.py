from pathlib import Path

from scripts.inject_social_meta import inject_or_replace

ROOT = Path(__file__).resolve().parents[1]


def _luminance(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]

    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_homepage_has_no_blocking_google_font_or_eager_chartjs():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "assets/app.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    assert "fonts.googleapis.com" not in css
    assert "cdn.jsdelivr.net/npm/chart.js" not in html
    assert "font-family:system-ui" in css


def test_active_green_meets_wcag_aa_against_white():
    css = (ROOT / "assets/app.css").read_text(encoding="utf-8")
    assert "--good:#087c3e" in css
    assert _contrast("#087c3e", "#ffffff") >= 4.5


def test_chartjs_is_lazy_loaded_and_transient_fetches_are_retried():
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert "function ensureChartJs()" in js
    assert "cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js" in js
    assert "TRANSIENT_HTTP=new Set([429,502,503,504])" in js
    assert "for(let attempt=0;attempt<3;attempt++)" in js


def test_standardized_deployment_injects_csp_and_referrer_policy():
    source = """<!doctype html><html><head>
    <script type="application/ld+json">{"@context":"https://schema.org"}</script>
    </head><body></body></html>"""
    html = inject_or_replace(source)
    assert 'http-equiv="Content-Security-Policy"' in html
    assert 'name="referrer" content="strict-origin-when-cross-origin"' in html
    csp = html.split('http-equiv="Content-Security-Policy" content="', 1)[1].split('"', 1)[0]
    script_src = csp.split("script-src ", 1)[1].split(";", 1)[0]
    assert "'sha256-" in script_src
    assert "'unsafe-inline'" not in script_src
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
