#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

try:
    from .florida_flag_terms import PRIMARY_SEVERITY, FloridaFlagState, interpret_florida_flag_terms
except ImportError:
    from florida_flag_terms import PRIMARY_SEVERITY, FloridaFlagState, interpret_florida_flag_terms

try:
    from .source_evidence import reset_primary_evidence
except ImportError:
    from source_evidence import reset_primary_evidence

ROOT = Path(__file__).resolve().parents[1]
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

TERM_PATTERN = re.compile(
    r"\b(?:water\s+closed(?:\s+to\s+(?:the\s+)?public)?|double\s+red(?:\s+flag)?|two\s+red\s+flags?|single\s+red(?:\s+flag)?|red\s+flag|high\s+hazard|high\s+surf\s+(?:and/or|and|or)\s+currents?|yellow\s+flag|medium\s+hazard|moderate\s+hazard|moderate\s+surf\s+(?:and/or|and|or)\s+currents?|green\s+flag|low\s+hazard|calm\s+conditions(?:\s*,?\s*exercise\s+caution)?|purple\s+flag|dangerous\s+marine\s+life)\b",
    re.I,
)
CURRENT_LINE = re.compile(
    r"\b(?:current\s+(?:status|condition(?:s)?|beach\s+condition(?:s)?|warning\s+condition|flag(?:s)?|flag\s+condition(?:s)?|beach\s+flag(?:s)?|beach\s+flag\s+condition(?:s)?)|today(?:'s)?\s+(?:status|condition(?:s)?|beach\s+condition(?:s)?|flag(?:s)?|flag\s+condition(?:s)?|warning\s+condition)|posted\s+(?:flag(?:s)?|warning\s+condition))\b\s*(?:is|are|:|-)?\s*(.{0,180})",
    re.I,
)
CURRENT_SECTION_BOUNDARY = re.compile(
    r"\b(?:beach\s+flag\s+warnings?|beach\s+warning\s+flags?|flag\s+warnings?|flag\s+meanings?|"
    r"warning\s+flag\s+system|beach\s+warning\s+flag\s+system|what\s+do\s+the\s+flags\s+mean|"
    r"what\s+each\s+flag\s+means|legend|rules|frequently\s+asked\s+questions|safety\s+tips?)\b",
    re.I,
)
BARE_CURRENT_COLOR = re.compile(r"^\s*(double\s+red|single\s+red|red|yellow|green|purple)\b", re.I)


def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    return s


@dataclass(frozen=True)
class CurrentFlagState(FloridaFlagState):
    distinct_flags: tuple[str, ...] = ()

    @property
    def conflict(self) -> bool:
        return len(self.distinct_flags) > 1


def merge_states(a: FloridaFlagState, b: FloridaFlagState) -> CurrentFlagState:
    flags = set(getattr(a, 'distinct_flags', ())) | set(getattr(b, 'distinct_flags', ()))
    flags.update(flag for flag in (a.primary, b.primary) if flag)
    return CurrentFlagState(
        primary=next(iter(flags)) if len(flags) == 1 else None,
        purple=a.purple or b.purple,
        primary_term=a.primary_term or b.primary_term,
        purple_term=a.purple_term or b.purple_term,
        distinct_flags=tuple(sorted(flags)),
    )


def has_evidence(state: FloridaFlagState) -> bool:
    return bool(state.primary or state.purple or getattr(state, 'distinct_flags', ()))


def parse_current_value(value: object) -> FloridaFlagState:
    state = FloridaFlagState()
    terms = list(TERM_PATTERN.finditer(str(value or '')))
    if not terms:
        state = interpret_florida_flag_terms(value)
    for term in terms:
        state = merge_states(state, interpret_florida_flag_terms(term.group(0)))
    for piece in re.split(r'[;,|]', str(value or '')):
        if re.fullmatch(r'\s*(?:double red|single red|red|yellow|green|purple)\s*', piece, re.I):
            state = merge_states(state, interpret_florida_flag_terms(piece))
    return state


def state_from_current_text(text: str) -> tuple[FloridaFlagState, str | None]:
    compact = re.sub(r"\s+", " ", text or " ").strip()
    state = FloridaFlagState()
    evidence: list[str] = []
    for match in CURRENT_LINE.finditer(compact):
        segment = CURRENT_SECTION_BOUNDARY.split(match.group(1), maxsplit=1)[0]
        bare = BARE_CURRENT_COLOR.search(segment)
        if bare:
            parsed = interpret_florida_flag_terms(bare.group(1))
            state = merge_states(state, parsed)
            evidence.append(bare.group(1))
        for piece in re.split(r'[;,|]', segment):
            if re.fullmatch(r'\s*(?:double red|single red|red|yellow|green|purple)\s*', piece, re.I):
                state = merge_states(state, interpret_florida_flag_terms(piece))
        terms = list(TERM_PATTERN.finditer(segment))
        for term in terms:
            parsed = interpret_florida_flag_terms(term.group(0))
            if has_evidence(parsed):
                state = merge_states(state, parsed)
                evidence.append(term.group(0))
    return state, "; ".join(dict.fromkeys(evidence)) or None


def contains_beach(obj: object, beach_names: list[str]) -> bool:
    if not beach_names:
        return False
    if isinstance(obj, dict):
        return any(contains_beach(v, beach_names) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_beach(v, beach_names) for v in obj)
    text = str(obj or "").lower()
    return any(name.lower() in text for name in beach_names)


def state_from_record(record: object) -> tuple[FloridaFlagState, str | None]:
    state = FloridaFlagState()
    evidence: list[str] = []
    if isinstance(record, dict):
        for key, value in record.items():
            key_l = str(key).lower()
            if any(token in key_l for token in ('legend', 'definition', 'forecast', 'meaning')):
                continue
            if isinstance(value, (dict, list)):
                child, why = state_from_record(value)
                state = merge_states(state, child)
                if why:
                    evidence.append(why)
                continue
            key_l = str(key).lower()
            if not any(token in key_l for token in ("flag", "status", "condition", "warning", "hazard", "marine")):
                continue
            parsed = parse_current_value(value)
            if has_evidence(parsed):
                state = merge_states(state, parsed)
                evidence.append(f"{key}={value}")
    elif isinstance(record, list):
        for child in record:
            child_state, why = state_from_record(child)
            state = merge_states(state, child_state)
            if why:
                evidence.append(why)
    return state, "; ".join(evidence) or None


def state_from_structured(obj: object, beach_names: list[str]) -> tuple[FloridaFlagState, str | None]:
    if not beach_names or not contains_beach(obj, beach_names):
        return FloridaFlagState(), None
    if isinstance(obj, dict):
        direct = " ".join(str(v or "") for v in obj.values() if not isinstance(v, (dict, list))).lower()
        if any(name.lower() in direct for name in beach_names):
            return state_from_record(obj)
        children = [value for key, value in obj.items()
                    if not any(token in str(key).lower() for token in ('legend', 'definition', 'forecast', 'meaning'))]
    else:
        children = obj if isinstance(obj, list) else []
    combined = FloridaFlagState()
    reasons = []
    for child in children:
        if isinstance(child, (dict, list)) and contains_beach(child, beach_names):
            state, why = state_from_structured(child, beach_names)
            combined = merge_states(combined, state)
            if why:
                reasons.append(why)
    return combined, "; ".join(reasons) or None


def extract_page_state(html: str, beach_names: list[str]) -> tuple[FloridaFlagState, str | None]:
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
        state, why = state_from_structured(obj, beach_names)
        if has_evidence(state):
            combined = merge_states(combined, state)
            if why:
                evidence.append(f"structured:{why}")
    text = " ".join(soup.stripped_strings)
    state, why = state_from_current_text(text)
    if has_evidence(state):
        combined = merge_states(combined, state)
        if why:
            evidence.append(f"current-text:{why}")
    return combined, " | ".join(evidence) or None


def candidate_urls(slug: str, payload: dict) -> list[str]:
    urls: list[str] = []
    for value in (payload.get("official_authority_url"), payload.get("source_url"), *EXTRA_SOURCE_URLS.get(slug, [])):
        if not isinstance(value, str) or not value.startswith("https://"):
            continue
        if not (urlparse(value).hostname or ""):
            continue
        if value not in urls:
            urls.append(value)
    return urls


def existing_state(payload: dict) -> FloridaFlagState:
    state = interpret_florida_flag_terms(payload.get("flag"))
    if payload.get("purple") is True:
        state = merge_states(state, FloridaFlagState(purple=True, purple_term="existing purple flag"))
    return merge_states(state, interpret_florida_flag_terms(payload.get("label")))


def update_payload(slug: str, payload: dict, session: requests.Session) -> tuple[dict, bool]:
    existing = existing_state(payload)
    verified = FloridaFlagState()
    verified_url = None
    verified_evidence = None
    beach_names = [str(x) for x in payload.get("beaches", []) if x]

    for url in candidate_urls(slug, payload):
        try:
            r = session.get(url, timeout=25)
            r.raise_for_status()
        except requests.RequestException:
            continue
        found, evidence = extract_page_state(r.text, beach_names)
        if not has_evidence(found):
            continue

        had_primary = verified.primary is not None
        had_purple = verified.purple
        verified = merge_states(verified, found)
        if verified_url is None or (found.primary and not had_primary):
            verified_url = url
            verified_evidence = evidence
        elif found.purple and not had_purple and verified.primary is None:
            verified_url = url
            verified_evidence = evidence

    # A fresh verified primary is a complete current primary observation. It must
    # not inherit a stale Purple overlay from the previous cache. If the only new
    # evidence is Purple, preserve the existing primary and add the overlay.
    if has_evidence(verified) and getattr(verified, "conflict", False):
        final_state = verified
    elif verified.primary:
        final_state = verified
    elif verified.purple:
        final_state = merge_states(existing, verified)
    else:
        final_state = existing

    before = json.dumps(payload, sort_keys=True, default=str)
    payload["flag"] = final_state.primary
    payload["primary_flag"] = final_state.primary
    payload["purple"] = final_state.purple
    payload["label"] = final_state.label or payload.get("label") or "Official flag status unavailable"
    payload["severity"] = PRIMARY_SEVERITY.get(final_state.primary)
    if getattr(final_state, "conflict", False):
        payload["flag_conflict"] = True
        payload["fresh_distinct_flags"] = list(final_state.distinct_flags)
        payload["label"] = "Conflicting current flag reports. Check your beach."

    payload["flag_schema"] = "Florida Beach Warning Flag terminology v1"
    payload["flag_terms_note"] = (
        "Official current wording is normalized as: Water Closed to Public=Double Red; "
        "High Hazard or High Surf and/or Currents=Red; Medium/Moderate Hazard or Moderate Surf and/or Currents=Yellow; "
        "Low Hazard or Calm Conditions, Exercise Caution=Green; Dangerous Marine Life=Purple. "
        "Purple is an independent overlay. Forecast rip-current risk is not converted into a flag. "
        "Generic current-text evidence is bounded before legend, warning, rules, FAQ, and safety-education sections."
    )
    if verified_url:
        verified_at = datetime.now(CENTRAL).isoformat()
        payload["terminology_verified_url"] = verified_url
        payload["terminology_evidence"] = verified_evidence
        payload["terminology_verified_at"] = verified_at
        if getattr(verified, "conflict", False):
            reset_primary_evidence(payload, verified_at, verified_url)
            payload["flag_conflict"] = True
            payload["fresh_distinct_flags"] = list(verified.distinct_flags)
            payload["source_check_status"] = "conflict"
            payload["last_checked_at"] = verified_at
            payload["provenance_tier"] = "primary_official_terminology_conflict"
        elif verified.primary:
            payload.pop("fresh_distinct_flags", None)
            prior_url = payload.get("source_url")
            prior_name = payload.get("source_name")
            if prior_url and prior_url != verified_url:
                payload["secondary_source_url"] = prior_url
                payload["secondary_source_name"] = prior_name
            payload["source_url"] = verified_url
            payload["source_name"] = payload.get("official_authority") or prior_name or "Official beach-safety authority"
            payload["method"] = "Direct official current-condition terminology normalized under Florida Beach Warning Flag definitions"
            payload["provenance_tier"] = "primary_official_terminology"
            payload["cached"] = False
            payload["source_check_status"] = "verified"
            # Re-reading dated current wording does not create a new issuance.
            same_dated_source = verified_url in (prior_url, payload.get("official_authority_url")) and (
                payload.get("official_updated_at") is not None or payload.get("official_updated_text") is not None)
            official_stamp = payload.get("official_updated_at")
            selected_stamp = official_stamp if same_dated_source else verified_at
            reset_primary_evidence(payload, selected_stamp, verified_url)
            if same_dated_source:
                payload["official_updated_at"] = official_stamp
            payload["last_verified_at"] = verified_at
            payload["last_checked_at"] = verified_at
            payload["stale_reason"] = None
            for transient_key in ("source_error", "cache_age_hours", "cached_from_provenance_tier"):
                payload.pop(transient_key, None)
    after = json.dumps(payload, sort_keys=True, default=str)
    return payload, before != after


def path_for(slug: str) -> Path:
    return ROOT / (ROOT_FLAG if slug == "pcb" else LOCATION_FILES[slug])


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
