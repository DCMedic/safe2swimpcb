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

try:
    from .flag_image_verification import fetch_and_classify_flag_image
except ImportError:
    from flag_image_verification import fetch_and_classify_flag_image

ROOT = Path(__file__).resolve().parents[1]
CENTRAL = ZoneInfo("America/Chicago")

LOCATIONS = {
    "okaloosa-island": {
        "source_name": "Okaloosa County Beach Safety",
        "source_url": "https://www.myokaloosa.com/ps/beach-safety",
    },
    "navarre-beach": {
        "source_name": "Santa Rosa County / Navarre Beach Safety",
        # Santa Rosa publishes the live Navarre surf-condition banner in the
        # county-wide page chrome/homepage. The older Water Safety page is an
        # educational page and is not the live-condition source.
        "source_url": "https://www.santarosa.fl.gov/",
        "official_url": "https://www.santarosa.fl.gov/318/Navarre-Beach-Pavilions",
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
    r"\b(?:current\s+(?:status|condition(?:s)?|surf\s+condition(?:s)?|warning\s+condition|flag(?:s)?|beach\s+flag(?:s)?)|"
    r"today(?:'s)?\s+(?:status|condition(?:s)?|surf\s+condition(?:s)?|warning\s+condition|flag(?:s)?)|"
    r"posted\s+(?:status|condition|flag(?:s)?))\b\s*(?:is|are|:|-)?\s*"
    r"(water\s+closed(?:\s+to\s+(?:the\s+)?public)?|high\s+hazard|medium\s+hazard|"
    r"moderate\s+hazard|low\s+hazard|calm\s+conditions|moderate\s+surf\s+and/or\s+currents|"
    r"high\s+surf\s+and/or\s+strong\s+currents)",
    re.I,
)
DANGEROUS_MARINE_LIFE = re.compile(r"\bdangerous\s+marine\s+life\b|\bpurple\s+flag\b", re.I)


def normalize_condition(value: str) -> str | None:
    key = re.sub(r"\s+", " ", value.strip().lower())
    key = key.replace("water closed to the public", "water closed to public")
    return HAZARD_TO_FLAG.get(key)


def parse_explicit_current_status(html: str) -> tuple[str | None, str | None, bool]:
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)
    match = CURRENT_STATUS.search(text)
    if not match:
        return None, None, False
    flag = normalize_condition(match.group(1))
    if not flag:
        return None, None, False
    # Purple is additive only when it appears immediately with the explicit
    # current-condition block, not elsewhere in a legend or education section.
    nearby = text[match.start(): min(len(text), match.end() + 120)]
    purple = bool(DANGEROUS_MARINE_LIFE.search(nearby))
    return flag, match.group(0), purple


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
    """Return images only when local DOM context explicitly identifies current conditions."""
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


def analyze_image_candidates(candidates: list[dict[str, str]], session: requests.Session) -> tuple[str | None, bool, list[dict], str | None]:
    results: list[dict] = []
    publishable: list[tuple[str, bool, float, str]] = []
    for candidate in candidates[:4]:
        result, error = fetch_and_classify_flag_image(candidate["url"], session)
        record = dict(candidate)
        if error:
            record["analysis_error"] = error[:300]
            results.append(record)
            continue
        if result is None:
            results.append(record)
            continue
        record["visual_analysis"] = result.to_dict()
        results.append(record)
        if result.publishable and result.primary:
            publishable.append((result.primary, result.purple, result.confidence, candidate["url"]))

    if not publishable:
        return None, False, results, None
    primaries = {item[0] for item in publishable}
    if len(primaries) != 1:
        return None, False, results, "eligible current-status images disagree on primary flag color"
    best = max(publishable, key=lambda item: item[2])
    purple = any(item[1] for item in publishable)
    return best[0], purple, results, None


def fetch_current_evidence(url: str) -> tuple[str | None, str | None, str | None, list[dict], str | None, bool]:
    session = requests.Session()
    session.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    try:
        response = session.get(url, timeout=25)
        response.raise_for_status()
    except requests.RequestException as exc:
        return None, None, str(exc), [], None, False

    text_flag, evidence, text_purple = parse_explicit_current_status(response.text)
    candidates = eligible_current_flag_images(response.text, response.url)
    image_flag, image_purple, analyzed, image_conflict = analyze_image_candidates(candidates, session)

    # Existing text evidence remains primary. Images are corroboration when they agree,
    # or a fallback only when no stronger current-status evidence exists.
    if text_flag:
        if image_flag and image_flag != text_flag:
            return text_flag, evidence, None, analyzed, f"text={text_flag}; image={image_flag}", text_purple
        return text_flag, evidence, None, analyzed, image_conflict, (text_purple or image_purple)
    if image_conflict:
        return None, None, None, analyzed, image_conflict, False
    if image_flag:
        return image_flag, "high-confidence eligible current-status image", None, analyzed, None, image_purple
    return None, None, None, analyzed, None, False


def refresh_slug(slug: str, cfg: dict[str, str]) -> None:
    path = ROOT / "data" / slug / "current_flag.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(previous, dict):
            previous = {}
    except (FileNotFoundError, json.JSONDecodeError):
        previous = {}

    now = datetime.now(CENTRAL).isoformat()
    flag, evidence, fetch_error, image_results, conflict, image_purple = fetch_current_evidence(cfg["source_url"])

    payload = dict(previous)
    official_url = cfg.get("official_url", cfg["source_url"])
    payload.update({
        "flag": flag,
        "primary_flag": flag,
        "purple": image_purple if flag else False,
        "label": (flag + (" + Purple" if image_purple else "")) if flag else "Official flag status unavailable",
        "severity": SEVERITY.get(flag),
        "last_checked_at": now,
        "source_name": cfg["source_name"],
        "source_url": cfg["source_url"],
        "official_authority": cfg["source_name"],
        "official_authority_url": official_url,
        "method": "Official current-status text/structured evidence first; guarded current-status image verification is additive fallback/corroboration only",
        "stale_after_hours": 24 if slug == "navarre-beach" and flag else (3 if flag else 0),
        "flag_schema": "Florida Beach Warning Flag terminology v1",
        "flag_terms_note": (
            "Official flag-definition text remains authoritative for terminology normalization. "
            "Image verification is additive only: candidates must be inside explicit current/today/posted-condition context, legend/education images are excluded, and pixels never override stronger text evidence."
        ),
        "current_flag_image_evidence": image_results,
    })

    if conflict:
        payload["evidence_conflict"] = conflict
    else:
        payload.pop("evidence_conflict", None)

    if flag:
        payload["last_verified_at"] = now
        payload["source_check_status"] = "verified_with_conflict" if conflict else "verified"
        payload["provenance_tier"] = "primary_official_current_status" if evidence != "high-confidence eligible current-status image" else "primary_official_current_image"
        payload["terminology_evidence"] = evidence
        payload["terminology_verified_at"] = now
        payload["terminology_verified_url"] = cfg["source_url"]
        payload.pop("source_error", None)
        payload.pop("stale_reason", None)
    else:
        payload["source_check_status"] = "unavailable" if fetch_error else ("conflict" if conflict else "degraded")
        payload["provenance_tier"] = "official_source_evidence_conflict" if conflict else "official_source_no_verified_current_status"
        payload["stale_reason"] = (
            "Official source was unreachable" if fetch_error else
            "Official source is reachable, but neither explicit current-status text nor a high-confidence eligible current-status image produced a publishable current flag"
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
    print(slug, payload["label"], payload["source_check_status"], f"image_evidence={len(image_results)}")


def main() -> None:
    for slug, cfg in LOCATIONS.items():
        refresh_slug(slug, cfg)


if __name__ == "__main__":
    main()
