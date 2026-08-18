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
FLAG_SEVERITY = {"Green": 1, "Yellow": 2, "Red": 3, "Double Red": 4}

LOCATIONS = {
    "south-walton": {
        "name": "South Walton / 30A",
        "authority": "Walton County beach officials / South Walton Fire District",
        "official_url": WALTON_URL,
        "nws_key": "Walton",
        "timezone": CENTRAL,
        "source_note": "Visit South Walton directs visitors to its beach-safety alert service; NWS Tallahassee republishes the flag reported by area beach officials.",
    },
    "cape-san-blas": {
        "name": "Cape San Blas / Indian Pass",
        "authority": "South Gulf Fire Rescue / Gulf County beach officials",
        "official_url": GULF_URL,
        "nws_key": "West Facing Gulf Beaches",
        "timezone": EASTERN,
        "source_note": "Gulf County tourism states South Gulf Fire Rescue/community volunteers manage Cape San Blas and Indian Pass flags. NWS Tallahassee republishes west-facing Gulf County flags reported by area beach officials.",
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
        "source_note": "Visit Gulf notes St. Joe Beach is not managed by South Gulf Fire Rescue. NWS Tallahassee separately reports south-facing Gulf County flags based on communication with area beach officials.",
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
    if "double" in text and "red" in text:
        return "Double Red"
    if re.search(r"\bred\b", text):
        return "Red"
    if re.search(r"\byellow\b", text):
        return "Yellow"
    if re.search(r"\bgreen\b", text):
        return "Green"
    return None


def fetch_nws_flags() -> tuple[dict[str, str], str | None]:
    r = session().get(NWS_URL, timeout=30)
    r.raise_for_status()
    text = BeautifulSoup(r.text, "html.parser").get_text("\n")
    flags: dict[str, str] = {}
    for key in [
        "Walton",
        "Bay",
        "State Park Gulf Beaches",
        "West Facing Gulf Beaches",
        "South Facing Gulf Beaches",
        "Franklin",
    ]:
        m = re.search(rf"(?mi)^\s*{re.escape(key)}\.*\s*(DOUBLE\s+RED|RED|YELLOW|GREEN)\.?\s*$", text)
        if m:
            flag = normalize_flag(m.group(1))
            if flag:
                flags[key] = flag
    issued = None
    m = re.search(r"(?mi)^\s*National Weather Service Tallahassee FL\s*\n\s*(.+?\d{4})\s*$", text)
    if m:
        issued = m.group(1).strip()
    return flags, issued


def fetch_franklin() -> dict[str, str | None]:
    r = session().get(FRANKLIN_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = " ".join(soup.stripped_strings)
    flag = None
    image = soup.find("img", alt=re.compile(r"(Double Red|Red|Yellow|Green) Flag", re.I))
    if image:
        flag = normalize_flag(image.get("alt"))
    if not flag:
        for phrase, mapped in {
            "Low Hazard": "Green",
            "Medium Hazard": "Yellow",
            "High Hazard": "Red",
            "Water Closed": "Double Red",
        }.items():
            if phrase.lower() in text.lower():
                flag = mapped
                break
    updated = None
    m = re.search(
        r"Last updated:\s*([^|]+?)(?=\s+(?:Green|Yellow|Red|Double Red|Low Hazard|Medium Hazard|High Hazard|Water Closed)|$)",
        text,
        re.I,
    )
    if m:
        updated = m.group(1).strip()
    return {"flag": flag, "official_updated_text": updated}


def write_payload(
    slug: str,
    cfg: dict,
    nws_flags: dict[str, str],
    nws_issued: str | None,
    franklin: dict[str, str | None] | None,
) -> None:
    out = DATA / slug
    out.mkdir(parents=True, exist_ok=True)
    now = datetime.now(cfg["timezone"])
    nws_flag = nws_flags.get(cfg["nws_key"])
    official_flag = franklin.get("flag") if slug == "franklin-county" and franklin else None
    official_updated = franklin.get("official_updated_text") if slug == "franklin-county" and franklin else None

    if official_flag:
        flag = official_flag
        tier = "primary_official"
        source_name = cfg["authority"]
        source_url = cfg["official_url"]
        method = "Direct official current-condition page snapshot"
        corroborating_flag = nws_flag
        corroborates = bool(nws_flag and nws_flag == official_flag)
        stale_after_hours = 12
    elif nws_flag:
        flag = nws_flag
        tier = "official_report_via_nws"
        source_name = "NWS Tallahassee SRFTAE, based on communication with area beach officials"
        source_url = NWS_URL
        method = "Authoritative secondary publication of flag reported by area beach officials; not inferred from rip-current risk"
        corroborating_flag = None
        corroborates = None
        stale_after_hours = 18
    else:
        flag = None
        tier = "unavailable"
        source_name = cfg["authority"]
        source_url = cfg["official_url"]
        method = "No current authoritative flag could be verified; Know the Gulf does not infer flags from weather or rip-current forecasts"
        corroborating_flag = None
        corroborates = None
        stale_after_hours = 0

    payload = {
        "location": cfg["name"],
        "flag": flag,
        "label": flag if flag else "Official flag status unavailable",
        "severity": FLAG_SEVERITY.get(flag),
        "provenance_tier": tier,
        "last_verified_at": now.isoformat(),
        "official_updated_text": official_updated,
        "source_name": source_name,
        "source_url": source_url,
        "official_authority": cfg["authority"],
        "official_authority_url": cfg["official_url"],
        "method": method,
        "stale_after_hours": stale_after_hours,
        "nws_reported_flag": nws_flag,
        "nws_issued_text": nws_issued,
        "nws_source_url": NWS_URL,
        "corroborating_flag": corroborating_flag,
        "corroborates_primary": corroborates,
        "source_note": cfg["source_note"],
        "safety_note": "Know the Gulf never derives a beach flag from forecast weather, surf height, or rip-current risk. When authoritative flag evidence is unavailable or stale, the public status should be shown as unavailable.",
    }
    (out / "current_flag.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    nws_flags, nws_issued = fetch_nws_flags()
    franklin = None
    try:
        franklin = fetch_franklin()
    except requests.RequestException as exc:
        print(f"Franklin official source unavailable: {exc}")

    missing = [cfg["nws_key"] for cfg in LOCATIONS.values() if cfg["nws_key"] not in nws_flags]
    if missing:
        print("NWS did not expose all expected flag keys:", ", ".join(sorted(set(missing))))

    for slug, cfg in LOCATIONS.items():
        write_payload(slug, cfg, nws_flags, nws_issued, franklin)
    print("eastern Panhandle current flags updated", datetime.now(CENTRAL).isoformat())


if __name__ == "__main__":
    main()
