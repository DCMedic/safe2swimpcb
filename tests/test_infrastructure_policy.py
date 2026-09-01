from pathlib import Path

from scripts.validate_infrastructure import validate

ROOT = Path(__file__).resolve().parents[1]


def test_infrastructure_policy_is_self_consistent():
    assert validate() == []


def test_live_safety_json_is_never_long_cached():
    caddy = (ROOT / "infra/caddy/Caddyfile").read_text(encoding="utf-8")
    assert "current_flag\\.json" in caddy
    assert 'Cache-Control "no-store, max-age=0, must-revalidate"' in caddy


def test_http_security_layer_has_clickjacking_and_hsts_controls():
    caddy = (ROOT / "infra/caddy/Caddyfile").read_text(encoding="utf-8")
    assert 'Strict-Transport-Security "max-age=31536000; includeSubDomains"' in caddy
    assert 'X-Frame-Options "DENY"' in caddy
    assert "frame-ancestors 'none'" in caddy
    assert 'Cross-Origin-Opener-Policy "same-origin"' in caddy


def test_trusted_types_is_not_enabled_prematurely():
    policy = (ROOT / "infra/policy.json").read_text(encoding="utf-8")
    assert '"enabled": false' in policy
