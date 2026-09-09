#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
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

CURRENT_CONTEXT = re.compile(
    r"\b(?:current|today(?:'s)?|posted|now|daily)\b.{0,80}\b(?:flag|status|condition|warning)\b|"
    r"\b(?:flag|status|condition|warning)\b.{0,80}\b(?:current|today(?:'s)?|posted|now|daily)\b",
    re.I,
)
LEGEND_CONTEXT = re.compile(
    r"\b(?:what\s+(?:each\s+)?flag\s+means?|flag\s+meanings?|warning\s+flag\s+system|flag\s+system|"
    r"legend|key|guide|learn|education|safety\s+tips?)\b",
    re.I,
)
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


def image_context(img) -> str:
    pieces = [img.get("alt", ""), img.get("title", ""), img.get("aria-label", "")]
    parent = img.parent
    depth = 0
    while parent is not None and depth < 3:
        pieces.append(parent.get_text(" ", strip=True))
        heading = parent.find_previous(["h1", "h2", "h3", "h4"])
        if heading:
            pieces.append(heading.get_text(" ", strip=True))
        parent = parent.parent
        depth += 1
    return re.sub(r"\s+", " ", " ".join(p for p in pieces if p)).strip()


def eligible_current_flag_images(html: str, base_url: str) -> list[dict[str, str]]:
    """Return only images whose local DOM context explicitly describes current conditions.

    Educational flag charts, legends, galleries, and generic safety graphics are rejected
    even when their pixels contain valid Florida warning-flag colors.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict[str, str]] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        context = image_context(img)
        if not CURRENT_CONTEXT.search(context):
            continue
        if LEGEND_CONTEXT.search(context):
            continue
        candidates.append({
            "url": urljoin(base_url, src),
            "context": context[:500],
            "alt": str(img.get("alt") or ""),
        })
    return candidates


def fetch_explicit_current_status(url: str) -> tuple[str | None, str | None, str | None, list[dict[str, str]]]:
    session = requests.Session()
    session.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    try:
        response = session.get(url, timeout=25)
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, None, str(exc), []
    flag, evidence = parse_explicit_current_status(response.text)
    images = eligible_current_flag_images(response.text, response.url)
    return flag, evidence, None, images


def refresh_slug(slug: str, cfg: dict[str, str]) -> None:
    path = ROOT / "data" / slug / "current_flag.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            previous = {}
    except (FileNotFoundError, json.JSONDecodeError):
        previous = {}

    now = datetime.now(CENTRAL).isoformat()
    flag, evidence, fetch_error, image_candidates = fetch_explicit_current_status(cfg["source_url"])

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
            "method": "Direct official source; current flag accepted only from explicit current-status evidence",
            "stale_after_hours": 3 if flag else 0,
            "flag_schema": "Florida Beach Warning Flag terminology v1",
            "flag_terms_note": (
                "Official flag-definition text is authoritative for terminology normalization. "
                "Current-status image candidates are considered only when their local page context explicitly identifies current/today/posted conditions; legends and educational charts are excluded before image analysis."
            ),
            "current_flag_image_candidates": image_candidates,
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
        payload["source_check_status"] = "unavailable" if fetch_error else "degraded"
        payload["provenance_tier"] = "official_source_no_explicit_current_status"
        payload["stale_reason"] = (
            "Official source was unreachable" if fetch_error else
            "Official source is reachable but does not expose explicit current status in parseable text; eligible image candidates are recorded but do not yet publish a color without validated image classification"
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
    print(slug, payload["label"], payload["source_check_status"], f"image_candidates={len(image_candidates)}")


def main() -> None:
    for slug, cfg in LOCATIONS.items():
        refresh_slug(slug, cfg)


if __name__ == "__main__":
    main()
