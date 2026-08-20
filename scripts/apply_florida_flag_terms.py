#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

try:
    from .florida_flag_terms import PRIMARY_SEVERITY, FloridaFlagState, interpret_florida_flag_terms
except ImportError:
    from florida_flag_terms import PRIMARY_SEVERITY, FloridaFlagState, interpret_florida_flag_terms

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CENTRAL = ZoneInfo("America/Chicago")

ROOT_FLAG = "data/current_flag.json"
LOCATION_FILES = {
    "destin": "data/destin/current_flag.json",
    "okaloosa-island": "data/okaloosa-island/current_flag.json",
    "navarre-beach": "data/navarre-beach/current_flag.json",
    "pensacola-beach": "data/pensacola-beach/current_flag.json",
    "south-walton": "data/south-walton/current_flag.json",
    "cape-san-blas": "data/cape-san-blas/current_flag.json",
    "gulf-state-park-beaches": "data/gulf-state-park-beaches/current_flag.json",
    "st-joe-beach": "data/st-joe-beach/current_flag.json",
    "franklin-county": "data/franklin-county/current_flag.json",
    "anna-maria-island": "data/anna-maria-island/current_flag.json",
    "siesta-key": "data/siesta-key/current_flag.json",
    "venice": "data/venice/current_flag.json",
    "sanibel": "data/sanibel/current_flag.json",
    "fort-myers-beach": "data/fort-myers-beach/current_flag.json",
    "naples": "data/naples/current_flag.json",
    "marco-island": "data/marco-island/current_flag.json",
}

# Additional public pages that are known to carry current conditions or beach-specific reports.
EXTRA_SOURCE_URLS = {
    "destin": ["https://www.destinfire.gov/today-s-warning-condition-beach-flags"],
    "okaloosa-island": ["https://www.myokaloosa.com/ps/beach-safety"],
    "navarre-beach": ["https://santarosa.fl.gov/269/Water-Safety"],
    "pensacola-beach": ["https://myescambia.com/pensacola-beach/pensacola-beach-lifeguards"],
    "anna-maria-island": [
        "https://safebeachday.com/manatee-public-beach/",
        "https://safebeachday.com/cortez-beach/",
        "https://safebeachday.com/coquina-beach-and-cortez-beach/",
    ],
}

CURRENT_CONTEXT = re.compile(
    r"\b(current(?:\s+status|\s+condition(?:s)?)?|today(?:'s)?|posted|beach\s+conditions?|warning\s+condition)\b",
    re.I,
)
TERM_PATTERN = re.compile(
    r"\b(?:water\s+closed(?:\s+to\s+(?:the\s+)?public)?|double\s+red(?:\s+flag)?|two\s+red\s+flags?|single\s+red(?:\s+flag)?|red\s+flag|high\s+hazard|high\s+surf\s+(?:and/or|and|or)\s+currents?|yellow\s+flag|medium\s+hazard|moderate\s+hazard|moderate\s+surf\s+(?:and/or|and|or)\s+currents?|green\s+flag|low\s+hazard|calm\s+conditions(?:\s*,?\s*exercise\s+caution)?|purple\s+flag|dangerous\s+marine\s+life)\b",
    re.I,
)


def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    return s


def merge_states(a: FloridaFlagState, b: FloridaFlagState) -> FloridaFlagState:
    # A newly found primary status wins only when the prior state has no primary.
    primary = a.primary or b.primary
    primary_term = a.primary_term or b.primary_term
    purple = a.purple or b.purple
    purple_term = a.purple_term or b.purple_term
    return FloridaFlagState(primary, purple, primary_term, purple_term)


def state_from_current_text(text: str) -> tuple[FloridaFlagState, str | None]:
    compact = re.sub(r"\s+", " ", text or " ").strip()
    if not compact:
        return FloridaFlagState(), None

    state = FloridaFlagState()
    evidence: list[str] = []
    for context in CURRENT_CONTEXT.finditer(compact):
        start = max(0, context.start() - 80)
        end = min(len(compact), context.end() + 260)
        window = compact[start:end]
        for term in TERM_PATTERN.finditer(window):
            parsed = interpret_florida_flag_terms(term.group(0))
            if parsed.primary or parsed.purple:
                state = merge_states(state, parsed)
                evidence.append(term.group(0))
    return state, "; ".join(dict.fromkeys(evidence)) or None


def scalar_values(obj: object):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                yield from scalar_values(value)
            else:
                yield str(key), value
    elif isinstance(obj, list):
        for value in obj:
            yield from scalar_values(value)


def state_from_structured(obj: object) -> tuple[FloridaFlagState, str | None]:
    state = FloridaFlagState()
    evidence: list[str] = []
    for key, value in scalar_values(obj):
        key_l = key.lower()
        # Structured fields can use standardized status words even when the literal
        # word "flag" is absent. Restrict interpretation to semantic current-status keys.
        if not any(token in key_l for token in ("flag", "status", "condition", "warning", "hazard", "marine")):
            continue
        parsed = interpret_florida_flag_terms(value)
        if parsed.primary or parsed.purple:
            state = merge_states(state, parsed)
            evidence.append(f"{key}={value}")
    return state, "; ".join(evidence) or None


def extract_page_state(html: str) -> tuple[FloridaFlagState, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    combined = FloridaFlagState()
    evidence: list[str] = []

    for script in soup.find_all("script"):
        raw = (script.string or script.get_text(" ") or "").strip()
        if not raw or raw[0] not in "[{":
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        state, why = state_from_structured(obj)
        if state.primary or state.purple:
            combined = merge_states(combined, state)
            if why:
                evidence.append(f"structured:{why}")

    text = " ".join(soup.stripped_strings)
    state, why = state_from_current_text(text)
    if state.primary or state.purple:
        combined = merge_states(combined, state)
        if why:
            evidence.append(f"current-text:{why}")

    return combined, " | ".join(evidence) or None


def candidate_urls(slug: str, payload: dict) -> list[str]:
    urls: list[str] = []
    for value in (
        payload.get("source_url"),
        payload.get("official_authority_url"),
        *EXTRA_SOURCE_URLS.get(slug, []),
    ):
        if not isinstance(value, str) or not value.startswith("https://"):
            continue
        host = (urlparse(value).hostname or "").lower()
        if not host:
            continue
        if value not in urls:
            urls.append(value)
    return urls


def existing_state(payload: dict) -> FloridaFlagState:
    state = interpret_florida_flag_terms(payload.get("flag"))
    if payload.get("purple") is True:
        state = merge_states(state, FloridaFlagState(purple=True, purple_term="existing purple flag"))
    label_state = interpret_florida_flag_terms(payload.get("label"))
    return merge_states(state, label_state)


def update_payload(slug: str, payload: dict, session: requests.Session) -> tuple[dict, bool]:
    state = existing_state(payload)
    verified_state = FloridaFlagState()
    verified_url = None
    verified_evidence = None

    for url in candidate_urls(slug, payload):
        try:
            r = session.get(url, timeout=25)
            r.raise_for_status()
        except requests.RequestException:
            continue
        found, evidence = extract_page_state(r.text)
        if found.primary or found.purple:
            verified_state = merge_states(verified_state, found)
            verified_url = url
            verified_evidence = evidence
            # A primary plus purple is complete enough to stop. A primary alone may
            # still be accompanied by purple on another official page, so continue.
            if verified_state.primary and verified_state.purple:
                break

    # Preserve an already verified primary from the collector. Add/normalize any
    # official terminology found here, especially Purple as an independent overlay.
    final_state = merge_states(state, verified_state)
    before = json.dumps(payload, sort_keys=True, default=str)

    payload["flag"] = final_state.primary
    payload["primary_flag"] = final_state.primary
    payload["purple"] = final_state.purple
    payload["label"] = final_state.label or payload.get("label") or "Official flag status unavailable"
    payload["severity"] = PRIMARY_SEVERITY.get(final_state.primary)
    payload["flag_schema"] = "Florida Beach Warning Flag terminology v1"
    payload["flag_terms_note"] = (
        "Official current wording is normalized as: Water Closed to Public=Double Red; "
        "High Hazard or High Surf and/or Currents=Red; Medium/Moderate Hazard or Moderate Surf and/or Currents=Yellow; "
        "Low Hazard or Calm Conditions, Exercise Caution=Green; Dangerous Marine Life=Purple. "
        "Purple is an independent overlay. Forecast rip-current risk is not converted into a flag."
    )
    if verified_url:
        payload["terminology_verified_url"] = verified_url
        payload["terminology_evidence"] = verified_evidence
        payload["terminology_verified_at"] = datetime.now(CENTRAL).isoformat()

    after = json.dumps(payload, sort_keys=True, default=str)
    return payload, before != after


def path_for(slug: str) -> Path:
    if slug == "pcb":
        return ROOT / ROOT_FLAG
    return ROOT / LOCATION_FILES[slug]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slugs", nargs="*", help="Location slugs; omit to normalize all known current caches")
    args = parser.parse_args()
    slugs = args.slugs or ["pcb", *LOCATION_FILES.keys()]
    s = http_session()
    for slug in slugs:
        path = path_for(slug)
        if not path.exists():
            print(slug, "missing-cache")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload, changed = update_payload(slug, payload, s)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(slug, payload.get("label"), "changed" if changed else "unchanged")


if __name__ == "__main__":
    main()
