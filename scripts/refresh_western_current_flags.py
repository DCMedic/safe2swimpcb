#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CENTRAL = ZoneInfo("America/Chicago")

LOCATIONS = {
    "okaloosa-island": {
        "source_name": "Okaloosa County Beach Safety",
        "source_url": "https://www.myokaloosa.com/ps/beach-safety",
    },
    "navarre-beach": {
        "source_name": "Santa Rosa County / Navarre Beach Safety",
        "source_url": "https://santarosa.fl.gov/269/Water-Safety",
    },
    "pensacola-beach": {
        "source_name": "Escambia County / Pensacola Beach Lifeguards",
        "source_url": "https://myescambia.com/pensacola-beach/pensacola-beach-lifeguards",
    },
}

HAZARD_TO_FLAG = {
    "low hazard": "Green",
    "calm conditions": "Green",
    "medium hazard": "Yellow",
    "moderate hazard": "Yellow",
    "moderate surf and/or currents": "Yellow",
    "high hazard": "Single Red",
    "high surf and/or strong currents": "Single Red",
    "water closed": "Double Red",
    "water closed to public": "Double Red",
}
SEVERITY = {"Green": 1, "Yellow": 2, "Single Red": 3, "Double Red": 4}

# A definition/legend remains authoritative for terminology, but it is not evidence
# that a particular flag is currently posted. Current-state extraction therefore
# requires an explicit current/today/posted-status label immediately associated
# with a recognized condition term.
CURRENT_STATUS = re.compile(
    r"\b(?:current\s+(?:status|condition(?:s)?|warning\s+condition|flag(?:s)?|beach\s+flag(?:s)?)|"
    r"today(?:'s)?\s+(?:status|condition(?:s)?|warning\s+condition|flag(?:s)?)|"
    r"posted\s+(?:status|condition|flag(?:s)?))\b\s*(?:is|are|:|-)?\s*"
    r"(water\s+closed(?:\s+to\s+(?:the\s+)?public)?|high\s+hazard|medium\s+hazard|"
    r"moderate\s+hazard|low\s+hazard|calm\s+conditions|moderate\s+surf\s+and/or\s+currents|"
    r"high\s+surf\s+and/or\s+strong\s+currents)",
    re.I,
)


def normalize_condition(value: str) -> str | None:
    key = re.sub(r"\s+", " ", value.strip().lower())
    key = key.replace("water closed to the public", "water closed to public")
    return HAZARD_TO_FLAG.get(key)


def parse_explicit_current_status(html: str) -> tuple[str | None, str | None]:
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)
    match = CURRENT_STATUS.search(text)
    if not match:
        return None, None
    flag = normalize_condition(match.group(1))
    return flag, match.group(0) if flag else (None, None)


def fetch_explicit_current_status(url: str) -> tuple[str | None, str | None, str | None]:
    session = requests.Session()
    session.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    try:
        response = session.get(url, timeout=25)
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, None, str(exc)
    flag, evidence = parse_explicit_current_status(response.text)
    return flag, evidence, None


def refresh_slug(slug: str, cfg: dict[str, str]) -> None:
    path = ROOT / "data" / slug / "current_flag.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            previous = {}
    except (FileNotFoundError, json.JSONDecodeError):
        previous = {}

    now = datetime.now(CENTRAL).isoformat()
    flag, evidence, fetch_error = fetch_explicit_current_status(cfg["source_url"])

    payload = dict(previous)
    payload.update(
        {
            "flag": flag,
            "primary_flag": flag,
            "purple": False,
            "label": flag if flag else "Official flag status unavailable",
            "severity": SEVERITY.get(flag),
            "last_checked_at": now,
            "source_name": cfg["source_name"],
            "source_url": cfg["source_url"],
            "official_authority": cfg["source_name"],
            "official_authority_url": cfg["source_url"],
            "method": "Direct official source; current flag accepted only when explicitly labeled as current/today/posted status",
            "stale_after_hours": 3 if flag else 0,
            "flag_schema": "Florida Beach Warning Flag terminology v1",
            "flag_terms_note": (
                "Official flag-definition text is authoritative for terminology normalization. "
                "A current displayed flag is published only when the official source separately provides explicit current-status evidence."
            ),
        }
    )

    if flag:
        payload["last_verified_at"] = now
        payload["source_check_status"] = "verified"
        payload["provenance_tier"] = "primary_official_current_status"
        payload["terminology_evidence"] = evidence
        payload["terminology_verified_at"] = now
        payload["terminology_verified_url"] = cfg["source_url"]
        payload.pop("source_error", None)
        payload.pop("stale_reason", None)
    else:
        # Do not preserve a previously displayed color when current evidence is
        # absent. For safety-critical flags, unknown is preferable to a false flag.
        payload["source_check_status"] = "unavailable" if fetch_error else "degraded"
        payload["provenance_tier"] = "official_source_no_explicit_current_status"
        payload["stale_reason"] = (
            "Official source was unreachable" if fetch_error else
            "Official source is reachable but does not expose an explicit current flag/status in parseable page text"
        )
        if fetch_error:
            payload["source_error"] = fetch_error
        else:
            payload.pop("source_error", None)
        payload.pop("terminology_evidence", None)
        payload.pop("terminology_verified_at", None)
        payload.pop("terminology_verified_url", None)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(slug, payload["label"], payload["source_check_status"])


def main() -> None:
    for slug, cfg in LOCATIONS.items():
        refresh_slug(slug, cfg)


if __name__ == "__main__":
    main()
