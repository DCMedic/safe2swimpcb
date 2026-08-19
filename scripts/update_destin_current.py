#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

try:
    from .common import session, now_local
except ImportError:
    from common import session, now_local

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "destin" / "current_flag.json"
URL = "https://www.destinfire.gov/today-s-warning-condition-beach-flags"
AUTHORITY = "Destin Fire Control District / Destin Beach Safety"
SEVERITY = {"Green": 1, "Yellow": 2, "Single Red": 3, "Double Red": 4}


def parse_destin_flag(html: str) -> str:
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)
    m = re.search(r"Current Status:\s*(Water Closed to Public|High Hazard|Medium Hazard|Low Hazard)", text, re.I)
    if not m:
        raise RuntimeError("Destin current status not found in official page")
    return {
        "water closed to public": "Double Red",
        "high hazard": "Single Red",
        "medium hazard": "Yellow",
        "low hazard": "Green",
    }[m.group(1).lower()]


def main() -> None:
    r = session().get(URL, timeout=30)
    r.raise_for_status()
    flag = parse_destin_flag(r.text)
    now = now_local()
    previous = {}
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    changed = previous.get("flag") not in (None, flag)
    payload = {
        "flag": flag,
        "label": flag,
        "severity": SEVERITY[flag],
        "last_verified_at": now.isoformat(),
        "status_changed_at": now.isoformat() if changed or not previous.get("status_changed_at") else previous.get("status_changed_at"),
        "source_name": AUTHORITY,
        "source_url": URL,
        "method": "Hourly public current-condition snapshot with retry-enabled HTTP client",
        "stale_after_hours": 3,
        "note": "Current Destin status is refreshed independently from the heavier western historical-data workflow. Posted flags and Destin Beach Safety control.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(flag, now.isoformat(), "changed=", changed)


if __name__ == "__main__":
    main()
