#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from .collector_resilience import fresh_cached_payload, mark_cached_official, retry_call
    from .common import session, now_local
except ImportError:
    from collector_resilience import fresh_cached_payload, mark_cached_official, retry_call
    from common import session, now_local

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "destin" / "current_flag.json"
URL = "https://www.destinfire.gov/today-s-warning-condition-beach-flags"
AUTHORITY = "Destin Fire Control District / Destin Beach Safety"
SEVERITY = {"Green": 1, "Yellow": 2, "Single Red": 3, "Double Red": 4}
CACHE_HOURS = 3


def parse_destin_flag(html: str) -> str:
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)
    match = re.search(
        r"Current Status\s*:?\s*(Water Closed(?: to Public)?|High Hazard|Medium Hazard|Moderate Hazard|Low Hazard)",
        text,
        re.I,
    )
    if not match:
        raise RuntimeError("Destin current status not found in official page")
    return {
        "water closed": "Double Red",
        "water closed to public": "Double Red",
        "high hazard": "Single Red",
        "medium hazard": "Yellow",
        "moderate hazard": "Yellow",
        "low hazard": "Green",
    }[match.group(1).lower()]


def load_previous() -> dict:
    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def fetch_live_flag() -> str:
    def operation() -> str:
        response = session().get(URL, timeout=(5, 20))
        response.raise_for_status()
        return parse_destin_flag(response.text)

    return retry_call(
        operation,
        attempts=3,
        base_delay_seconds=1,
        retry_exceptions=(requests.RequestException, RuntimeError),
        on_error=lambda attempt, exc: print(f"Destin source attempt {attempt} failed: {type(exc).__name__}: {exc}"),
    )


def degraded_payload(now, previous: dict, exc: BaseException) -> dict:
    cached, age = fresh_cached_payload(OUT, now, max_age_hours=CACHE_HOURS)
    if cached:
        payload = mark_cached_official(
            cached,
            now,
            exc,
            method="Cached last-known official Destin flag after bounded live-source retries failed",
        )
        payload["cache_age_hours"] = round(age, 2) if age is not None else None
        return payload

    return {
        "flag": None,
        "label": "Official flag status unavailable",
        "severity": None,
        "provenance_tier": "unavailable",
        "last_verified_at": previous.get("last_verified_at"),
        "last_checked_at": now.isoformat(),
        "status_changed_at": previous.get("status_changed_at"),
        "source_name": AUTHORITY,
        "source_url": URL,
        "source_check_status": "unavailable",
        "source_error": str(exc)[:500],
        "method": "No current authoritative Destin flag could be verified after bounded retries",
        "stale_after_hours": 0,
        "stale_reason": "The previous official observation exceeded its freshness window and the live source could not be verified.",
        "note": "A failed source check never advances last_verified_at. Posted flags and Destin Beach Safety instructions control.",
    }


def main() -> None:
    now = now_local()
    previous = load_previous()
    try:
        flag = fetch_live_flag()
    except (requests.RequestException, RuntimeError) as exc:
        payload = degraded_payload(now, previous, exc)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print("Destin live verification degraded", payload.get("label"), payload.get("source_check_status"))
        return

    changed = previous.get("flag") not in (None, flag)
    payload = {
        "flag": flag,
        "label": flag,
        "severity": SEVERITY[flag],
        "provenance_tier": "primary_official",
        "cached": False,
        "last_verified_at": now.isoformat(),
        "last_checked_at": now.isoformat(),
        "status_changed_at": now.isoformat() if changed or not previous.get("status_changed_at") else previous.get("status_changed_at"),
        "source_name": AUTHORITY,
        "source_url": URL,
        "source_check_status": "verified",
        "method": "Hourly public current-condition snapshot with bounded fetch-and-parse retries",
        "stale_after_hours": CACHE_HOURS,
        "stale_reason": None,
        "note": "Current Destin status is refreshed independently from the heavier western historical-data workflow. Posted flags and Destin Beach Safety control.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(flag, now.isoformat(), "changed=", changed)


if __name__ == "__main__":
    main()
