#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

try:
    from .flag_image_verification import fetch_and_classify_flag_image
except ImportError:
    from flag_image_verification import fetch_and_classify_flag_image

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "south-walton" / "current_flag.json"
SOURCE_URL = "https://www.visitsouthwalton.com/beach-safety/"
SOURCE_NAME = "Walton County beach officials / South Walton Fire District"
CENTRAL = ZoneInfo("America/Chicago")
SEVERITY = {"Green": 1, "Yellow": 2, "Single Red": 3, "Double Red": 4}

CURRENT_LABEL = re.compile(r"\bcurrent\s+(?:beach\s+)?conditions?\b", re.I)
STOP_HEADING = re.compile(r"\b(?:beach\s+flag\s+warnings?|flag\s+system|flag\s+meanings?|rules?|rip\s+current)\b", re.I)
LEGEND_TEXT = re.compile(r"\b(?:water\s+closed\s+to\s+public|high\s+hazard|medium\s+hazard|low\s+hazard|stinging\s+marine\s+life)\b", re.I)
COLOR_TOKEN = re.compile(r"(?<![a-z])(double[-_\s]?red|single[-_\s]?red|yellow|green|purple|red)(?![a-z])", re.I)


def _attr_text(tag: Tag) -> str:
    values: list[str] = []
    for key, value in tag.attrs.items():
        if isinstance(value, (list, tuple)):
            value = " ".join(str(v) for v in value)
        values.append(f"{key}={value}")
    return " ".join(values)


def _find_current_anchor(soup: BeautifulSoup) -> Tag | None:
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "div", "p", "span"]):
        text = tag.get_text(" ", strip=True)
        if text and CURRENT_LABEL.fullmatch(re.sub(r"[:\s]+$", "", text)):
            return tag
    return None


def _current_region_elements(soup: BeautifulSoup) -> list[Tag]:
    anchor = _find_current_anchor(soup)
    if anchor is None:
        return []
    elements: list[Tag] = [anchor]
    for node in anchor.next_elements:
        if not isinstance(node, Tag):
            continue
        if node is anchor:
            continue
        if node.name in {"h1", "h2", "h3", "h4", "h5"}:
            heading = node.get_text(" ", strip=True)
            if STOP_HEADING.search(heading):
                break
        elements.append(node)
        if len(elements) >= 120:
            break
    return elements


def extract_semantic_current_state(html: str) -> tuple[str | None, bool, list[str]]:
    """Read only semantic color labels/attributes inside the explicit Current Conditions region."""
    soup = BeautifulSoup(html, "html.parser")
    elements = _current_region_elements(soup)
    primary: str | None = None
    purple = False
    evidence: list[str] = []
    for tag in elements:
        if tag.name in {"script", "style"}:
            continue
        text = tag.get_text(" ", strip=True)
        attrs = _attr_text(tag)
        haystack = f"{attrs} {text}"
        # Do not accept prose definitions as current-state evidence.
        if LEGEND_TEXT.search(text) and not CURRENT_LABEL.search(text):
            continue
        for match in COLOR_TOKEN.finditer(haystack):
            token = re.sub(r"[-_\s]+", " ", match.group(1).lower()).strip()
            if token == "purple":
                purple = True
                evidence.append(f"semantic:{token}")
            elif token == "yellow":
                primary = primary or "Yellow"
                evidence.append(f"semantic:{token}")
            elif token == "green":
                primary = primary or "Green"
                evidence.append(f"semantic:{token}")
            elif token == "double red":
                primary = primary or "Double Red"
                evidence.append("semantic:double red")
            elif token == "single red":
                primary = primary or "Single Red"
                evidence.append("semantic:single red")
            # Bare red is intentionally not publishable because it cannot establish one vs two red flags.
    return primary, purple, list(dict.fromkeys(evidence))


def eligible_current_images(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    elements = _current_region_elements(soup)
    urls: list[str] = []
    for tag in elements:
        if tag.name != "img":
            continue
        src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src")
        if not src:
            continue
        url = urljoin(base_url, src)
        if url not in urls:
            urls.append(url)
    return urls[:4]


def resolve_current_state(html: str, base_url: str, session: requests.Session) -> tuple[str | None, bool, list[dict], str | None]:
    semantic_primary, semantic_purple, semantic_evidence = extract_semantic_current_state(html)
    image_records: list[dict] = []
    image_primary: str | None = None
    image_purple = False
    conflict: str | None = None
    for url in eligible_current_images(html, base_url):
        result, error = fetch_and_classify_flag_image(url, session)
        record: dict = {"url": url}
        if error:
            record["analysis_error"] = error[:300]
        elif result is not None:
            record["visual_analysis"] = result.to_dict()
            if result.publishable and result.primary:
                if image_primary and image_primary != result.primary:
                    conflict = "eligible current-condition images disagree"
                image_primary = image_primary or result.primary
                image_purple = image_purple or result.purple
        image_records.append(record)

    if semantic_primary and image_primary and semantic_primary != image_primary:
        conflict = f"semantic={semantic_primary}; image={image_primary}"
    primary = semantic_primary or image_primary
    purple = semantic_purple or image_purple
    evidence = [{"semantic_evidence": semantic_evidence}, *image_records]
    return primary, purple, evidence, conflict


def refresh() -> None:
    previous: dict = {}
    try:
        previous = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    session = requests.Session()
    session.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    now = datetime.now(CENTRAL).isoformat()
    fetch_error: str | None = None
    primary: str | None = None
    purple = False
    evidence: list[dict] = []
    conflict: str | None = None
    try:
        response = session.get(SOURCE_URL, timeout=(5, 20))
        response.raise_for_status()
        primary, purple, evidence, conflict = resolve_current_state(response.text, response.url, session)
    except requests.RequestException as exc:
        fetch_error = str(exc)

    payload = dict(previous)
    payload.update({
        "location": "South Walton / 30A",
        "flag": primary,
        "primary_flag": primary,
        "purple": purple if primary else False,
        "label": (primary + (" + Purple" if purple else "")) if primary else "Official flag status unavailable",
        "severity": SEVERITY.get(primary),
        "last_checked_at": now,
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "official_authority": SOURCE_NAME,
        "official_authority_url": SOURCE_URL,
        "method": "Direct South Walton Current Conditions visual/semantic evidence; existing NWS and terminology systems remain independent corroborating layers",
        "stale_after_hours": 3 if primary else 0,
        "flag_schema": "Florida Beach Warning Flag terminology v1",
        "flag_terms_note": "Official flag definitions remain authoritative for terminology. South Walton current-state parsing is bounded to the explicit Current Conditions region and stops before Beach Flag Warnings/legend content.",
        "current_flag_image_evidence": evidence,
    })

    if conflict:
        payload["evidence_conflict"] = conflict
    else:
        payload.pop("evidence_conflict", None)

    if primary and not conflict:
        payload["last_verified_at"] = now
        payload["source_check_status"] = "verified"
        payload["provenance_tier"] = "primary_official_current_visual"
        payload["terminology_evidence"] = "bounded-current-conditions-visual"
        payload["terminology_verified_at"] = now
        payload["terminology_verified_url"] = SOURCE_URL
        payload["stale_reason"] = None
        payload.pop("source_error", None)
    else:
        payload["source_check_status"] = "unavailable" if fetch_error else ("conflict" if conflict else "degraded")
        payload["provenance_tier"] = "official_source_evidence_conflict" if conflict else "official_source_no_verified_current_status"
        payload["stale_reason"] = "South Walton official Current Conditions could not be safely resolved from bounded current-state evidence"
        if fetch_error:
            payload["source_error"] = fetch_error
        else:
            payload.pop("source_error", None)
        payload.pop("terminology_evidence", None)
        payload.pop("terminology_verified_at", None)
        payload.pop("terminology_verified_url", None)

    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("south-walton", payload["label"], payload["source_check_status"])


if __name__ == "__main__":
    refresh()
