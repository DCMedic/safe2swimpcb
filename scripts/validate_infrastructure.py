#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "infra" / "policy.json"
CADDY = ROOT / "infra" / "caddy" / "Caddyfile"


def validate() -> list[str]:
    errors: list[str] = []
    if not POLICY.exists():
        return ["infra/policy.json missing"]
    if not CADDY.exists():
        return ["infra/caddy/Caddyfile missing"]

    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    caddy = CADDY.read_text(encoding="utf-8")

    if policy.get("canonical_host") != "knowthegulf.com":
        errors.append("canonical_host must remain knowthegulf.com")

    headers = policy.get("security_headers", {})
    required = {
        "Strict-Transport-Security",
        "Cross-Origin-Opener-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    }
    missing = sorted(required - set(headers))
    if missing:
        errors.append("missing required security headers: " + ", ".join(missing))

    csp = str(headers.get("Content-Security-Policy", ""))
    for directive in ("frame-ancestors 'none'", "object-src 'none'", "base-uri 'self'"):
        if directive not in csp:
            errors.append(f"CSP missing {directive}")

    if policy.get("trusted_types", {}).get("enabled") is not False:
        errors.append("Trusted Types must remain disabled until DOM sinks are migrated")

    cache = policy.get("cache_policy", {})
    for key in ("current_condition_json", "health_state_json"):
        value = str(cache.get(key, ""))
        if "no-store" not in value:
            errors.append(f"{key} must remain no-store")

    for header, value in headers.items():
        if header not in caddy or value not in caddy:
            errors.append(f"Caddyfile does not implement policy header {header}")

    if "current_flag\\.json" not in caddy or "no-store, max-age=0, must-revalidate" not in caddy:
        errors.append("Caddyfile does not explicitly protect live flag JSON from caching")

    if "redir https://knowthegulf.com{uri} permanent" not in caddy:
        errors.append("www canonical redirect missing")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("INFRASTRUCTURE POLICY VALIDATION FAILED")
        for error in errors:
            print(f" - {error}")
        return 1
    print("infrastructure policy validation ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
