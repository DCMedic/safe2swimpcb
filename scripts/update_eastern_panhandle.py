#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CENTRAL = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")
NWS_URL = "https://forecast.weather.gov/product.php?issuedby=TAE&product=SRF&site=NWS&format=txt&glossary=0"
FRANKLIN_URL = "https://www.franklincountyparks.com/parks-recreation/beach-flag-warnings/"
WALTON_URL = "https://www.visitsouthwalton.com/beach-safety/"
GULF_URL = "https://www.visitgulf.com/things-to-do/beaches/beach-safety/"
FLAG_SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Single Red": 3, "Double Red": 4}
MAX_OFFICIAL_AGE_HOURS = 24
NWS_KEYS = [
    "Walton",
    "Bay",
    "State Park Gulf Beaches",
    "West Facing Gulf Beaches",
    "South Facing Gulf Beaches",
    "Franklin",
]

LOCATIONS = {
    "south-walton": {
        "name": "South Walton / 30A",
        "authority": "Walton County beach officials / South Walton Fire District",
        "official_url": WALTON_URL,
        "nws_key": "Walton",
        "timezone": CENTRAL,
        "source_note": "NWS Tallahassee republishes the flag reported by Walton-area beach officials; Visit South Walton supplies the public beach-safety program.",
    },
    "cape-san-blas": {
        "name": "Cape San Blas / Indian Pass",
        "authority": "South Gulf Fire Rescue / Gulf County beach officials",
        "official_url": GULF_URL,
        "nws_key": "West Facing Gulf Beaches",
        "timezone": EASTERN,
        "source_note": "NWS Tallahassee republishes west-facing Gulf County flags reported by area beach officials.",
    },
    "gulf-state-park-beaches": {
        "name": "Gulf County State Park Beaches",
        "authority": "Gulf County / state park beach officials",
        "official_url": GULF_URL,
        "nws_key": "State Park Gulf Beaches",
        "timezone": EASTERN,
        "source_note": "NWS Tallahassee separately reports State Park Gulf Beaches based on communication with area beach officials.",
    },
    "st-joe-beach": {
        "name": "St. Joe Beach",
        "authority": "Gulf County beach officials",
        "official_url": GULF_URL,
        "nws_key": "South Facing Gulf Beaches",
        "timezone": EASTERN,
        "source_note": "NWS Tallahassee separately reports south-facing Gulf County flags based on communication with area beach officials.",
    },
    "franklin-county": {
        "name": "Franklin County / St. George Island",
        "authority": "Franklin County Board of County Commissioners / Parks & Recreation",
        "official_url": FRANKLIN_URL,
        "nws_key": "Franklin",
        "timezone": EASTERN,
        "source_note": "Franklin County publishes current beach conditions directly; NWS Tallahassee provides a corroborating flag reported by area beach officials.",
    },
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "KnowTheGulf/1.0 (+https://knowthegulf.com)"})
    return s


def normalize_flag(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"[^A-Za-z ]+", " ", value).strip().lower()
    if (("double" in text or "two" in text) and "red" in text) or "water closed" in text:
        return "Double Red"
    if re.search(r"\bred\b", text):
        return "Red"
    if re.search(r"\byellow\b", text):
        return "Yellow"
    if re.search(r"\bgreen\b", text):
        return "Green"
    return None


def hours_old(ts: datetime | None, now: datetime) -> float | None:
    if ts is None:
        return None
    return max(0.0, (now.astimezone(ts.tzinfo) - ts).total_seconds() / 3600.0)


def parse_nws_issued(text: str) -> datetime | None:
    m = re.search(
        r"(?mi)^\s*(\d{3,4}\s+[AP]M)\s+(?:EDT|EST)\s+([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4})\s*$",
        text,
    )
    if not m:
        return None
    raw_time = m.group(1).zfill(7)
    try:
        return datetime.strptime(f"{raw_time} {m.group(2)}", "%I%M %p %a %b %d %Y").replace(tzinfo=EASTERN)
    except ValueError:
        return None


def parse_franklin_updated(value: str | None, now: datetime | None = None) -> datetime | None:
    if not value:
        return None
    reference = now.astimezone(EASTERN) if now else datetime.now(EASTERN)
    cleaned = value.strip().replace("\u00a0", " ")
    cleaned = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+(EDT|EST)$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+at\s+", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")

    formats_with_year = ("%B %d, %Y %I:%M %p", "%B %d %Y %I:%M %p")
    for fmt in formats_with_year:
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=EASTERN)
        except ValueError:
            pass

    for year in (reference.year, reference.year - 1, reference.year + 1):
        for fmt in ("%B %d %I:%M %p", "%b %d %I:%M %p"):
            try:
                candidate = datetime.strptime(f"{cleaned} {year}", f"{fmt} %Y").replace(tzinfo=EASTERN)
            except ValueError:
                continue
            if abs((reference - candidate).total_seconds()) <= 370 * 24 * 3600:
                return candidate
    return None


def parse_nws_flag_table(text: str) -> dict[str, str]:
    flags: dict[str, str] = {}
    for key in NWS_KEYS:
        patterns = [
            rf"(?mi)^\s*{re.escape(key)}\s*\.*\s*(DOUBLE\s+RED|RED|YELLOW|GREEN)(?:\s+FLAGS?)?\.?\s*$",
            rf"(?mi)^\s*{re.escape(key)}\s*[:=-]\s*(DOUBLE\s+RED|RED|YELLOW|GREEN)(?:\s+FLAGS?)?\.?\s*$",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                flag = normalize_flag(m.group(1))
                if flag:
                    flags[key] = flag
                    break
    return flags


def _nws_version_url(version: int | None) -> str:
    if version is None:
        return NWS_URL
    return f"{NWS_URL}&version={version}"


def fetch_nws_flags() -> tuple[dict[str, str], str | None, datetime | None, str]:
    s = session()
    newest_issued: datetime | None = None
    newest_issued_text: str | None = None
    last_url = NWS_URL

    for version in [None, 1, 2, 3, 4, 5, 6, 7, 8]:
        url = _nws_version_url(version)
        last_url = url
        try:
            r = s.get(url, timeout=(5, 10))
            r.raise_for_status()
        except requests.RequestException as exc:
            print(f"NWS SRFTAE unavailable for {url}: {type(exc).__name__}: {exc}")
            continue

        text = BeautifulSoup(r.text, "html.parser").get_text("\n")
        issued = parse_nws_issued(text)
        m = re.search(r"(?mi)^\s*National Weather Service Tallahassee FL\s*\n\s*(.+?\d{4})\s*$", text)
        issued_text = m.group(1).strip() if m else None
        if newest_issued is None and issued is not None:
            newest_issued = issued
            newest_issued_text = issued_text
        flags = parse_nws_flag_table(text)
        if not flags:
            continue
        age = hours_old(issued, datetime.now(EASTERN)) if issued else None
        if age is not None and age <= MAX_OFFICIAL_AGE_HOURS:
            return flags, issued_text, issued, url

    return {}, newest_issued_text, newest_issued, last_url


def _franklin_current_text(soup: BeautifulSoup) -> tuple[str, object]:
    heading = soup.find(lambda tag: tag.name in {"h1", "h2", "h3", "h4"} and "current beach conditions" in tag.get_text(" ", strip=True).lower())
    if not heading:
        return " ".join(soup.stripped_strings), soup

    pieces: list[str] = []
    for node in heading.next_elements:
        if node is heading:
            continue
        name = getattr(node, "name", None)
        if name in {"h1", "h2", "h3", "h4"}:
            break
        if isinstance(node, str):
            value = node.strip()
            if value:
                pieces.append(value)
    return " ".join(pieces), heading.parent or soup


def parse_franklin_page(html: str, fetched_at: datetime | None = None) -> dict[str, object | None]:
    fetched_at = fetched_at.astimezone(EASTERN) if fetched_at else datetime.now(EASTERN)
    soup = BeautifulSoup(html, "html.parser")
    current_text, current_container = _franklin_current_text(soup)

    flag = None
    image = current_container.find("img", alt=re.compile(r"(Double Red|Red|Yellow|Green) Flag", re.I))
    if image:
        flag = normalize_flag(image.get("alt"))
    if not flag:
        for phrase, mapped in {
            "Water Closed": "Double Red",
            "High Hazard": "Red",
            "Medium Hazard": "Yellow",
            "Moderate Hazard": "Yellow",
            "Low Hazard": "Green",
        }.items():
            if phrase.lower() in current_text.lower():
                flag = mapped
                break

    updated_text = None
    m = re.search(
        r"Last\s+updated\s*:?\s*(.+?)(?=\s+(?:Green|Yellow|Red|Double Red|Low Hazard|Medium Hazard|Moderate Hazard|High Hazard|Water Closed|Moderate Surf|High Surf|Calm Conditions)|$)",
        current_text,
        re.I,
    )
    if m:
        updated_text = m.group(1).strip(" |")
    updated_at = parse_franklin_updated(updated_text, now=fetched_at)

    return {
        "flag": flag,
        "official_updated_text": updated_text,
        "official_updated_at": updated_at,
        "fetched_at": fetched_at,
        "timestamp_basis": "official_page" if updated_at else ("fetch_time" if flag else None),
    }


def fetch_franklin(attempts: int = 3) -> dict[str, object | None]:
    s = session()
    last_exc: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = s.get(FRANKLIN_URL, timeout=(5, 12))
            r.raise_for_status()
            parsed = parse_franklin_page(r.text, fetched_at=datetime.now(EASTERN))
            if parsed.get("flag"):
                return parsed
            raise requests.RequestException("Franklin page loaded but no explicit current-condition flag was parsed")
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_exc is not None
    raise last_exc


def load_previous_payload(slug: str) -> dict[str, object] | None:
    path = DATA / slug / "current_flag.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def cached_franklin_observation(now: datetime) -> dict[str, object | None] | None:
    previous = load_previous_payload("franklin-county")
    if not previous:
        return None
    flag = normalize_flag(previous.get("flag") if isinstance(previous.get("flag"), str) else None)
    observed_at = parse_iso_datetime(previous.get("official_updated_at"))
    if observed_at is None and previous.get("timestamp_basis") == "fetch_time":
        observed_at = parse_iso_datetime(previous.get("official_observed_at"))
    age = hours_old(observed_at, now) if observed_at else None
    if not flag or age is None or age > MAX_OFFICIAL_AGE_HOURS:
        return None
    return {
        "flag": flag,
        "official_updated_text": previous.get("official_updated_text"),
        "official_updated_at": parse_iso_datetime(previous.get("official_updated_at")),
        "fetched_at": parse_iso_datetime(previous.get("official_observed_at")) or observed_at,
        "timestamp_basis": previous.get("timestamp_basis") or "official_page",
        "cached": True,
    }


def write_payload(
    slug: str,
    cfg: dict,
    nws_flags: dict[str, str],
    nws_issued_text: str | None,
    nws_issued_at: datetime | None,
    nws_source_url: str,
    franklin: dict[str, object | None] | None,
) -> None:
    out = DATA / slug
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(cfg["timezone"])
    nws_flag = nws_flags.get(cfg["nws_key"])
    nws_age = hours_old(nws_issued_at, now)
    nws_fresh = bool(nws_flag and nws_age is not None and nws_age <= MAX_OFFICIAL_AGE_HOURS)

    official_flag = franklin.get("flag") if slug == "franklin-county" and franklin else None
    official_updated_text = franklin.get("official_updated_text") if slug == "franklin-county" and franklin else None
    official_updated_at = franklin.get("official_updated_at") if slug == "franklin-county" and franklin else None
    fetched_at = franklin.get("fetched_at") if slug == "franklin-county" and franklin else None
    timestamp_basis = franklin.get("timestamp_basis") if slug == "franklin-county" and franklin else None
    cached = bool(franklin.get("cached")) if slug == "franklin-county" and franklin else False

    evidence_at = official_updated_at if isinstance(official_updated_at, datetime) else fetched_at if isinstance(fetched_at, datetime) else None
    official_age = hours_old(evidence_at, now) if evidence_at else None
    official_fresh = bool(official_flag and official_age is not None and official_age <= MAX_OFFICIAL_AGE_HOURS)

    if official_fresh:
        flag = str(official_flag)
        tier = "primary_official_cached" if cached else "primary_official"
        source_name = cfg["authority"]
        source_url = cfg["official_url"]
        method = "Still-fresh last-known official current-condition observation retained after a transient source failure" if cached else "Direct official current-condition page snapshot"
        corroborating_flag = nws_flag if nws_fresh else None
        corroborates = bool(corroborating_flag and corroborating_flag == flag)
        stale_after_hours = MAX_OFFICIAL_AGE_HOURS
        stale_reason = "Direct source could not be refreshed; cached official observation remains within the accepted freshness window" if cached else None
    elif nws_fresh:
        flag = str(nws_flag)
        tier = "official_report_via_nws"
        source_name = "NWS Tallahassee SRFTAE, based on communication with area beach officials"
        source_url = nws_source_url
        method = "Newest fresh SRFTAE flag table reported by area beach officials; never inferred from rip-current risk"
        corroborating_flag = None
        corroborates = None
        stale_after_hours = MAX_OFFICIAL_AGE_HOURS
        stale_reason = "Direct official source unavailable or stale; using fresh NWS-republished official report" if slug == "franklin-county" else None
    else:
        flag = None
        tier = "unavailable"
        source_name = cfg["authority"]
        source_url = cfg["official_url"]
        method = "No current authoritative flag could be verified; Know the Gulf does not infer flags from weather or rip-current forecasts"
        corroborating_flag = None
        corroborates = None
        stale_after_hours = 0
        stale_reason = "Authoritative flag evidence is missing or older than the accepted freshness window"

    payload = {
        "location": cfg["name"],
        "flag": flag,
        "label": flag if flag else "Official flag status unavailable",
        "severity": FLAG_SEVERITY.get(flag),
        "provenance_tier": tier,
        "last_verified_at": now.isoformat(),
        "official_updated_text": official_updated_text,
        "official_updated_at": official_updated_at.isoformat() if isinstance(official_updated_at, datetime) else None,
        "official_observed_at": evidence_at.isoformat() if isinstance(evidence_at, datetime) else None,
        "official_age_hours": round(official_age, 2) if official_age is not None else None,
        "timestamp_basis": timestamp_basis,
        "source_name": source_name,
        "source_url": source_url,
        "official_authority": cfg["authority"],
        "official_authority_url": cfg["official_url"],
        "method": method,
        "stale_after_hours": stale_after_hours,
        "stale_reason": stale_reason,
        "nws_reported_flag": nws_flag,
        "nws_issued_text": nws_issued_text,
        "nws_issued_at": nws_issued_at.isoformat() if nws_issued_at else None,
        "nws_age_hours": round(nws_age, 2) if nws_age is not None else None,
        "nws_source_url": nws_source_url,
        "corroborating_flag": corroborating_flag,
        "corroborates_primary": corroborates,
        "source_note": cfg["source_note"],
        "safety_note": "Know the Gulf displays only explicit flags from local authorities or an NWS product that says the flag was reported by area beach officials. Forecast risk is never converted into a flag.",
    }
    (out / "current_flag.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    nws_flags, nws_issued_text, nws_issued_at, nws_source_url = fetch_nws_flags()
    franklin = None
    try:
        franklin = fetch_franklin()
    except requests.RequestException as exc:
        print(f"Franklin official source unavailable: {type(exc).__name__}: {exc}")
        franklin = cached_franklin_observation(datetime.now(EASTERN))
        if franklin:
            print("Retaining still-fresh cached Franklin official observation")

    missing = [cfg["nws_key"] for cfg in LOCATIONS.values() if cfg["nws_key"] not in nws_flags]
    if missing:
        print("No fresh NWS flag found for:", ", ".join(sorted(set(missing))))

    for slug, cfg in LOCATIONS.items():
        write_payload(slug, cfg, nws_flags, nws_issued_text, nws_issued_at, nws_source_url, franklin)
    print("eastern Panhandle current flags updated", datetime.now(CENTRAL).isoformat())


if __name__ == "__main__":
    main()
