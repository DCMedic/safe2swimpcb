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
DATA = ROOT / "data"
CENTRAL = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")
NWS_URL = "https://forecast.weather.gov/product.php?issuedby=TAE&product=SRF&site=NWS&format=txt&glossary=0"
FRANKLIN_URL = "https://www.franklincountyparks.com/parks-recreation/beach-flag-warnings/"
WALTON_URL = "https://www.visitsouthwalton.com/beach-safety/"
GULF_URL = "https://www.visitgulf.com/things-to-do/beaches/beach-safety/"
FLAG_SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Single Red": 3, "Double Red": 4}
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
    if ("double" in text or "two" in text) and "red" in text or "water closed" in text:
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


def parse_franklin_updated(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*", "", value.strip(), flags=re.I)
    cleaned = re.sub(r"\s+(EDT|EST)$", "", cleaned, flags=re.I)
    cleaned = cleaned.replace(" at ", " ")
    try:
        dt = datetime.strptime(f"{cleaned} {datetime.now(EASTERN).year}", "%B %d %I:%M %p %Y")
        return dt.replace(tzinfo=EASTERN)
    except ValueError:
        return None


def parse_nws_flag_table(text: str) -> dict[str, str]:
    flags: dict[str, str] = {}
    for key in NWS_KEYS:
        # Current and archived SRFTAE products use dotted leaders, but tolerate
        # whitespace and optional plural "flags" text to survive formatting changes.
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
    # The first early-morning SRFTAE can precede the day's beach-official flag
    # communication. Walk recent product versions and use the newest table that
    # is still within the accepted freshness window rather than returning null.
    for version in [None, 1, 2, 3, 4, 5, 6, 7, 8]:
        url = _nws_version_url(version)
        r = s.get(url, timeout=30)
        r.raise_for_status()
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
        if age is not None and age <= 24:
            return flags, issued_text, issued, url
    return {}, newest_issued_text, newest_issued, NWS_URL


def parse_franklin_page(html: str) -> dict[str, object | None]:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    flag = None
    image = soup.find("img", alt=re.compile(r"(Double Red|Red|Yellow|Green) Flag", re.I))
    if image:
        flag = normalize_flag(image.get("alt"))
    if not flag:
        for phrase, mapped in {
            "Water Closed": "Double Red",
            "High Hazard": "Red",
            "Medium Hazard": "Yellow",
            "Low Hazard": "Green",
        }.items():
            if phrase.lower() in text.lower():
                flag = mapped
                break
    updated_text = None
    m = re.search(
        r"Last updated:\s*(.+?)(?=\s+(?:Green|Yellow|Red|Double Red|Low Hazard|Medium Hazard|High Hazard|Water Closed)|$)",
        text,
        re.I,
    )
    if m:
        updated_text = m.group(1).strip(" |")
    return {
        "flag": flag,
        "official_updated_text": updated_text,
        "official_updated_at": parse_franklin_updated(updated_text),
    }


def fetch_franklin() -> dict[str, object | None]:
    r = session().get(FRANKLIN_URL, timeout=30)
    r.raise_for_status()
    return parse_franklin_page(r.text)


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
    nws_fresh = bool(nws_flag and nws_age is not None and nws_age <= 24)

    official_flag = franklin.get("flag") if slug == "franklin-county" and franklin else None
    official_updated_text = franklin.get("official_updated_text") if slug == "franklin-county" and franklin else None
    official_updated_at = franklin.get("official_updated_at") if slug == "franklin-county" and franklin else None
    official_age = hours_old(official_updated_at, now) if isinstance(official_updated_at, datetime) else None
    official_fresh = bool(official_flag and official_age is not None and official_age <= 24)

    if official_fresh:
        flag = str(official_flag)
        tier = "primary_official"
        source_name = cfg["authority"]
        source_url = cfg["official_url"]
        method = "Direct official current-condition page snapshot"
        corroborating_flag = nws_flag if nws_fresh else None
        corroborates = bool(corroborating_flag and corroborating_flag == flag)
        stale_after_hours = 24
        stale_reason = None
    elif nws_fresh:
        flag = str(nws_flag)
        tier = "official_report_via_nws"
        source_name = "NWS Tallahassee SRFTAE, based on communication with area beach officials"
        source_url = nws_source_url
        method = "Newest fresh SRFTAE flag table reported by area beach officials; never inferred from rip-current risk"
        corroborating_flag = None
        corroborates = None
        stale_after_hours = 24
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
        "official_age_hours": round(official_age, 2) if official_age is not None else None,
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
        print(f"Franklin official source unavailable: {exc}")

    missing = [cfg["nws_key"] for cfg in LOCATIONS.values() if cfg["nws_key"] not in nws_flags]
    if missing:
        print("No fresh NWS flag found for:", ", ".join(sorted(set(missing))))

    for slug, cfg in LOCATIONS.items():
        write_payload(slug, cfg, nws_flags, nws_issued_text, nws_issued_at, nws_source_url, franklin)
    print("eastern Panhandle current flags updated", datetime.now(CENTRAL).isoformat())


if __name__ == "__main__":
    main()
